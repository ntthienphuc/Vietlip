import struct
from dataclasses import replace
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.services.engine import MockEngine
from app.services.streaming_buffer import Frame, FrameBuffer, WordTimeline, unpack_frame
from app.services.word_alignment import align_words
from app.services.realtime import LiveJpegDecoder, decode_jpeg_frames
from app.services.video_preprocessor import VideoValidationError


def test_native_camera_rotation_and_resize_preserve_upright_geometry():
    frame = np.zeros((480, 720, 3), dtype=np.uint8)
    frame[:, :360] = [0, 0, 255]
    frame[:, 360:] = [255, 0, 0]
    _, jpeg = cv2.imencode(".jpg", frame)
    image = decode_jpeg_frames([jpeg.tobytes()], True, rotation_degrees=90, max_width=360)[0]
    assert image.shape == (540, 360, 3)
    assert image[50, 50, 0] > 240 and image[-50, 50, 2] > 240


def test_timestamp_packet_rejects_bad_time_and_preserves_capture_time():
    jpeg = b"\xff\xd8\xff\xd9"
    f = unpack_frame(b"LIP2" + struct.pack(">Id", 7, 1234.5) + jpeg)
    assert f.sequence == 7 and f.seconds == 1.2345 and f.jpeg == jpeg
    for timestamp in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            unpack_frame(b"LIP2" + struct.pack(">Id", 0, timestamp) + jpeg)


def test_live_decoder_reuses_only_session_pixels_and_preserves_order_and_rotation():
    payloads = [
        cv2.imencode(".jpg", np.full((32, 48, 3), shade, dtype=np.uint8))[1].tobytes()
        for shade in (20, 80, 140)
    ]
    a, b, c = payloads
    one_frame_bytes = max(map(len, payloads)) + 32 * 48 * 3
    cache = LiveJpegDecoder(90, 360, max_bytes=2 * one_frame_bytes)
    first = cache.decode([a, b, a])
    assert first[0] is first[2]
    second = cache.decode([c, b, a])
    expected = decode_jpeg_frames([c, b, a], True, rotation_degrees=90, max_width=360)
    assert second[1] is first[1] and second[2] is first[0]
    assert all(np.array_equal(x, y) for x, y in zip(second, expected, strict=True))
    assert cache.decode([c])[0] is not second[0]
    assert LiveJpegDecoder(0, 360).decode([a])[0].shape == (32, 48, 3)
    for bad in ([], [a, b"broken", c], [b""]):
        with pytest.raises(VideoValidationError):
            cache.decode(bad)


def test_frame_drop_does_not_compress_time_and_memory_stays_bounded():
    buffer = FrameBuffer(seconds=2, max_bytes=2000, max_frames=100)
    for i in range(1000):
        buffer.add(Frame(i, i / 10, b"x" * 10))
    frames, start, end = buffer.snapshot(2, 25)
    assert len(buffer.frames) <= 21 and buffer.bytes <= 210
    assert len(frames) == 50
    assert end - start == pytest.approx(2)
    with pytest.raises(ValueError):
        buffer.add(Frame(999, 100, b"x"))


def test_gap_does_not_generate_fake_intermediate_frames():
    buffer = FrameBuffer()
    for i, t in enumerate([0, 0.04, 0.08, 2, 2.04, 2.08]):
        buffer.add(Frame(i, t, b"x"))
    frames, start, end = buffer.snapshot(6, 25)
    assert start == 2 and len(frames) == 3 and buffer.gaps == 1


def test_overlapping_windows_share_sampling_grid_despite_camera_jitter():
    buffer = FrameBuffer()
    for i in range(101):
        buffer.add(Frame(i, i / 30 + 0.003, str(i).encode()))
    first, start_a, _ = buffer.snapshot(2, 25)
    for i in range(101, 147):
        buffer.add(Frame(i, i / 30 + 0.003, str(i).encode()))
    second, start_b, _ = buffer.snapshot(2, 25)
    assert start_a * 25 == pytest.approx(round(start_a * 25))
    assert start_b * 25 == pytest.approx(round(start_b * 25))
    indexed_a = {round((start_a + i / 25) * 25): frame for i, frame in enumerate(first)}
    indexed_b = {round((start_b + i / 25) * 25): frame for i, frame in enumerate(second)}
    common = set(indexed_a) & set(indexed_b)
    assert len(common) >= 10
    assert all(indexed_a[t] == indexed_b[t] for t in common)


def test_sampling_grid_respects_turn_boundary_and_single_frame_startup():
    buffer = FrameBuffer()
    buffer.add(Frame(0, 0.013, b"first"))
    assert buffer.snapshot(6, 25)[0] == [b"first"]
    for i in range(1, 50):
        buffer.add(Frame(i, 0.013 + i / 30, str(i).encode()))
    frames, start, end = buffer.snapshot(6, 25, after=0.42, until=1.2)
    assert start >= 0.42 and end <= 1.24
    assert all(int(frame) >= 13 for frame in frames)


def test_word_timeline_keeps_repeated_speech_and_does_not_repeat_jittered_overlap():
    timeline = WordTimeline()
    words = [
        {"text": "rất", "start": 0.1, "end": 0.3},
        {"text": "rất", "start": 0.4, "end": 0.6},
        {"text": "tốt", "start": 0.7, "end": 1.0},
    ]
    timeline.update(words, 0, 3)
    out = timeline.update(words, 0, 3)
    assert out["stable_transcript"] == "rất rất tốt"
    shifted = [dict(w, start=w["start"] + 0.1, end=w["end"] + 0.1) for w in words]
    shifted.append({"text": "nhé", "start": 1.2, "end": 1.5})
    out = timeline.update(shifted, 0, 3, final=True)
    assert out["transcript"] == "rất rất tốt nhé"


def test_ctc_alignment_handles_repeated_tokens_and_word_boundaries():
    ids = [0, 1, 1, 0, 1, 2, 0]
    logp = np.full((7, 4), -20, dtype=np.float32)
    logp[np.arange(7), ids] = 0
    words = align_words(logp, [1, 1, 2], ["<blank>", "▁rất", "▁tốt", "<eos>"], 25)
    assert [w["text"] for w in words] == ["rất", "rất", "tốt"]
    assert words[0]["end"] <= words[1]["start"]
    assert align_words(logp[:2], [1, 1, 1], ["", "a"], 25) == []


class TimedEngine(MockEngine):
    def transcribe_frames(self, frames_rgb, **kwargs):
        result = super().transcribe_frames(frames_rgb, **kwargs)
        result.diagnostics["words"] = [
            {"text": "xin", "start": 0, "end": 0.2},
            {"text": "chào", "start": 0.2, "end": 0.4},
        ]
        return result


def test_protocol_two_acknowledges_and_flushes_short_tail():
    settings = replace(
        Settings.from_env(),
        realtime_min_seconds=0.4,
        realtime_decode_interval_seconds=0.5,
        realtime_window_seconds=2,
    )
    _, jpeg = cv2.imencode(".jpg", np.full((100, 100, 3), 100, dtype=np.uint8))
    with TestClient(create_app(settings=settings, engine=TimedEngine())) as client:
        with client.websocket_connect("/v1/realtime") as ws:
            ws.send_json({"type": "start", "protocol": 2, "input_kind": "mouth_roi"})
            assert ws.receive_json()["protocol"] == 2
            for i in range(6):
                ws.send_bytes(b"LIP2" + struct.pack(">Id", i, i * 100) + jpeg.tobytes())
            ws.send_json({"type": "stop"})
            events = []
            for _ in range(15):
                event = ws.receive_json()
                events.append(event)
                if event["type"] == "session_final":
                    break
            assert [e["sequence"] for e in events if e["type"] == "ack"] == list(range(6))
            assert events[-1]["type"] == "session_final"
            assert events[-1]["transcript"] == "xin chào"
            assert events[-1]["source_seconds"] == pytest.approx(0.52)


@pytest.mark.parametrize("successful_window_first", [False, True])
def test_final_after_failed_decode_neither_hangs_nor_reuses_stale_words(successful_window_first):
    class FailingEngine(TimedEngine):
        calls = 0

        def transcribe_frames(self, frames_rgb, **kwargs):
            self.calls += 1
            if not successful_window_first or self.calls > 1:
                raise RuntimeError("Deliberate decoder failure")
            return super().transcribe_frames(frames_rgb, **kwargs)

    settings = replace(
        Settings.from_env(),
        realtime_min_seconds=0.4,
        realtime_decode_interval_seconds=0.5,
        realtime_overlap_seconds=0.1,
        realtime_window_seconds=2,
    )
    _, jpeg = cv2.imencode(".jpg", np.full((100, 100, 3), 100, dtype=np.uint8))
    with TestClient(create_app(settings=settings, engine=FailingEngine())) as client:
        with client.websocket_connect("/v1/realtime") as ws:
            ws.send_json({"type": "start", "protocol": 2, "input_kind": "mouth_roi"})
            assert ws.receive_json()["type"] == "ready"
            batches = [[0, 1], [2]] if successful_window_first else [[0, 1]]
            for batch in batches:
                for i in batch:
                    ws.send_bytes(b"LIP2" + struct.pack(">Id", i, i * 500) + jpeg.tobytes())
                while True:
                    event = ws.receive_json()
                    if event["type"] != "ack":
                        break
                assert event["type"] == (
                    "partial" if successful_window_first and batch[0] == 0 else "notice"
                )
            ws.send_json({"type": "stop"})
            final = ws.receive_json()
            assert final["type"] == "session_final" and final["incomplete"]
            assert final["transcript"] == ("xin chào" if successful_window_first else "")
