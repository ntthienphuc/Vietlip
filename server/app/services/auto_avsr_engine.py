from __future__ import annotations

import gc
import math
import os
import sys
import time
from argparse import Namespace
from pathlib import Path
from threading import Lock
from typing import Any

from ..config import Settings
from .engine import EngineResult
from .video_preprocessor import VideoPreprocessor


class AutoAvsrEngine:
    """CUDA-preferred, CPU-capable adapter for frozen Vietnamese Auto-AVSR."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_id = settings.model_id
        self.state = "not_loaded"
        self.loaded = False
        self.cuda_available = False
        self.device_label = settings.device
        self.effective_precision = settings.precision
        self.last_error: str | None = None
        self._load_elapsed_ms: int | None = None
        self._model: Any = None
        self._torch: Any = None
        self._load_lock = Lock()
        self._inference_lock = Lock()
        self._preprocessor = VideoPreprocessor(
            auto_avsr_root=settings.auto_avsr_root,
            target_fps=settings.target_fps,
            min_frames=settings.min_frames,
            max_frames=settings.max_frames,
        )

    def load(self) -> None:
        if self.loaded:
            return
        with self._load_lock:
            if self.loaded:
                return
            self.state = "loading"
            try:
                self._load_impl()
            except Exception as exc:
                self.state = "error"
                self.last_error = f"{type(exc).__name__}: {exc}"
                raise

    def _load_impl(self) -> None:
        import torch

        load_started = time.perf_counter()
        self._torch = torch
        self.cuda_available = bool(torch.cuda.is_available())
        selected_device = self._select_device(
            self.settings.device,
            cuda_available=self.cuda_available,
            allow_cpu_fallback=self.settings.allow_cpu_fallback,
        )
        if selected_device == "cpu":
            thread_count = self.settings.cpu_threads
            if thread_count <= 0:
                thread_count = max(1, min((os.cpu_count() or 2) - 1, 12))
            torch.set_num_threads(thread_count)
        for path, label in (
            (self.settings.checkpoint_path, "checkpoint"),
            (self.settings.auto_avsr_root, "Auto-AVSR source"),
            (self.settings.spm_model_path, "SentencePiece model"),
            (self.settings.spm_units_path, "SentencePiece units"),
        ):
            if not path.exists():
                raise FileNotFoundError(f"Missing {label}: {path.name}")

        os.environ["VSR_SPM_MODEL"] = str(self.settings.spm_model_path)
        os.environ["VSR_SPM_UNITS"] = str(self.settings.spm_units_path)
        source_root = str(self.settings.auto_avsr_root)
        if source_root not in sys.path:
            sys.path.insert(0, source_root)

        from lightning import ModelModule

        args = self._model_args()
        model = ModelModule(args)
        load_options = {"map_location": "cpu"}
        try:
            checkpoint = torch.load(
                self.settings.checkpoint_path,
                weights_only=False,
                mmap=True,
                **load_options,
            )
        except TypeError:
            checkpoint = torch.load(
                self.settings.checkpoint_path,
                **load_options,
            )
        state_dict = checkpoint.get("state_dict", checkpoint)
        model.load_state_dict(state_dict, strict=True)
        del checkpoint
        del state_dict
        gc.collect()

        device = torch.device(selected_device)
        requested_precision = self.settings.precision.lower()
        use_half = device.type == "cuda" and requested_precision in {
            "auto",
            "float16",
            "fp16",
            "half",
        }
        if use_half:
            model = model.half()
            self.effective_precision = "float16"
        else:
            model = model.float()
            self.effective_precision = "float32"
        model = model.to(device).eval()
        model.on_test_epoch_start()
        self._model = model
        self.device_label = str(device)
        self.loaded = True
        self.state = "ready"
        self.last_error = None
        self._load_elapsed_ms = round((time.perf_counter() - load_started) * 1000)

    @staticmethod
    def _select_device(
        requested: str,
        *,
        cuda_available: bool,
        allow_cpu_fallback: bool,
    ) -> str:
        normalized = requested.strip().lower()
        if normalized == "auto":
            return "cuda" if cuda_available else "cpu"
        if normalized == "cpu":
            return "cpu"
        if normalized.startswith("cuda"):
            if cuda_available:
                return normalized
            if allow_cpu_fallback:
                return "cpu"
            raise RuntimeError(
                "CUDA không khả dụng và LIP_ALLOW_CPU_FALLBACK=false."
            )
        raise ValueError("LIP_DEVICE phải là auto, cpu hoặc cuda[:index].")

    def _model_args(self) -> Namespace:
        return Namespace(
            modality="video",
            ctc_weight=self.settings.ctc_weight,
            beam_size=self.settings.beam_size,
            nbest=self.settings.nbest,
            length_penalty=0.0,
            lm_weight=0.0,
            word_lm_path=None,
            word_lm_sp_model=None,
            onset_weight=0.0,
            rime_weight=0.0,
            syllable_weight=0.0,
            count_weight=0.0,
            interctc_text_weight=0.0,
            interctc_toneless_weight=0.0,
            interctc_shared_weight=0.0,
            signer_adv_weight=0.0,
            signer_kd_weight=0.0,
            xbridge_self_weight=0.0,
            xbridge_cross_weight=0.0,
            mdbridge_mode="none",
            skip_text_decoding=False,
            results_path=None,
        )

    def transcribe(
        self,
        video_path: Path,
        *,
        input_kind: str,
        context_hint: str | None,
    ) -> EngineResult:
        total_started = time.perf_counter()
        self.load()
        preprocess_started = time.perf_counter()
        prepared = self._preprocessor.prepare(video_path, input_kind)
        preprocess_ms = round((time.perf_counter() - preprocess_started) * 1000)
        with self._inference_lock:
            decode_started = time.perf_counter()
            result = self._decode(prepared, context_hint=context_hint)
            decode_ms = round((time.perf_counter() - decode_started) * 1000)
        result.diagnostics["runtime"] = {
            "device": self.device_label,
            "precision": self.effective_precision,
            "cpu_threads": (
                self._torch.get_num_threads()
                if self.device_label == "cpu"
                else None
            ),
            "model_load_ms": self._load_elapsed_ms,
            "preprocess_ms": preprocess_ms,
            "decode_ms": decode_ms,
            "total_engine_ms": round(
                (time.perf_counter() - total_started) * 1000
            ),
        }
        return result

    def transcribe_frames(
        self,
        frames_rgb: list[Any],
        *,
        source_fps: float,
        input_kind: str,
        context_hint: str | None,
    ) -> EngineResult:
        total_started = time.perf_counter()
        self.load()
        preprocess_started = time.perf_counter()
        prepared = self._preprocessor.prepare_frames(
            frames_rgb,
            source_fps=source_fps,
            input_kind=input_kind,
        )
        preprocess_ms = round((time.perf_counter() - preprocess_started) * 1000)
        with self._inference_lock:
            decode_started = time.perf_counter()
            result = self._decode(prepared, context_hint=context_hint)
            decode_ms = round((time.perf_counter() - decode_started) * 1000)
        result.diagnostics["streaming_preview"] = True
        result.diagnostics["runtime"] = {
            "device": self.device_label,
            "precision": self.effective_precision,
            "preprocess_ms": preprocess_ms,
            "decode_ms": decode_ms,
            "total_engine_ms": round(
                (time.perf_counter() - total_started) * 1000
            ),
        }
        return result

    def _decode(self, prepared, *, context_hint: str | None) -> EngineResult:
        torch = self._torch
        model = self._model
        device = next(model.parameters()).device
        sample = prepared.tensor.to(device)
        if next(model.parameters()).dtype == torch.float16:
            sample = sample.half()

        with torch.inference_mode():
            x = model.model.frontend(sample.unsqueeze(0))
            x = model.model.proj_encoder(x)
            encoded = model._encode_for_decode(x).squeeze(0)
            hypotheses = model.beam_search(encoded)
            selected = [
                hypothesis.asdict()
                for hypothesis in hypotheses[
                    : min(len(hypotheses), self.settings.nbest)
                ]
            ]
            log_prob = model.model.ctc.log_softmax(encoded.unsqueeze(0)).squeeze(0)

        alternatives = []
        for hypothesis in selected:
            token_ids = torch.tensor(
                [int(value) for value in hypothesis["yseq"][1:]]
            )
            text = (
                model.text_transform.post_process(token_ids)
                .replace("<eos>", "")
                .strip()
            )
            alternatives.append(
                {
                    "text": text,
                    "raw_score": float(hypothesis["score"]),
                }
            )
        transcript = alternatives[0]["text"] if alternatives else ""
        raw_scores = [item["raw_score"] for item in alternatives]
        decode_diagnostics = {
            "beam_size": self.settings.beam_size,
            "ctc_weight": self.settings.ctc_weight,
            "nbest_count": len(alternatives),
            "top1_top2_raw_margin": (
                round(raw_scores[0] - raw_scores[1], 6)
                if len(raw_scores) > 1
                else None
            ),
            "nbest_relative_entropy": self._relative_entropy(raw_scores),
            "scores_are_calibrated_probabilities": False,
        }
        prepared.diagnostics.update(
            {
                "decode": decode_diagnostics,
                "context_hint_provided": bool(context_hint),
                "context_hint_applied": False,
                "scientific_status": "review_required",
            }
        )
        prepared.diagnostics.setdefault("warnings", []).append(
            "Độ tin cậy decode chưa được hiệu chuẩn thành xác suất đúng."
        )
        return EngineResult(
            transcript=transcript,
            num_frames=prepared.num_frames,
            alternatives=alternatives,
            diagnostics=prepared.diagnostics,
        )

    @staticmethod
    def _relative_entropy(scores: list[float]) -> float | None:
        if len(scores) < 2:
            return None
        maximum = max(scores)
        weights = [math.exp(value - maximum) for value in scores]
        total = sum(weights)
        probabilities = [value / total for value in weights]
        entropy = -sum(
            probability * math.log(max(probability, 1e-12))
            for probability in probabilities
        )
        return round(entropy / math.log(len(probabilities)), 6)
