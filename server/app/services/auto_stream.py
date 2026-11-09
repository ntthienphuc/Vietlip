"""Continuous camera session with visual onset and automatic endpointing."""

from __future__ import annotations
import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import logging
import time
from fastapi import WebSocketDisconnect
from .live_evidence import LiveEvidence, check_live_images
from .realtime import decode_jpeg_frames
from .streaming_buffer import FrameBuffer, unpack_frame
from .caption_stability import AgreementTimeline
from .caption_delivery import CaptionDelivery
from .live_trace import LiveTrace
from .video_preprocessor import VideoValidationError
from .visual_activity import EndpointPolicy, Observation, VisualMotionDetector

logger = logging.getLogger(__name__)


@dataclass
class Turn:
    id: int
    start: float
    frozen: tuple | None = None
    reason: str | None = None
    last_key: tuple | None = None
    result: object = None


async def run_auto_stream(ws, config, engine, semaphore, start_message):
    session = AutoStream(ws, config, engine, semaphore, start_message)
    await session.run()


class AutoStream:
    def __init__(self, ws, config, engine, semaphore, start):
        self.ws, self.config, self.engine, self.semaphore = ws, config, engine, semaphore
        self.rotation, self.kind = (
            start.get("rotation_degrees", 0),
            start.get("input_kind", "raw_face"),
        )
        self.buffer = FrameBuffer(
            seconds=config.realtime_window_seconds + 2,
            max_frames=int(config.target_fps * (config.realtime_window_seconds + 2) * 2),
        )
        self.timeline, self.evidence = AgreementTimeline(), LiveEvidence()
        self.delivery = CaptionDelivery()
        self.trace = LiveTrace()
        self.detector, self.gate = VisualMotionDetector(self.kind), EndpointPolicy()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lip-activity")
        self.event, self.send_lock = asyncio.Event(), asyncio.Lock()
        self.current, self.pending = None, deque()
        self.turn_id = self.received = self.activity_samples = 0
        self.activity_time = -1.0
        self.capture_closed = self.disconnected = self.monitor_done = False
        self.started = self.last_frame_wall = time.monotonic()
        self.state, self.decoder_state = "waiting_for_face", "idle"
        self.activity_ms = 0.0
        self.first_frame_source = self.first_frame_wall = None

    async def send(self, payload):
        if self.disconnected:
            return
        try:
            async with self.send_lock:
                self.delivery.stamp(payload)
                await self.ws.send_json(payload)
                self.trace.record(payload)
        except (WebSocketDisconnect, RuntimeError):
            self.disconnected = True

    def transport(self):
        recent = [f for f in self.buffer.frames if f.seconds >= self.buffer.last_time - 2]
        fps = (
            (len(recent) - 1) / (recent[-1].seconds - recent[0].seconds) if len(recent) > 1 else 0.0
        )
        # Expose capture-to-server age independently of session handshake time.
        capture_elapsed = (
            None
            if self.first_frame_wall is None
            else (time.monotonic() - self.first_frame_wall + self.first_frame_source)
        )
        return dict(
            received_frames=self.received,
            capture_fps=round(fps, 2),
            capture_clock_seconds=None if capture_elapsed is None else round(capture_elapsed, 4),
            last_frame_age_ms=round((time.monotonic() - self.last_frame_wall) * 1000),
            capture_gaps=self.buffer.gaps,
            buffered_frames=len(self.buffer.frames),
            recognition_state=self.state,
            decoder_state=self.decoder_state,
            activity_detector="estimated_lip_motion_v1",
            activity_samples=self.activity_samples,
            activity_timestamp=self.activity_time,
            activity_processing_ms=round(self.activity_ms, 2),
        )

    def finish_turn(self, end, reason):
        if self.current is None:
            return
        turn, self.current = self.current, None
        turn.frozen = self.buffer.snapshot(
            self.config.realtime_window_seconds, self.config.target_fps, after=turn.start, until=end
        )
        turn.reason = reason
        if reason not in {"visual_pause", "session_stop", "manual"}:
            self.evidence.record(turn.start, end, reason)
        if len(self.pending) >= 2:
            lost = self.pending.popleft()
            self.evidence.record(lost.start, lost.frozen[2], "server_overloaded")
        self.pending.append(turn)
        self.event.set()

    def observe_frame(self, frame):
        rgb = decode_jpeg_frames([frame.jpeg], True, rotation_degrees=self.rotation, max_width=360)[
            0
        ]
        return self.detector.analyze(rgb)

    async def monitor(self):
        loop = asyncio.get_running_loop()
        last_heartbeat, last_state = 0.0, None
        try:
            while not self.disconnected:
                frame = self.buffer.frames[-1] if self.buffer.frames else None
                if (
                    frame is not None
                    and frame.seconds > self.activity_time
                    and (frame.seconds - self.activity_time >= 0.1 or self.capture_closed)
                ):
                    tick = time.perf_counter()
                    try:
                        observation = await loop.run_in_executor(
                            self.executor, self.observe_frame, frame
                        )
                    except Exception:
                        logger.exception("Visual activity failed")
                        observation = Observation(quality="activity_unavailable")
                    self.activity_ms = (time.perf_counter() - tick) * 1000
                    self.activity_samples += 1
                    self.activity_time = frame.seconds
                    update = self.gate.observe(frame.seconds, observation)
                    self.state = update.state
                    if update.start is not None and self.current is None:
                        self.turn_id += 1
                        self.current = Turn(self.turn_id, update.start)
                        await self.send(
                            dict(
                                type="activity",
                                speech_start=update.start,
                                turn_id=self.turn_id,
                                **self.transport(),
                            )
                        )
                    if update.end is not None:
                        self.finish_turn(update.end, update.reason)
                        await self.send(
                            dict(
                                type="activity",
                                speech_end=update.end,
                                endpoint_reason=update.reason,
                                turn_id=self.turn_id,
                                **self.transport(),
                            )
                        )
                    self.event.set()
                age = time.monotonic() - self.last_frame_wall
                if age > 2:
                    self.state = "camera_stalled"
                    if self.current is not None:
                        self.finish_turn(
                            self.buffer.last_time + 1 / self.config.target_fps, "capture_gap"
                        )
                    self.gate = EndpointPolicy()
                if self.state != last_state or time.monotonic() - last_heartbeat >= 1:
                    await self.send(dict(type="telemetry", **self.transport()))
                    last_state, last_heartbeat = self.state, time.monotonic()
                if self.capture_closed:
                    self.finish_turn(
                        self.buffer.last_time + 1 / self.config.target_fps, "session_stop"
                    )
                    return
                await asyncio.sleep(0.04)
        finally:
            self.monitor_done = True
            self.event.set()

    async def worker(self):
        while not self.disconnected:
            try:
                await asyncio.wait_for(self.event.wait(), timeout=0.3)
            except asyncio.TimeoutError:
                pass
            self.event.clear()
            if self.disconnected:
                return
            endpoint = bool(self.pending)
            turn = self.pending.popleft() if endpoint else self.current
            if turn is None:
                if self.monitor_done:
                    await self.send(
                        dict(
                            type="session_final",
                            protocol=2,
                            transcript=self.timeline.text,
                            stable_transcript=self.timeline.text,
                            provisional_transcript="",
                            model_id=self.config.model_id,
                            review_required=True,
                            incomplete=bool(self.evidence.unavailable_windows or self.buffer.gaps),
                            evidence=self.evidence.payload(),
                            **self.transport(),
                        )
                    )
                    return
                continue
            if not endpoint:
                # Silence is context, not an invitation to decode another sentence.
                if self.state != "speaking":
                    continue
                _, begin, end = self.buffer.snapshot(
                    self.config.realtime_window_seconds, self.config.target_fps, after=turn.start
                )
                if end - begin < self.config.realtime_min_seconds or (
                    turn.last_key
                    and end - turn.last_key[1] < self.config.realtime_decode_interval_seconds
                ):
                    continue
            tick = time.perf_counter()
            begin, end = turn.start, self.buffer.last_time
            try:
                self.decoder_state = "finalizing" if endpoint else "processing"
                async with self.semaphore:
                    # Endpoint images are frozen on detection. Live windows use
                    # the newest frames after GPU admission, not an old backlog.
                    frames, begin, end = (
                        turn.frozen
                        if endpoint
                        else self.buffer.snapshot(
                            self.config.realtime_window_seconds,
                            self.config.target_fps,
                            after=turn.start,
                        )
                    )
                    if not frames or end - begin < 0.48:
                        raise VideoValidationError(
                            "short_activity", "Chuyển động quá ngắn để đọc rõ. Hãy nói lại."
                        )
                    key = (begin, end)
                    if turn.last_key == key and turn.result is not None:
                        result = turn.result
                    else:
                        rgb = await asyncio.to_thread(
                            decode_jpeg_frames,
                            frames,
                            True,
                            rotation_degrees=self.rotation,
                            max_width=360 if self.kind == "raw_face" else None,
                        )
                        await asyncio.to_thread(check_live_images, rgb, self.config.target_fps)
                        result = await asyncio.to_thread(
                            self.engine.transcribe_frames,
                            rgb,
                            source_fps=self.config.target_fps,
                            input_kind=self.kind,
                            context_hint=None,
                        )
                        if not result.transcript.strip():
                            raise VideoValidationError(
                                "empty_hypothesis", "Chưa đọc được đoạn này. Hãy nói lại."
                            )
                        turn.last_key, turn.result = key, result
                        self.evidence.record(begin, end)
                words = result.diagnostics.get("words", [])
                if not words:
                    # No fabricated ownership when alignment failed.
                    raise VideoValidationError(
                        "word_timing_unavailable", "Chưa ghép được chữ vào phiên. Hãy nói lại."
                    )
                update = self.timeline.update(
                    words,
                    begin,
                    end,
                    final=endpoint,
                    right_context=self.config.realtime_overlap_seconds,
                )
                await self.send(
                    dict(
                        update,
                        type="segment_final" if endpoint else "partial",
                        protocol=2,
                        elapsed_ms=round((time.perf_counter() - tick) * 1000),
                        turn_id=turn.id,
                        endpoint_reason=turn.reason,
                        window_start=begin,
                        window_end=end,
                        source_seconds=end,
                        behind_live_ms=round(max(0, self.buffer.last_time - end) * 1000),
                        window_end_to_caption_ms=None
                        if self.first_frame_wall is None
                        else round(
                            max(
                                0,
                                time.monotonic()
                                - self.first_frame_wall
                                + self.first_frame_source
                                - end,
                            )
                            * 1000
                        ),
                        engine_runtime=result.diagnostics.get("runtime", {}),
                        word_timing_available=True,
                        window_words=words,
                        window_transcript=result.transcript,
                        model_id=self.config.model_id,
                        device=self.engine.device_label,
                        review_required=True,
                        experimental_phoneme_rescoring=result.diagnostics.get(
                            "experimental_phoneme_rescoring", {"enabled": False}
                        ),
                        incomplete=bool(self.evidence.unavailable_windows or self.buffer.gaps),
                        evidence=self.evidence.payload(),
                        **self.transport(),
                    )
                )
            except Exception as exc:
                self.timeline.discard_pending()
                if not isinstance(exc, VideoValidationError):
                    logger.exception("Auto endpoint decode failed")
                if turn.last_key != (begin, end) or turn.result is not None:
                    self.evidence.record(begin, end, getattr(exc, "code", "caption_unavailable"))
                turn.last_key, turn.result = (begin, end), None
                message = (
                    str(exc)
                    if isinstance(exc, VideoValidationError)
                    else "Chưa đọc được đoạn này. Hãy nói lại."
                )
                # An unfinished prefix can decode to blank. Keep its unavailable
                # evidence, but do not tell a still-speaking user to repeat yet.
                waiting_for_context = (
                    not endpoint and getattr(exc, "code", None) == "empty_hypothesis"
                )
                await self.send(
                    dict(
                        type="telemetry" if waiting_for_context else "notice",
                        code=getattr(exc, "code", "caption_unavailable"),
                        message=message,
                        turn_id=turn.id,
                        transcript=self.timeline.text,
                        stable_transcript=self.timeline.text,
                        provisional_transcript="",
                        incomplete=True,
                        evidence=self.evidence.payload(),
                        **self.transport(),
                    )
                )
            finally:
                self.decoder_state = "idle"
            if self.pending or self.monitor_done:
                self.event.set()

    async def run(self):
        tasks = []
        loop = asyncio.get_running_loop()
        try:
            if not self.engine.loaded:
                async with self.semaphore:
                    await asyncio.to_thread(self.engine.load)
            await loop.run_in_executor(self.executor, self.detector.load)
            await self.send(
                dict(
                    type="ready",
                    protocol=2,
                    sample_fps=self.config.realtime_sample_fps,
                    max_inflight_frames=4,
                    max_seconds=self.config.realtime_max_seconds,
                    window_seconds=self.config.realtime_window_seconds,
                    auto_endpoint=True,
                    silence_seconds=self.gate.silence_seconds,
                    mode="visual_activity_sliding_window",
                    stability_policy="local_agreement_2",
                )
            )
            monitor, worker = (
                asyncio.create_task(self.monitor()),
                asyncio.create_task(self.worker()),
            )
            tasks = [monitor, worker]
            while not self.disconnected:
                message = await asyncio.wait_for(self.ws.receive(), timeout=15)
                if message["type"] == "websocket.disconnect":
                    self.disconnected = True
                    break
                if message.get("bytes") is not None:
                    packet = message["bytes"]
                    if len(packet) > self.config.realtime_max_frame_bytes + 16:
                        await self.ws.close(code=1009)
                        break
                    frame = unpack_frame(packet)
                    if (
                        frame.seconds > self.config.realtime_max_seconds
                        or time.monotonic() - self.started > self.config.realtime_max_seconds + 30
                    ):
                        break
                    self.buffer.add(frame)
                    self.received += 1
                    self.last_frame_wall = time.monotonic()
                    if self.first_frame_wall is None:
                        self.first_frame_source, self.first_frame_wall = (
                            frame.seconds,
                            self.last_frame_wall,
                        )
                    await self.send(dict(type="ack", sequence=frame.sequence))
                elif message.get("text"):
                    control = json.loads(message["text"])
                    if control.get("type") == "stop":
                        break
                    if control.get("type") == "caption_rendered":
                        receipt = self.delivery.acknowledge(control)
                        if receipt is not None:
                            self.trace.record(receipt)
            self.capture_closed = True
            await asyncio.gather(*tasks)
        except (WebSocketDisconnect, asyncio.TimeoutError):
            self.disconnected = True
        except ValueError as exc:
            await self.send(dict(type="error", code="invalid_frame", message=str(exc)))
            await self.ws.close(code=1008)
        except Exception:
            logger.exception("Automatic live session failed")
            await self.send(
                dict(
                    type="error",
                    code="live_unavailable",
                    message="Luồng tự động chưa sẵn sàng. Kiểm tra máy chủ.",
                )
            )
            await self.ws.close(code=1013)
        finally:
            self.disconnected = self.capture_closed = True
            self.event.set()
            # Wait for owning threads before closing native resources.
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await loop.run_in_executor(self.executor, self.detector.close)
            self.executor.shutdown(wait=True)
            self.trace.close()
            logger.info(
                "Auto live frames=%s turns=%s activity_ms=%.2f evidence=%s",
                self.received,
                self.turn_id,
                self.activity_ms,
                self.evidence.payload(),
            )
