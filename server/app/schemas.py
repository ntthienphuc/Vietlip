from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Alternative(BaseModel):
    text: str
    raw_score: Optional[float] = None


class TranscriptionResponse(BaseModel):
    request_id: str
    transcript: str
    status: Literal["review_required"] = "review_required"
    model_id: str
    elapsed_ms: int
    num_frames: int
    created_at: datetime
    alternatives: list[Alternative] = Field(default_factory=list)
    processing_mode: Literal["visual_only"] = "visual_only"
    # Reserved response fields keep older clients able to parse visual results.
    assisted_transcript: Optional[str] = None
    consensus_transcript: Optional[str] = None
    risk_notice: Optional[str] = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    service: str = "lip-reader-api"
    app_name: str = "VietLip"
    app_version: str = "1.7.0"
    api_version: str
    status: Literal["ok", "degraded"]
    model_state: str
    model_loaded: bool
    cuda_available: bool
    device: str
    requested_device: str
    precision: str
    model_id: str
    last_error: Optional[str] = None
    queued_jobs: int = 0
    active_job: bool = False
    job_capacity: int = 0
    realtime_available: bool = False
    realtime_mode: Optional[str] = None
    realtime_max_seconds: Optional[float] = None


class JobAccepted(BaseModel):
    job_id: str
    request_id: str
    status: Literal["queued"] = "queued"
    queue_position: int
    poll_after_ms: int = 800
    created_at: datetime


class JobStatus(BaseModel):
    job_id: str
    request_id: str
    status: Literal[
        "queued",
        "processing",
        "completed",
        "failed",
        "cancelled",
    ]
    queue_position: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[TranscriptionResponse] = None
    error: Optional["ErrorDetail"] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None
