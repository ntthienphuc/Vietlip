"""Opt-in experimental Vietnamese phoneme rescoring, without a second encoder."""

from __future__ import annotations
import hashlib
from pathlib import Path
import time


class PhonemeRescorer:
    def __init__(self, head_path, dependency_path, checkpoint_path, device, weight=1.0):
        import torch
        from experiments.phoneme_probe.codec import VietnamesePhones
        from experiments.phoneme_probe.model import PhonemeHead

        self.torch = torch
        payload = torch.load(head_path, map_location="cpu", weights_only=True)
        self.head_sha256 = hashlib.sha256(Path(head_path).read_bytes()).hexdigest()
        expected = payload["feature_identity"]["checkpoint_sha256"]
        actual = hashlib.sha256(Path(checkpoint_path).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("Phoneme head does not match the visual checkpoint")
        if not 0 <= weight <= 1:
            raise ValueError("Experimental phoneme weight must be in [0, 1]")
        self.weight = weight
        self.codec = VietnamesePhones(Path(dependency_path), dialect="n")
        self.head = PhonemeHead(**payload["config"]).to(device).eval()
        self.head.requires_grad_(False)
        self.head.load_state_dict(payload["state_dict"], strict=True)
        self.ids = {s: i for i, s in enumerate(payload["segmental_tokens"])}
        self.loss = torch.nn.CTCLoss(reduction="sum", zero_infinity=False)

    def rank(self, encoded, candidates):
        from experiments.phoneme_probe.codec import UnsupportedSyllable, ctc_min_frames

        tick = time.perf_counter()
        targets = []
        for candidate in candidates:
            try:
                phones = self.codec.encode(candidate["text"])
                target = [self.ids[p] for p in phones]
            except (UnsupportedSyllable, KeyError):
                return candidates, dict(applied=False, reason="unsupported_candidate_pronunciation")
            if not target or ctc_min_frames(target) > len(encoded):
                return candidates, dict(applied=False, reason="invalid_ctc_length")
            targets.append(target)
        if len(candidates) < 2 or self.weight == 0:
            return candidates, dict(applied=False, reason="no_alternative")
        torch = self.torch
        with torch.inference_mode():
            logits, _ = self.head(encoded.float().unsqueeze(0))
            logp = logits[0].log_softmax(-1)
            scores = []
            for target in targets:
                loss = self.loss(
                    logp[:, None, :],
                    torch.tensor(target, device=encoded.device),
                    torch.tensor([len(encoded)]),
                    torch.tensor([len(target)]),
                )
                if not torch.isfinite(loss):
                    return candidates, dict(applied=False, reason="nonfinite_phoneme_score")
                scores.append(-float(loss))
        ranked = [
            dict(row, phoneme_ctc_score=score, rank_score=row["raw_score"] + self.weight * score)
            for row, score in zip(candidates, scores)
        ]
        ranked.sort(key=lambda row: row["rank_score"], reverse=True)
        return ranked, dict(
            applied=True,
            weight=self.weight,
            changed=ranked[0]["text"] != candidates[0]["text"],
            elapsed_ms=round((time.perf_counter() - tick) * 1000, 3),
            scores_are_calibrated_probabilities=False,
        )
