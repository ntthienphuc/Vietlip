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
