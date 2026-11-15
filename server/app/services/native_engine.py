"""Inference-only Auto-AVSR adapter for full native research checkpoints.

Loads all 767 native state entries strictly; no training initializer, optimizer,
Lightning wrapper or audio enters this path.
"""

from __future__ import annotations

import gc
import os
import sys
import time

from .auto_avsr_engine import AutoAvsrEngine
from .engine import EngineResult
from .word_alignment import align_words
from .decoder_cache import cached_cross_attention


class NativeAvsrEngine(AutoAvsrEngine):
    def _load_impl(self):
        import torch
        import sentencepiece

        started = time.perf_counter()
        self._torch = torch
        self.cuda_available = torch.cuda.is_available()
        device = self._select_device(
            self.settings.device,
            cuda_available=self.cuda_available,
            allow_cpu_fallback=self.settings.allow_cpu_fallback,
        )
        torch.set_num_threads(self.settings.cpu_threads or min(6, os.cpu_count() or 2))
        source = str(self.settings.auto_avsr_root)
        if source not in sys.path:
            sys.path.insert(0, source)
        from espnet.nets.pytorch_backend.e2e_asr_conformer import E2E
        from espnet.nets.batch_beam_search import BatchBeamSearch
        from .incremental_decoder import IncrementalDecoderScorer
        from .cpu_ctc_prefix import CpuCTCPrefixScorer

        entries = {}
        for line in self.settings.spm_units_path.read_text(encoding="utf8").splitlines():
            token, identifier = line.rsplit(maxsplit=1)
            entries[int(identifier)] = token
        if set(entries) != set(range(1, len(entries) + 1)):
            raise ValueError("Vocabulary indices must be contiguous")
        self.tokens = ["<blank>"] + [entries[i] for i in sorted(entries)] + ["<eos>"]
        self._spm = sentencepiece.SentencePieceProcessor(
            model_file=str(self.settings.spm_model_path)
        )
        if self.tokens[1:-1] != [
            self._spm.id_to_piece(i) for i in range(self._spm.get_piece_size())
        ]:
            raise ValueError("Checkpoint units must match SentencePiece token order")
        model = E2E(len(self.tokens), "video", ctc_weight=self.settings.ctc_weight)
        payload = torch.load(
            self.settings.checkpoint_path, map_location="cpu", weights_only=True, mmap=True
        )
        state = payload.get("model", payload.get("state_dict", payload))
        if all(k.startswith("model.") for k in state):
            state = {k[6:]: v for k, v in state.items()}
        model.load_state_dict(state, strict=True)
        self.checkpoint_identity = payload.get("identity", {})
        del state, payload
        gc.collect()
        use_half = device.startswith("cuda") and self.settings.precision in ("float16", "fp16")
        model = model.half() if use_half else model.float()
        # ESPnet's CTC prefix search uses -1e10 sentinels, which overflow fp16.
        # Keep numerically sensitive autoregressive/CTC decoding in float32.
        model.decoder.float()
        model.ctc.float()
        self._model = model.to(device).eval()
        self.effective_precision = "float16_encoder_float32_decoder" if use_half else "float32"
        self.device_label = device
        self._beams = {}
        self._use_incremental = os.getenv("LIP_INCREMENTAL_DECODER", "1") == "1"
        self._cpu_ctc = os.getenv("LIP_CTC_PREFIX_DEVICE", "cpu") == "cpu"
        for size in {self.settings.beam_size, self.settings.realtime_beam_size}:
            weight = self.settings.ctc_weight
            scorers = model.scorers()
            if self._use_incremental:
                scorers["decoder"] = IncrementalDecoderScorer(model.decoder)
            if self._cpu_ctc and weight < 1:
                scorers["ctc"] = CpuCTCPrefixScorer(model.ctc, model.eos)
            self._beams[size] = BatchBeamSearch(
                beam_size=size,
                vocab_size=model.odim,
                weights={"decoder": 1 - weight, "ctc": weight},
                scorers=scorers,
                sos=model.sos,
                eos=model.eos,
                token_list=self.tokens,
                pre_beam_ratio=1.5,
                pre_beam_score_key=None if weight == 1 else "decoder",
            )
        self.loaded = True
        self.state = "ready"
        self.last_error = None
        self._load_elapsed_ms = round((time.perf_counter() - started) * 1000)

    def warmup(self):
        """Initialize inference kernels before accepting the first live session."""
        from .video_preprocessor import PreparedVideo

        self.load()
        started = time.perf_counter()
        with self._inference_lock:
            for frames in sorted(
                {
                    round(self.settings.realtime_min_seconds * self.settings.target_fps),
                    round(self.settings.realtime_window_seconds * self.settings.target_fps),
                }
            ):
                # Synthetic pixels initialize kernels; results never enter a session.
                prepared = PreparedVideo(self._torch.zeros((frames, 1, 88, 88)), frames, {})
                self._decode_native(prepared, realtime=True)
        self._warmup_ms = round((time.perf_counter() - started) * 1000)
        return self._warmup_ms

    def _text(self, ids):
        pieces = [self.tokens[int(i)] for i in ids if 0 < int(i) < len(self.tokens) - 1]
        # Joining piece strings leaks <0xNN> tokens instead of decoding UTF-8.
        return self._spm.decode(pieces).strip()

    def _decode(self, prepared, *, context_hint=None):
        return self._decode_native(prepared, realtime=False)

    def _decode_native(self, prepared, *, realtime):
        torch = self._torch
        model = self._model
        p = next(model.parameters())
        tensor = prepared.tensor.to(device=p.device, dtype=p.dtype)
        started = time.perf_counter()
        with torch.inference_mode():
            features = model.frontend(tensor.unsqueeze(0))
            encoded = model.encoder(model.proj_encoder(features), None)[0]
            encoded = encoded.float()
            if not torch.isfinite(encoded).all():
                raise RuntimeError("Nonfinite encoder states; use LIP_PRECISION=float32")
            logp = model.ctc.log_softmax(encoded).float()[0]
            if not torch.isfinite(logp).all():
                raise RuntimeError("Nonfinite CTC scores; transcription rejected")
            greedy_ids = logp.argmax(-1).unique_consecutive().tolist()
            greedy_ids = [i for i in greedy_ids if 0 < i < model.eos]
            decoder = self.settings.realtime_decoder if realtime else "beam"
            alternatives = []
            if decoder == "greedy":
                ids = greedy_ids
                alternatives = [
                    {"text": self._text(ids), "raw_score": float(logp.max(-1).values.sum())}
                ]
            else:
                size = self.settings.realtime_beam_size if realtime else self.settings.beam_size
                with cached_cross_attention(
                    model.decoder,
                    enabled=not self._use_incremental
                    and os.getenv("LIP_DECODER_CACHE", "1") == "1",
                ):
                    hypotheses = self._beams[size](encoded[0])
                ids = []
                for hyp in hypotheses[: self.settings.nbest]:
                    seq = [int(i) for i in hyp.yseq[1:] if 0 < int(i) < model.eos]
                    if not alternatives:
                        ids = seq
                    alternatives.append(
                        {"text": self._text(seq), "raw_score": float(hyp.score), "_token_ids": seq}
                    )
                for alternative in alternatives:
                    alternative.pop("_token_ids", None)
            words = align_words(
                logp.cpu().numpy(),
                ids,
                self.tokens,
                self.settings.target_fps,
                decode_pieces=self._spm.decode,
            )
        prepared.diagnostics.update(
            {
                "words": words,
                "decode": {
                    "method": decoder,
                    "beam_size": size if decoder != "greedy" else 1,
                    "ctc_weight": self.settings.ctc_weight,
                    "incremental_decoder": self._use_incremental,
                    "ctc_prefix_device": "cpu" if self._cpu_ctc else self.device_label,
                    "scores_are_calibrated_probabilities": False,
                },
                "greedy_transcript": self._text(greedy_ids),
                "context_hint_applied": False,
                "model_decode_ms": round((time.perf_counter() - started) * 1000),
            }
        )
        return EngineResult(
            transcript=alternatives[0]["text"] if alternatives else "",
            num_frames=prepared.num_frames,
            alternatives=alternatives,
            diagnostics=prepared.diagnostics,
        )

    def transcribe_frames(self, frames_rgb, *, source_fps, input_kind, context_hint=None):
        started = time.perf_counter()
        self.load()
        prepared = self._preprocessor.prepare_frames(
            frames_rgb, source_fps=source_fps, input_kind=input_kind
        )
        preprocess_ms = round((time.perf_counter() - started) * 1000)
        with self._inference_lock:
            result = self._decode_native(prepared, realtime=True)
        result.diagnostics["runtime"] = {
            "device": self.device_label,
            "precision": self.effective_precision,
            "preprocess_ms": preprocess_ms,
            "decode_ms": result.diagnostics["model_decode_ms"],
            "total_engine_ms": round((time.perf_counter() - started) * 1000),
        }
        return result
