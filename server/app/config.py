from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    api_version: str
    model_id: str
    model_backend: str
    model_load_on_startup: bool
    checkpoint_path: Path
    auto_avsr_root: Path
    spm_model_path: Path
    spm_units_path: Path
    device: str
    precision: str
    allow_cpu_fallback: bool
    cpu_threads: int
    max_upload_bytes: int
    max_frames: int
    min_frames: int
    target_fps: float
    beam_size: int
    nbest: int
    ctc_weight: float
    max_context_chars: int
    max_queued_jobs: int
    job_retention_seconds: int
    realtime_enabled: bool
    realtime_sample_fps: float
    realtime_min_seconds: float
    realtime_decode_interval_seconds: float
    realtime_window_seconds: float
    realtime_overlap_seconds: float
    realtime_max_seconds: float
    realtime_max_frame_bytes: int
    realtime_decoder: str = "beam"
    realtime_beam_size: int = 3

    def __post_init__(self) -> None:
        if self.realtime_decoder not in {"beam", "greedy"} or self.realtime_beam_size < 1:
            raise ValueError("Invalid realtime decoder configuration")
        if self.beam_size < 1:
            raise ValueError("LIP_BEAM_SIZE phải >= 1.")
        if not 1 <= self.nbest <= self.beam_size:
            raise ValueError("LIP_NBEST phải nằm trong [1, LIP_BEAM_SIZE].")
        if not 0.0 <= self.ctc_weight <= 1.0:
            raise ValueError("LIP_CTC_WEIGHT phải nằm trong [0, 1].")
        if self.max_queued_jobs < 1:
            raise ValueError("LIP_MAX_QUEUED_JOBS phải >= 1.")
        if self.job_retention_seconds < 60:
            raise ValueError("LIP_JOB_RETENTION_SECONDS phải >= 60.")
        if self.realtime_sample_fps <= 0:
            raise ValueError("LIP_REALTIME_SAMPLE_FPS phải > 0.")
        if self.realtime_min_seconds <= 0:
            raise ValueError("LIP_REALTIME_MIN_SECONDS phải > 0.")
        if self.realtime_decode_interval_seconds < 0.5:
            raise ValueError("LIP_REALTIME_DECODE_INTERVAL_SECONDS phải >= 0.5.")
        if self.realtime_window_seconds < self.realtime_min_seconds:
            raise ValueError("LIP_REALTIME_WINDOW_SECONDS phải >= LIP_REALTIME_MIN_SECONDS.")
        if not 0 <= self.realtime_overlap_seconds < self.realtime_window_seconds:
            raise ValueError("LIP_REALTIME_OVERLAP_SECONDS phải nằm trong [0, window).")
        if self.realtime_max_seconds < self.realtime_min_seconds:
            raise ValueError("LIP_REALTIME_MAX_SECONDS phải >= LIP_REALTIME_MIN_SECONDS.")
        if self.realtime_max_frame_bytes < 16 * 1024:
            raise ValueError("LIP_REALTIME_MAX_FRAME_BYTES quá nhỏ.")

    @classmethod
    def from_env(cls) -> "Settings":
        server_root = Path(__file__).resolve().parents[1]
        model_root = server_root / "vendor" / "auto_avsr"
        vocabulary_root = server_root / "assets" / "tokenizers"
        return cls(
            api_version="1.3.0",
            model_id=os.getenv(
                "LIP_MODEL_ID",
                "auto-avsr-vi-so_seed17",
            ),
            model_backend="native_avsr",
            model_load_on_startup=_as_bool(
                os.getenv("LIP_MODEL_LOAD_ON_STARTUP"),
                False,
            ),
            checkpoint_path=Path(
                os.getenv(
                    "AUTO_AVSR_CHECKPOINT",
                    str(server_root / "models" / "SO_seed17.pt"),
                )
            ),
            auto_avsr_root=Path(os.getenv("AUTO_AVSR_ROOT", str(model_root))),
            spm_model_path=Path(
                os.getenv(
                    "VSR_SPM_MODEL",
                    str(vocabulary_root / "vi.model"),
                )
            ),
            spm_units_path=Path(
                os.getenv(
                    "VSR_SPM_UNITS",
                    str(vocabulary_root / "vi_units.txt"),
                )
            ),
            device=os.getenv("LIP_DEVICE", "auto"),
            precision=os.getenv("LIP_PRECISION", "auto"),
            allow_cpu_fallback=_as_bool(
                os.getenv("LIP_ALLOW_CPU_FALLBACK"),
                True,
            ),
            cpu_threads=int(os.getenv("LIP_CPU_THREADS", "0")),
            max_upload_bytes=int(os.getenv("LIP_MAX_UPLOAD_BYTES", str(100 * 1024 * 1024))),
            max_frames=int(os.getenv("LIP_MAX_FRAMES", "1125")),
            min_frames=int(os.getenv("LIP_MIN_FRAMES", "8")),
            target_fps=float(os.getenv("LIP_TARGET_FPS", "25")),
            beam_size=int(os.getenv("LIP_BEAM_SIZE", "10")),
            nbest=int(os.getenv("LIP_NBEST", "10")),
            ctc_weight=float(os.getenv("LIP_CTC_WEIGHT", "0.1")),
            max_context_chars=int(os.getenv("LIP_MAX_CONTEXT_CHARS", "100")),
            max_queued_jobs=int(os.getenv("LIP_MAX_QUEUED_JOBS", "8")),
            job_retention_seconds=int(os.getenv("LIP_JOB_RETENTION_SECONDS", "1800")),
            realtime_enabled=_as_bool(
                os.getenv("LIP_REALTIME_ENABLED"),
                True,
            ),
            realtime_sample_fps=float(os.getenv("LIP_REALTIME_SAMPLE_FPS", "25")),
            realtime_min_seconds=float(os.getenv("LIP_REALTIME_MIN_SECONDS", "2.0")),
            realtime_decode_interval_seconds=float(
                os.getenv("LIP_REALTIME_DECODE_INTERVAL_SECONDS", "1.5")
            ),
            realtime_window_seconds=float(os.getenv("LIP_REALTIME_WINDOW_SECONDS", "6.0")),
            realtime_overlap_seconds=float(os.getenv("LIP_REALTIME_OVERLAP_SECONDS", "1.0")),
            realtime_max_seconds=float(os.getenv("LIP_REALTIME_MAX_SECONDS", "300")),
            realtime_max_frame_bytes=int(
                os.getenv("LIP_REALTIME_MAX_FRAME_BYTES", str(1024 * 1024))
            ),
            realtime_decoder=os.getenv("LIP_REALTIME_DECODER", "beam"),
            realtime_beam_size=int(os.getenv("LIP_REALTIME_BEAM_SIZE", "3")),
        )
