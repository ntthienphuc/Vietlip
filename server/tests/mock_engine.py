"""Deterministic visual inference fixture for API and streaming tests."""

from pathlib import Path
from typing import Any

from app.services.engine import EngineResult


class MockEngine:
    """Exercise live and upload endpoints without loading the model."""

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
                "warnings": ["Kết quả cần được người dùng kiểm tra trước khi sử dụng."],
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
                "warnings": ["Phụ đề trực tiếp cần được người dùng kiểm tra trước khi sử dụng."],
            },
        )
