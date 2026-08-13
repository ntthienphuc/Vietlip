from __future__ import annotations

import re
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from typing import Any

from .video_preprocessor import VideoValidationError


def _tokens(text: str) -> list[str]:
    return re.sub(r"\s+", " ", text.strip()).split(" ") if text.strip() else []


@dataclass
class LocalAgreement:
    """Word-level stable-prefix tracking for repeated offline decoding.

    A word is marked stable only after it appears in the same position in two
    consecutive hypotheses. Stable words are never silently rewritten in the
    live UI; the final uploaded video remains the authoritative result.
    """

    previous: list[str] = field(default_factory=list)
    stable: list[str] = field(default_factory=list)

    def update(self, transcript: str) -> dict[str, str]:
        current = _tokens(transcript)
        common_count = 0
        for old, new in zip(self.previous, current):
            if old != new:
                break
            common_count += 1

        candidate = current[:common_count]
        if (
            len(candidate) >= len(self.stable)
            and candidate[: len(self.stable)] == self.stable
        ):
            self.stable = candidate

        stable_matches_current = current[: len(self.stable)] == self.stable
        provisional = current[len(self.stable) :] if stable_matches_current else current
        self.previous = current
        return {
            "transcript": " ".join(current),
            "stable_transcript": " ".join(self.stable),
            "provisional_transcript": " ".join(provisional),
        }

    def reset(self) -> None:
        self.previous.clear()
        self.stable.clear()


@dataclass
class ContinuousTranscript:
    """Stitch overlapping caption windows without rewriting committed text."""

    committed: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(self.committed)

    def preview(self, window_transcript: str) -> str:
        return " ".join(self._merge(self.committed, _tokens(window_transcript)))

    def commit(self, window_transcript: str) -> str:
        self.committed = self._merge(
            self.committed,
            _tokens(window_transcript),
        )
        return self.text

    @staticmethod
    def _merge(base: list[str], incoming: list[str]) -> list[str]:
        if not base:
            return list(incoming)
        if not incoming:
            return list(base)
        maximum = min(len(base), len(incoming), 16)
        for size in range(maximum, 1, -1):
            if base[-size:] == incoming[:size]:
                return [*base, *incoming[size:]]

        best_size = 0
        best_ratio = 0.0
        for size in range(3, maximum + 1):
            ratio = SequenceMatcher(
                None,
                base[-size:],
                incoming[:size],
                autojunk=False,
            ).ratio()
            if ratio >= 0.75 and (
                ratio > best_ratio or (ratio == best_ratio and size > best_size)
            ):
                best_size = size
                best_ratio = ratio
        return [*base, *incoming[best_size:]]


def decode_jpeg_frames(frame_payloads: list[bytes]) -> list[Any]:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "Video runtime is missing. Install requirements-cpu.txt "
            "or requirements-gpu.txt."
        ) from exc

    frames_rgb: list[Any] = []
    for payload in frame_payloads:
        encoded = np.frombuffer(payload, dtype=np.uint8)
        frame_bgr = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if frame_bgr is None:
            continue
        frames_rgb.append(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    if not frames_rgb:
        raise VideoValidationError(
            "invalid_realtime_frame",
            "Không giải mã được khung hình trực tiếp.",
        )
    return frames_rgb
