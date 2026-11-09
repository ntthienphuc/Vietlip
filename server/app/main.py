from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .schemas import (
    ErrorDetail,
    HealthResponse,
    JobAccepted,
    JobStatus,
    TranscriptionResponse,
)
from .services.auto_avsr_engine import AutoAvsrEngine
from .services.native_engine import NativeAvsrEngine
from .services.startup import prepare_engine
from .services.streaming_session import run_stream
from .services.engine import InferenceEngine
from .services.llm_postprocessor import (
    LlmPostprocessor,
    create_llm_postprocessor,
)
from .services.nbest_consensus import summarize_nbest
from .services.realtime import (
    ContinuousTranscript,
    LocalAgreement,
    decode_jpeg_frames,
)
from .services.video_preprocessor import VideoValidationError

logger = logging.getLogger(__name__)


def create_app(
    *,
    settings: Optional[Settings] = None,
    engine: Optional[InferenceEngine] = None,
    llm: Optional[LlmPostprocessor] = None,
) -> FastAPI:
    config = settings or Settings.from_env()
    inference_engine = engine or (
        NativeAvsrEngine(config)
        if config.model_backend == "native_avsr"
        else AutoAvsrEngine(config)
    )
    llm_processor = llm or create_llm_postprocessor(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = config
        app.state.engine = inference_engine
        app.state.inference_semaphore = asyncio.Semaphore(1)
        app.state.llm = llm_processor
        app.state.jobs: dict[str, dict[str, Any]] = {}
        app.state.job_queue = asyncio.Queue(maxsize=config.max_queued_jobs)
        app.state.job_worker_task = asyncio.create_task(_job_worker(app))
        if config.model_load_on_startup:
            try:
                await asyncio.to_thread(
                    prepare_engine,
                    inference_engine,
                    warmup=os.getenv("LIP_STARTUP_WARMUP", "0") == "1",
                )
            except Exception:
                # Health reports the real model error while the API remains
                # available for diagnosis.
                logger.exception("Model startup preparation failed")
        try:
            yield
        finally:
            app.state.job_worker_task.cancel()
            await asyncio.gather(
                app.state.job_worker_task,
                return_exceptions=True,
            )
            for job in app.state.jobs.values():
                path = job.get("temp_path")
                if isinstance(path, Path):
                    path.unlink(missing_ok=True)

    app = FastAPI(
        title="Vietnamese Lip Reader API",
        version=config.api_version,
        description=(
            "CPU-capable, GPU-preferred Auto-AVSR review API. "
            "Every transcript requires human review."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(VideoValidationError)
    async def video_error_handler(
        request: Request,
        exc: VideoValidationError,
    ):
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "Video rejected: code=%s request_id=%s path=%s message=%s",
            exc.code,
            request_id,
            request.url.path,
            str(exc),
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": ErrorDetail(
                    code=exc.code,
                    message=str(exc),
                    request_id=request_id,
                ).model_dump()
            },
        )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = (request.headers.get("x-request-id") or uuid.uuid4().hex)[:128]
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        response.headers["cache-control"] = "no-store"
        return response

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        current_engine = app.state.engine
        try:
            llm_available = await app.state.llm.healthcheck()
        except Exception:
            llm_available = False
        return HealthResponse(
            api_version=config.api_version,
            status="degraded" if current_engine.state == "error" else "ok",
            model_state=current_engine.state,
            model_loaded=current_engine.loaded,
            cuda_available=current_engine.cuda_available,
            device=current_engine.device_label,
            requested_device=config.device,
            precision=current_engine.effective_precision,
            model_id=current_engine.model_id,
            llm_available=llm_available,
            llm_model=app.state.llm.model_label,
            last_error=current_engine.last_error,
            queued_jobs=app.state.job_queue.qsize(),
            active_job=any(item.get("status") == "processing" for item in app.state.jobs.values()),
            job_capacity=config.max_queued_jobs,
            realtime_available=config.realtime_enabled,
            realtime_mode=("continuous_visual_captions" if config.realtime_enabled else None),
            realtime_max_seconds=(config.realtime_max_seconds if config.realtime_enabled else None),
        )

    @app.websocket("/v1/realtime")
    async def realtime_preview(websocket: WebSocket) -> None:
        """Continuous visual captions from overlapping offline-model windows."""
        await websocket.accept()
        if not config.realtime_enabled:
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "realtime_disabled",
                    "message": "Phụ đề trực tiếp chưa được bật trên server.",
                }
            )
            await websocket.close(code=1013)
            return

        session_id = uuid.uuid4().hex
        frame_payloads: list[bytes] = []
        agreement = LocalAgreement()
        transcript = ContinuousTranscript()
        frame_event = asyncio.Event()
        send_lock = asyncio.Lock()
        worker_task: asyncio.Task[None] | None = None
        last_decode_started = 0.0
        last_partial_end = 0
        segment_start = 0
        segment_index = 0
        stop_requested = False
        abort_requested = False
        last_window_start = -1
        last_window_end = -1
        last_window_text = ""
        last_notice_key = ""
        last_notice_sent_at = 0.0
        received_frames = 0
        window_frames = max(
            1,
            int(config.realtime_sample_fps * config.realtime_window_seconds),
        )
        overlap_frames = max(
            0,
            int(config.realtime_sample_fps * config.realtime_overlap_seconds),
        )
        hop_frames = max(1, window_frames - overlap_frames)
        max_frames = max(
            1,
            int(config.realtime_sample_fps * config.realtime_max_seconds),
        )
        min_frames = max(
            1,
            int(config.realtime_sample_fps * config.realtime_min_seconds),
        )
        limit_reported = False

        async def send_json(payload: dict[str, Any]) -> None:
            try:
                async with send_lock:
                    await websocket.send_json(payload)
            except (RuntimeError, WebSocketDisconnect):
                pass

        async def send_notice(code: str, message: str) -> None:
            """Avoid flooding a slow mobile client with repeated notices."""
            nonlocal last_notice_key, last_notice_sent_at
            now = time.monotonic()
            key = f"{code}:{message}"
            if key == last_notice_key and now - last_notice_sent_at < 8.0:
                return
            last_notice_key = key
            last_notice_sent_at = now
            await send_json(
                {
                    "type": "notice",
                    "code": code,
                    "message": message,
                }
            )

        async def prewarm_model() -> None:
            if app.state.engine.loaded:
                return
            try:
                await asyncio.to_thread(app.state.engine.load)
            except Exception as exc:
                logger.warning(
                    "Realtime model prewarm failed: session_id=%s error=%s",
                    session_id,
                    type(exc).__name__,
                )

        async def decode_snapshot(
            snapshot: list[bytes],
        ) -> tuple[str, int] | None:
            started = time.perf_counter()
            try:
                frames_rgb = await asyncio.to_thread(
                    decode_jpeg_frames,
                    snapshot,
                )
                async with app.state.inference_semaphore:
                    result = await asyncio.to_thread(
                        app.state.engine.transcribe_frames,
                        frames_rgb,
                        source_fps=config.realtime_sample_fps,
                        input_kind="raw_face",
                        context_hint=None,
                    )
                return (
                    result.transcript,
                    round((time.perf_counter() - started) * 1000),
                )
            except VideoValidationError as exc:
                await send_notice(exc.code, str(exc))
            except Exception as exc:
                logger.warning(
                    "Realtime preview failed: session_id=%s error=%s",
                    session_id,
                    type(exc).__name__,
                )
                await send_notice(
                    "caption_unavailable",
                    (
                        "Chưa tạo được phụ đề cho đoạn này. Video vẫn có thể "
                        "được xử lý đầy đủ sau khi dừng quay."
                    ),
                )
            return None

        async def caption_worker() -> None:
            nonlocal last_decode_started, last_partial_end
            nonlocal last_window_end, last_window_start, last_window_text
            nonlocal segment_index, segment_start
            while True:
                await frame_event.wait()
                frame_event.clear()
                if abort_requested:
                    return

                while True:
                    total = len(frame_payloads)
                    available = total - segment_start
                    full_segment = available >= window_frames
                    finishing = stop_requested and not full_segment

                    if full_segment:
                        snapshot_end = segment_start + window_frames
                        snapshot = list(frame_payloads[segment_start:snapshot_end])
                        kind = "segment"
                    elif finishing:
                        if available < min_frames:
                            await send_json(
                                {
                                    "type": "session_final",
                                    "session_id": session_id,
                                    "transcript": transcript.text,
                                    "segment_count": segment_index,
                                    "review_required": True,
                                }
                            )
                            return
                        snapshot_end = total
                        snapshot = list(frame_payloads[segment_start:total])
                        kind = "final"
                    else:
                        now = time.monotonic()
                        if (
                            available < min_frames
                            or total <= last_partial_end
                            or now - last_decode_started < config.realtime_decode_interval_seconds
                        ):
                            break
                        snapshot_end = total
                        snapshot = list(frame_payloads[segment_start:total])
                        kind = "partial"

                    if last_window_start == segment_start and last_window_end == snapshot_end:
                        decoded = (last_window_text, 0)
                    else:
                        last_decode_started = time.monotonic()
                        decoded = await decode_snapshot(snapshot)
                    if abort_requested:
                        return

                    if decoded is None:
                        if kind == "segment":
                            await send_json(
                                {
                                    "type": "segment_skipped",
                                    "session_id": session_id,
                                    "segment_index": segment_index,
                                    "message": (
                                        "Một đoạn chưa đủ rõ để tạo phụ đề; "
                                        "phiên trực tiếp vẫn tiếp tục."
                                    ),
                                }
                            )
                            segment_start += hop_frames
                            if segment_start > 0:
                                del frame_payloads[:segment_start]
                                segment_start = 0
                                last_window_start = -1
                                last_window_end = -1
                                last_window_text = ""
                                last_partial_end = 0
                            segment_index += 1
                            agreement.reset()
                            continue
                        if kind == "final":
                            await send_json(
                                {
                                    "type": "session_final",
                                    "session_id": session_id,
                                    "transcript": transcript.text,
                                    "segment_count": segment_index,
                                    "review_required": True,
                                }
                            )
                            return
                        last_partial_end = snapshot_end
                        break

                    window_text, elapsed_ms = decoded
                    last_window_start = segment_start
                    last_window_end = snapshot_end
                    last_window_text = window_text

                    if kind == "partial":
                        local = agreement.update(window_text)
                        last_partial_end = snapshot_end
                        await send_json(
                            {
                                "type": "partial",
                                "session_id": session_id,
                                "transcript": transcript.preview(window_text),
                                "committed_transcript": transcript.text,
                                "window_transcript": local["transcript"],
                                "stable_transcript": transcript.preview(local["stable_transcript"]),
                                "provisional_transcript": local["provisional_transcript"],
                                "frame_count": received_frames,
                                "source_seconds": round(
                                    received_frames / config.realtime_sample_fps,
                                    2,
                                ),
                                "elapsed_ms": elapsed_ms,
                                "device": app.state.engine.device_label,
                                "review_required": True,
                            }
                        )
                        break

                    combined = transcript.commit(window_text)
                    segment_index += 1
                    await send_json(
                        {
                            "type": "segment_final",
                            "session_id": session_id,
                            "transcript": combined,
                            "segment_transcript": window_text,
                            "segment_index": segment_index - 1,
                            "elapsed_ms": elapsed_ms,
                            "review_required": True,
                        }
                    )
                    if kind == "final":
                        await send_json(
                            {
                                "type": "session_final",
                                "session_id": session_id,
                                "transcript": combined,
                                "segment_count": segment_index,
                                "review_required": True,
                            }
                        )
                        return

                    segment_start += hop_frames
                    if segment_start > 0:
                        del frame_payloads[:segment_start]
                        segment_start = 0
                        last_window_start = -1
                        last_window_end = -1
                        last_window_text = ""
                    agreement.reset()
                    last_partial_end = 0

        try:
            first = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=10,
            )
            if first.get("type") == "start" and first.get("protocol") == 2:
                await run_stream(
                    websocket, config, app.state.engine, app.state.inference_semaphore, first
                )
                return
            if first.get("type") != "start":
                await send_json(
                    {
                        "type": "error",
                        "code": "start_required",
                        "message": "Cần khởi tạo phiên trực tiếp trước khi gửi hình.",
                    }
                )
                await websocket.close(code=1008)
                return
            await send_json(
                {
                    "type": "ready",
                    "session_id": session_id,
                    "sample_fps": config.realtime_sample_fps,
                    "min_seconds": config.realtime_min_seconds,
                    "decode_interval_seconds": (config.realtime_decode_interval_seconds),
                    "window_seconds": config.realtime_window_seconds,
                    "overlap_seconds": config.realtime_overlap_seconds,
                    "max_seconds": config.realtime_max_seconds,
                    "mode": "continuous_visual_captions",
                }
            )
            asyncio.create_task(prewarm_model())
            worker_task = asyncio.create_task(caption_worker())

            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                payload = message.get("bytes")
                if payload is not None:
                    if len(payload) > config.realtime_max_frame_bytes:
                        await send_json(
                            {
                                "type": "notice",
                                "code": "frame_too_large",
                                "message": "Một khung hình trực tiếp quá lớn và đã được bỏ qua.",
                            }
                        )
                        continue
                    if received_frames >= max_frames:
                        if not limit_reported:
                            limit_reported = True
                            await send_json(
                                {
                                    "type": "limit",
                                    "message": (
                                        "Đã đạt thời lượng phụ đề trực tiếp; "
                                        "video vẫn tiếp tục được lưu bình thường."
                                    ),
                                }
                            )
                        continue
                    frame_payloads.append(bytes(payload))
                    received_frames += 1
                    frame_event.set()
                    continue

                text_payload = message.get("text")
                if text_payload:
                    try:
                        import json

                        control = json.loads(text_payload)
                    except (TypeError, ValueError):
                        continue
                    if control.get("type") == "stop":
                        stop_requested = True
                        frame_event.set()
                        if worker_task is not None:
                            await worker_task
                        break
        except (asyncio.TimeoutError, WebSocketDisconnect):
            abort_requested = True
            frame_event.set()
        finally:
            if not stop_requested:
                abort_requested = True
                frame_event.set()
            if worker_task is not None and not worker_task.done():
                try:
                    await asyncio.wait_for(
                        asyncio.shield(worker_task),
                        timeout=2,
                    )
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    # Inference running in a worker thread cannot be cancelled
                    # safely. Let it finish while the socket closes; the global
                    # semaphore still prevents concurrent access to the model.
                    pass
            try:
                await websocket.close()
            except RuntimeError:
                pass

    async def _process_saved_video(
        temp_path: Path,
        *,
        resolved_request_id: str,
        input_kind: str,
        context_hint: Optional[str],
        mode: str,
        started: float,
    ) -> TranscriptionResponse:
        async with app.state.inference_semaphore:
            result = await asyncio.to_thread(
                app.state.engine.transcribe,
                temp_path,
                input_kind=input_kind,
                context_hint=context_hint,
            )

        consensus = summarize_nbest(result.alternatives)
        if consensus is not None:
            result.diagnostics["nbest_consensus"] = consensus

        llm_result = None
        if mode != "visual_only":
            try:
                llm_result = await app.state.llm.process(
                    mode=mode,
                    visual_transcript=result.transcript,
                    alternatives=result.alternatives,
                    context_hint=context_hint or "",
                )
                result.diagnostics["llm"] = llm_result.diagnostics
            except Exception as exc:
                logger.warning(
                    "LLM post-processing failed for request_id=%s: %s",
                    resolved_request_id,
                    type(exc).__name__,
                )
                result.diagnostics["llm"] = {
                    "status": "error",
                    "message": (
                        "Không gọi được LLM; bản thuần chuyển động môi vẫn được giữ nguyên."
                    ),
                }

        return TranscriptionResponse(
            request_id=resolved_request_id,
            transcript=result.transcript,
            status="review_required",
            model_id=app.state.engine.model_id,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            num_frames=result.num_frames,
            created_at=datetime.now(timezone.utc),
            alternatives=result.alternatives,
            processing_mode=mode,
            assisted_transcript=(llm_result.assisted_transcript if llm_result else None),
            consensus_transcript=(
                str(consensus["candidate_text"]) if consensus is not None else None
            ),
            risk_notice=(
                "LLM chỉ chọn trong N-best; vẫn có thể chọn sai."
                if mode == "context_select"
                else (
                    "Bản diễn giải từ LLM có thể chứa chi tiết không thể xác nhận "
                    "chỉ bằng chuyển động môi; hãy đối chiếu với kết quả thị giác."
                    if mode == "llm_assist"
                    else None
                )
            ),
            diagnostics=result.diagnostics,
        )

    def _validate_submission(
        *,
        filename: str,
        resolved_request_id: str,
        context_hint: Optional[str],
        mode: str,
        accept_llm_risk: bool,
    ) -> None:
        if context_hint and len(context_hint) > config.max_context_chars:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "context_too_long",
                    "message": (f"Ngữ cảnh tối đa {config.max_context_chars} ký tự."),
                    "request_id": resolved_request_id,
                },
            )
        allowed_modes = {"visual_only", "context_select", "llm_assist"}
        if mode not in allowed_modes:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_mode",
                    "message": "Chế độ xử lý không được hỗ trợ.",
                    "request_id": resolved_request_id,
                },
            )
        if mode != "visual_only":
            if not accept_llm_risk:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "llm_risk_not_accepted",
                        "message": ("Vui lòng xác nhận bạn sẽ kiểm tra kết quả hỗ trợ từ LLM."),
                        "request_id": resolved_request_id,
                    },
                )
            if not context_hint or not context_hint.strip():
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "context_required",
                        "message": ("Chế độ có LLM cần một chủ đề hoặc ngữ cảnh do bạn nhập."),
                        "request_id": resolved_request_id,
                    },
                )
        if not filename.lower().endswith(".mp4"):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "unsupported_media_type",
                    "message": "Ứng dụng hiện chỉ nhận video MP4.",
                    "request_id": resolved_request_id,
                },
            )

    @app.post(
        "/v1/transcriptions",
        response_model=TranscriptionResponse,
        responses={422: {"description": "Invalid or unusable MP4"}},
    )
    async def create_transcription(
        request: Request,
        video: UploadFile = File(...),
        request_id: Optional[str] = Form(None),
        input_kind: str = Form("auto"),
        context_hint: Optional[str] = Form(None),
        mode: str = Form("visual_only"),
        accept_llm_risk: bool = Form(False),
    ) -> TranscriptionResponse:
        resolved_request_id = (
            request_id.strip()[:128]
            if request_id and request_id.strip()
            else request.state.request_id
        )
        _validate_submission(
            filename=video.filename or "",
            resolved_request_id=resolved_request_id,
            context_hint=context_hint,
            mode=mode,
            accept_llm_risk=accept_llm_risk,
        )

        temp_path: Path | None = None
        started = time.perf_counter()
        try:
            temp_path = await _save_upload(
                video,
                max_bytes=config.max_upload_bytes,
            )
            return await _process_saved_video(
                temp_path,
                resolved_request_id=resolved_request_id,
                input_kind=input_kind,
                context_hint=context_hint,
                mode=mode,
                started=started,
            )
        except VideoValidationError:
            raise
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Inference failed for request_id=%s", resolved_request_id)
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "model_unavailable",
                    "message": (
                        "Mô hình chưa sẵn sàng để suy luận. "
                        "Hãy kiểm tra trạng thái máy chủ hoặc thử lại sau."
                    ),
                    "request_id": resolved_request_id,
                },
            ) from exc
        finally:
            await video.close()
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

        raise AssertionError("unreachable")

    def _job_status_payload(job: dict[str, Any]) -> JobStatus:
        return JobStatus(
            job_id=job["job_id"],
            request_id=job["request_id"],
            status=job["status"],
            queue_position=job.get("queue_position"),
            created_at=job["created_at"],
            started_at=job.get("started_at"),
            completed_at=job.get("completed_at"),
            result=job.get("result"),
            error=job.get("error"),
        )

    def _cleanup_expired_jobs() -> None:
        now = datetime.now(timezone.utc)
        expired = []
        for job_id, job in app.state.jobs.items():
            completed_at = job.get("completed_at")
            if completed_at is None:
                continue
            age = (now - completed_at).total_seconds()
            if age > config.job_retention_seconds:
                expired.append(job_id)
        for job_id in expired:
            app.state.jobs.pop(job_id, None)

    async def _job_worker(current_app: FastAPI) -> None:
        while True:
            job_id = await current_app.state.job_queue.get()
            job = current_app.state.jobs.get(job_id)
            try:
                if job is None or job.get("status") == "cancelled":
                    continue
                job["status"] = "processing"
                job["queue_position"] = None
                job["started_at"] = datetime.now(timezone.utc)
                try:
                    result = await _process_saved_video(
                        job["temp_path"],
                        resolved_request_id=job["request_id"],
                        input_kind=job["input_kind"],
                        context_hint=job["context_hint"],
                        mode=job["mode"],
                        started=time.perf_counter(),
                    )
                    if job.get("cancel_requested"):
                        job["status"] = "cancelled"
                    else:
                        job["status"] = "completed"
                        job["result"] = result
                except VideoValidationError as exc:
                    job["status"] = "failed"
                    job["error"] = ErrorDetail(
                        code=exc.code,
                        message=str(exc),
                        request_id=job["request_id"],
                    )
                except HTTPException as exc:
                    detail = exc.detail if isinstance(exc.detail, dict) else {}
                    job["status"] = "failed"
                    job["error"] = ErrorDetail(
                        code=str(detail.get("code") or "request_failed"),
                        message=str(detail.get("message") or "Không thể xử lý video đã gửi."),
                        request_id=job["request_id"],
                    )
                except Exception as exc:
                    logger.exception(
                        "Queued inference failed for request_id=%s",
                        job["request_id"],
                    )
                    job["status"] = "failed"
                    job["error"] = ErrorDetail(
                        code="model_unavailable",
                        message=(
                            "Mô hình chưa sẵn sàng để suy luận. "
                            "Hãy kiểm tra trạng thái máy chủ hoặc thử lại sau."
                        ),
                        request_id=job["request_id"],
                    )
                    job["internal_error"] = type(exc).__name__
                finally:
                    job["completed_at"] = datetime.now(timezone.utc)
                    path = job.get("temp_path")
                    if isinstance(path, Path):
                        path.unlink(missing_ok=True)
                    job["temp_path"] = None
            finally:
                current_app.state.job_queue.task_done()

    @app.post("/v1/jobs", response_model=JobAccepted, status_code=202)
    async def create_job(
        request: Request,
        video: UploadFile = File(...),
        request_id: Optional[str] = Form(None),
        input_kind: str = Form("auto"),
        context_hint: Optional[str] = Form(None),
        mode: str = Form("visual_only"),
        accept_llm_risk: bool = Form(False),
    ) -> JobAccepted:
        _cleanup_expired_jobs()
        resolved_request_id = (
            request_id.strip()[:128]
            if request_id and request_id.strip()
            else request.state.request_id
        )
        _validate_submission(
            filename=video.filename or "",
            resolved_request_id=resolved_request_id,
            context_hint=context_hint,
            mode=mode,
            accept_llm_risk=accept_llm_risk,
        )
        if app.state.job_queue.full():
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "job_queue_full",
                    "message": ("Hàng đợi đang đầy. Vui lòng chờ một lượt xử lý hoàn tất."),
                    "request_id": resolved_request_id,
                },
            )

        temp_path: Path | None = None
        try:
            temp_path = await _save_upload(
                video,
                max_bytes=config.max_upload_bytes,
            )
        finally:
            await video.close()

        job_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc)
        queue_position = app.state.job_queue.qsize() + 1
        app.state.jobs[job_id] = {
            "job_id": job_id,
            "request_id": resolved_request_id,
            "status": "queued",
            "queue_position": queue_position,
            "created_at": created_at,
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "temp_path": temp_path,
            "input_kind": input_kind,
            "context_hint": context_hint,
            "mode": mode,
            "cancel_requested": False,
        }
        try:
            app.state.job_queue.put_nowait(job_id)
        except asyncio.QueueFull:
            temp_path.unlink(missing_ok=True)
            app.state.jobs.pop(job_id, None)
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "job_queue_full",
                    "message": "Hàng đợi vừa đầy. Vui lòng gửi lại sau.",
                    "request_id": resolved_request_id,
                },
            )
        return JobAccepted(
            job_id=job_id,
            request_id=resolved_request_id,
            queue_position=queue_position,
            created_at=created_at,
        )

    @app.get("/v1/jobs/{job_id}", response_model=JobStatus)
    async def get_job(job_id: str) -> JobStatus:
        _cleanup_expired_jobs()
        job = app.state.jobs.get(job_id)
        if job is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "job_not_found",
                    "message": "Không tìm thấy lượt xử lý hoặc kết quả đã hết hạn.",
                },
            )
        return _job_status_payload(job)

    @app.delete("/v1/jobs/{job_id}", response_model=JobStatus)
    async def cancel_job(job_id: str) -> JobStatus:
        job = app.state.jobs.get(job_id)
        if job is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "job_not_found",
                    "message": "Không tìm thấy lượt xử lý.",
                },
            )
        if job["status"] == "queued":
            job["status"] = "cancelled"
            job["completed_at"] = datetime.now(timezone.utc)
            path = job.get("temp_path")
            if isinstance(path, Path):
                path.unlink(missing_ok=True)
            job["temp_path"] = None
        elif job["status"] == "processing":
            job["cancel_requested"] = True
        return _job_status_payload(job)

    return app


async def _save_upload(upload: UploadFile, *, max_bytes: int) -> Path:
    descriptor, raw_path = tempfile.mkstemp(prefix="lip_", suffix=".mp4")
    os.close(descriptor)
    path = Path(raw_path)
    total = 0
    header = b""
    try:
        with path.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                if not header:
                    header = chunk[:32]
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail={
                            "code": "upload_too_large",
                            "message": (f"Video vượt giới hạn {max_bytes // (1024 * 1024)} MB."),
                        },
                    )
                handle.write(chunk)
        if total < 12 or b"ftyp" not in header:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_mp4",
                    "message": "File không có header MP4 hợp lệ.",
                },
            )
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


app = create_app()
