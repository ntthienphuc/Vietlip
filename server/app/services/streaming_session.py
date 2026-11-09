"""Protocol 2: bounded live windows, explicit end-of-turn and input feedback."""

from __future__ import annotations
import asyncio
import json
import logging
import time
from fastapi import WebSocketDisconnect
from .realtime import decode_jpeg_frames
from .streaming_buffer import FrameBuffer, WordTimeline, unpack_frame
from .video_preprocessor import VideoValidationError
from .live_evidence import LiveEvidence, check_live_images

logger = logging.getLogger(__name__)


async def run_stream(websocket, config, engine, semaphore, start_message):
    buffer = FrameBuffer(
        seconds=config.realtime_window_seconds + 2,
        max_frames=int(config.target_fps * (config.realtime_window_seconds + 2) * 2),
    )
    timeline, evidence = WordTimeline(), LiveEvidence()
    event, send_lock = asyncio.Event(), asyncio.Lock()
    stopping = disconnected = False
    last_end, segment_start = -1.0, 0.0
    last_result = None
    flush_at = None
    received = 0
    started = last_frame_wall = time.monotonic()
    state = "collecting"
    input_kind = start_message.get("input_kind", "raw_face")
    rotation = start_message.get("rotation_degrees", 0)
    if (
        type(rotation) is not int
        or rotation not in {0, 90, 180, 270}
        or input_kind not in {"raw_face", "mouth_roi"}
    ):
        await websocket.close(code=1008)
        return
    if start_message.get("auto_endpoint", input_kind == "raw_face"):
        from .auto_stream import run_auto_stream

        return await run_auto_stream(websocket, config, engine, semaphore, start_message)

    async def send(payload):
        nonlocal disconnected
        if disconnected:
            return
        try:
            async with send_lock:
                await websocket.send_json(payload)
        except (WebSocketDisconnect, RuntimeError):
            disconnected = True

    def transport():
        recent = [f for f in buffer.frames if f.seconds >= buffer.last_time - 2]
        fps = (
            (len(recent) - 1) / (recent[-1].seconds - recent[0].seconds) if len(recent) > 1 else 0.0
        )
        return {
            "received_frames": received,
            "capture_fps": round(fps, 2),
            "capture_gaps": buffer.gaps,
            "buffered_frames": len(buffer.frames),
            "last_frame_age_ms": round((time.monotonic() - last_frame_wall) * 1000),
        }

    async def heartbeat():
        while not disconnected:
            await asyncio.sleep(1)
            if disconnected:
                return
            age = time.monotonic() - last_frame_wall
            status = "camera_stalled" if received and age > 2 else state
            await send(dict(type="telemetry", recognition_state=status, **transport()))

    async def complete(kind, *, incomplete=False, message=None):
        await send(
            dict(
                type=kind,
                protocol=2,
                transcript=timeline.text,
                stable_transcript=timeline.text,
                provisional_transcript="",
                incomplete=incomplete or bool(evidence.unavailable_windows or buffer.gaps),
                recognition_state="unavailable" if incomplete else "complete",
                message=message,
                model_id=config.model_id,
                review_required=True,
                evidence=evidence.payload(),
                **transport(),
            )
        )

    async def worker():
        nonlocal last_end, last_result, segment_start, flush_at, state
        while not disconnected:
            try:
                await asyncio.wait_for(
                    event.wait(), timeout=config.realtime_decode_interval_seconds
                )
            except asyncio.TimeoutError:
                pass
            event.clear()
            if disconnected:
                return
            boundary = flush_at
            final = stopping and boundary is None
            endpoint = final or boundary is not None
            snapshot, begin, end = buffer.snapshot(
                config.realtime_window_seconds,
                config.target_fps,
                after=segment_start,
                until=boundary,
            )
            kind = "session_final" if final else "segment_final" if endpoint else "partial"
            if not snapshot:
                if endpoint:
                    await complete(kind, incomplete=not bool(timeline.text))
                    if final:
                        return
                    segment_start = boundary
                    flush_at = None
                    event.set()
                continue
            if not endpoint and (
                end - begin < config.realtime_min_seconds
                or end - last_end < config.realtime_decode_interval_seconds
            ):
                continue
            if end == last_end and not endpoint:
                continue
            if endpoint and end == last_end and last_result is None:
                await complete(kind, incomplete=True)
                if final:
                    return
                segment_start = boundary
                flush_at = None
                event.set()
                continue
            elapsed = 0
            try:
                if end == last_end and last_result is not None:
                    result = last_result
                elif end == last_end:
                    raise VideoValidationError(
                        "caption_unavailable", "Đoạn cuối chưa nhận dạng được."
                    )
                else:
                    tick = time.perf_counter()
                    state = "processing"
                    async with semaphore:
                        # A video job may hold the GPU: resnapshot AFTER admission
                        # so a queued live decode processes the freshest camera data.
                        snapshot, begin, end = buffer.snapshot(
                            config.realtime_window_seconds,
                            config.target_fps,
                            after=segment_start,
                            until=boundary,
                        )
                        if not snapshot:
                            raise VideoValidationError(
                                "capture_gap", "Đã mất hình của đoạn này. Hãy nói lại."
                            )
                        frames = await asyncio.to_thread(
                            decode_jpeg_frames,
                            snapshot,
                            True,
                            rotation_degrees=rotation,
                            max_width=360 if input_kind == "raw_face" else None,
                        )
                        await asyncio.to_thread(check_live_images, frames, config.target_fps)
                        result = await asyncio.to_thread(
                            engine.transcribe_frames,
                            frames,
                            source_fps=config.target_fps,
                            input_kind=input_kind,
                            context_hint=None,
                        )
                    if not result.transcript.strip():
                        raise VideoValidationError(
                            "empty_hypothesis", "Chưa đọc được đoạn này. Hãy nhìn thẳng và nói lại."
                        )
                    elapsed = round((time.perf_counter() - tick) * 1000)
                    evidence.record(begin, end)
                    last_result = result
                last_end = end
                words = result.diagnostics.get("words", [])
                update = (
                    timeline.update(
                        words,
                        begin,
                        end,
                        final=endpoint,
                        right_context=config.realtime_overlap_seconds,
                    )
                    if words
                    else {
                        "transcript": result.transcript,
                        "stable_transcript": timeline.text,
                        "provisional_transcript": result.transcript,
                    }
                )
                state = "reading"
                await send(
                    dict(
                        update,
                        type=kind,
                        protocol=2,
                        elapsed_ms=elapsed,
                        source_seconds=round(end, 3),
                        window_start=begin,
                        window_end=end,
                        behind_live_ms=round(max(0, buffer.last_time - end) * 1000),
                        word_timing_available=bool(words),
                        window_words=words,
                        window_transcript=result.transcript,
                        device=engine.device_label,
                        model_id=config.model_id,
                        review_required=True,
                        recognition_state=state,
                        experimental_phoneme_rescoring=result.diagnostics.get(
                            "experimental_phoneme_rescoring", {"enabled": False}
                        ),
                        incomplete=bool(evidence.unavailable_windows or buffer.gaps),
                        quality=result.diagnostics.get("quality", {}),
                        evidence=evidence.payload(),
                        **transport(),
                    )
                )
            except Exception as exc:
                last_result = None
                # Repeated flush of the same failed window is not a new attempt.
                if end != last_end:
                    evidence.record(begin, end, getattr(exc, "code", "caption_unavailable"))
                last_end = end
                state = "unavailable"
                if not isinstance(exc, VideoValidationError):
                    logger.exception("Streaming decode failed")
                message = (
                    str(exc)
                    if isinstance(exc, VideoValidationError)
                    else "Chưa nhận dạng được đoạn này. Hãy thử lại."
                )
                await send(
                    dict(
                        type="notice",
                        code=getattr(exc, "code", "caption_unavailable"),
                        message=message,
                        recognition_state=state,
                        transcript=timeline.text,
                        stable_transcript=timeline.text,
                        provisional_transcript="",
                        window_start=begin,
                        window_end=end,
                        evidence=evidence.payload(),
                        **transport(),
                    )
                )
                if endpoint:
                    await complete(kind, incomplete=True, message=message)
            if final:
                return
            if boundary is not None:
                segment_start = boundary
                flush_at = None
                last_result = None
                state = "collecting"
                event.set()

    # Readiness means the model really loaded. Fail before the app starts capture.
    try:
        if not engine.loaded:
            async with semaphore:
                await asyncio.to_thread(engine.load)
    except Exception:
        logger.exception("Live model load failed")
        await send(
            {
                "type": "error",
                "code": "model_unavailable",
                "message": "Mô hình chưa sẵn sàng. Kiểm tra máy chủ rồi thử lại.",
            }
        )
        await websocket.close(code=1013)
        return
    await send(
        {
            "type": "ready",
            "protocol": 2,
            "sample_fps": config.realtime_sample_fps,
            "max_inflight_frames": 4,
            "window_seconds": config.realtime_window_seconds,
            "max_seconds": config.realtime_max_seconds,
            "supports_flush": True,
            "mode": "timestamped_sliding_window",
        }
    )
    task = asyncio.create_task(worker())
    pulse = asyncio.create_task(heartbeat())
    try:
        while not disconnected:
            message = await asyncio.wait_for(websocket.receive(), timeout=15)
            if message["type"] == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                packet = message["bytes"]
                if len(packet) > config.realtime_max_frame_bytes + 16:
                    await websocket.close(code=1009)
                    break
                try:
                    frame = unpack_frame(packet)
                    if (
                        frame.seconds > config.realtime_max_seconds
                        or time.monotonic() - started > config.realtime_max_seconds + 30
                    ):
                        stopping = True
                        event.set()
                        await task
                        break
                    buffer.add(frame)
                except ValueError as exc:
                    await send({"type": "error", "code": "invalid_frame", "message": str(exc)})
                    await websocket.close(code=1008)
                    break
                received += 1
                last_frame_wall = time.monotonic()
                await send({"type": "ack", "sequence": frame.sequence})
                event.set()
            elif message.get("text"):
                control = json.loads(message["text"])
                if control.get("type") == "stop":
                    stopping = True
                    event.set()
                    await task
                    break
                if control.get("type") == "flush" and flush_at is None:
                    flush_at = max(segment_start, buffer.last_time + 1 / config.target_fps)
                    event.set()
    except (WebSocketDisconnect, asyncio.TimeoutError, ValueError):
        pass
    finally:
        disconnected = True
        event.set()
        pulse.cancel()
        await asyncio.gather(pulse, return_exceptions=True)
        # Inference threads retain semaphore ownership until they actually finish.
        await task
        logger.info(
            "Realtime transport frames=%s seconds=%.3f gaps=%s evidence=%s",
            received,
            buffer.last_time,
            buffer.gaps,
            evidence.payload(),
        )
