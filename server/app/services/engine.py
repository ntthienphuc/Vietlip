from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class EngineResult:
    transcript: str
    num_frames: int
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


class InferenceEngine(Protocol):
    model_id: str
    state: str
    loaded: bool
    cuda_available: bool
    device_label: str
    effective_precision: str
    last_error: str | None

    def load(self) -> None: ...

    def transcribe(
        self,
        video_path: Path,
        *,
        input_kind: str,
        context_hint: str | None,
    ) -> EngineResult: ...

    def transcribe_frames(
        self,
        frames_rgb: list[Any],
        *,
        source_fps: float,
        input_kind: str,
        context_hint: str | None,
    ) -> EngineResult: ...


class MockEngine:
    """Small deterministic engine used only by contract tests and demos."""

    model_id = "mock-contract-engine"
    state = "ready"
    loaded = True
    cuda_available = False
    device_label = "cpu-test"
    effective_precision = "float32"
    last_error = None

    def load(self) -> None:
        return None

    def transcribe(
        self,
        video_path: Path,
        *,
        input_kind: str,
        context_hint: str | None,
    ) -> EngineResult:
        if not video_path.is_file():
            raise FileNotFoundError(video_path)
        return EngineResult(
            transcript="xin chào",
            num_frames=25,
            alternatives=[
                {"text": "xin chào", "raw_score": -1.25},
                {"text": "xin chao", "raw_score": -1.91},
            ],
            diagnostics={
                "input_kind": input_kind,
                "quality": {"face_detection_ratio": 1.0},
                "context_hint_applied": False,
                "warnings": [
                    "Kết quả cần được người dùng kiểm tra trước khi sử dụng."
                ],
            },
        )

    def transcribe_frames(
        self,
        frames_rgb: list[Any],
        *,
        source_fps: float,
        input_kind: str,
        context_hint: str | None,
    ) -> EngineResult:
        return EngineResult(
            transcript="xin chào",
            num_frames=len(frames_rgb),
            alternatives=[
                {"text": "xin chào", "raw_score": -1.25},
                {"text": "xin chao", "raw_score": -1.91},
            ],
            diagnostics={
                "input_kind": input_kind,
                "source_fps": source_fps,
                "streaming_preview": True,
                "context_hint_applied": False,
                "warnings": [
                    "Phụ đề trực tiếp cần được người dùng kiểm tra trước khi sử dụng."
                ],
            },
        )
