import numpy as np
import pytest

from app.services.speech_confirmation import SpeechConfirmation, decide


def event(time, score=0.1, quality="visible"):
    return dict(time=time, score=score, quality=quality)


def test_short_or_missing_context_never_means_silence():
    negative = [event(1.56), event(1.68)]
    assert decide(negative, 1.8) == "short_unknown"
    assert decide([], 3) == "unknown"
    assert decide(negative + [event(1.8, None, "face_unavailable")], 3) == "unknown"
    assert decide(negative, 2) == "negative"


def test_confirmation_needs_distinct_consecutive_positive_windows():
    assert decide([event(1.56, 0.9), event(1.68, 0.9)], 2) == "confirmed"
    assert decide([event(1.56, 0.9), event(1.56, 0.9)], 2) == "unknown"
    assert decide([event(1.68, 0.9), event(1.56, 0.9)], 2) == "unknown"
    assert decide([event(1.56, 0.9), event(1.8, 0.9)], 2) == "unknown"
    assert decide([event(1.56, 0.9), event(1.68), event(1.8, 0.9)], 2) == "unknown"


def test_bad_weights_and_wrong_frame_clock_preserve_original_decode(tmp_path):
    model = SpeechConfirmation(tmp_path / "missing.npz")
    model.load()
    result = model.evaluate([], 0, 2, 1, 0)
    assert result["state"] == "unavailable" and result["allow_decode"]
    assert result["failure"]
    model.close()


def test_positive_confirmation_is_scoped_to_one_turn(monkeypatch):
    from app.services import speech_confirmation as module

    class Model:
        value = 0.9

        def score(self, _):
            return self.value

    monkeypatch.setattr(module, "face_crop", lambda frame, _: (frame[:96, :96], "visible"))
    checker = SpeechConfirmation("unused")
    checker.model = Model()
    frames = [np.full((96, 96, 3), i, dtype=np.uint8) for i in range(50)]
    first = checker.evaluate(frames, 0, 2, 1, 0)
    assert first["state"] == "confirmed" and first["classifier_calls"] == 2
    checker.model.value = 0.1
    later = checker.evaluate(frames, 1, 3, 1, 0)
    assert later["state"] == "confirmed" and later["classifier_calls"] == 0
    new = checker.evaluate(frames, 3, 5, 2, 3)
    assert new["state"] == "negative" and not new["allow_decode"]
    short = checker.evaluate(frames[:25], 6, 7, 3, 6)
    assert short["state"] == "short_unknown" and short["allow_decode"]
    wrong_clock = checker.evaluate(frames, 8, 9, 4, 8)
    assert wrong_clock["state"] == "unavailable" and wrong_clock["allow_decode"]


def test_isolated_positive_is_retained_after_long_turn_cache_eviction(monkeypatch):
    from app.services import speech_confirmation as module

    class Model:
        calls = 0

        def score(self, _):
            self.calls += 1
            return 0.9 if self.calls == 1 else 0.1

    monkeypatch.setattr(module, "face_crop", lambda frame, _: (frame, "visible"))
    checker = SpeechConfirmation("unused")
    checker.model = Model()
    frames = [np.full((1, 1, 3), i, dtype=np.uint8) for i in range(50)]
    first = checker.evaluate(frames, 0, 2, 1, 0)
    assert first["state"] == "unknown" and first["allow_decode"]
    for begin in range(2, 140, 2):
        later = checker.evaluate(frames, begin, begin + 2, 1, 0)
        assert later["state"] == "unknown" and later["allow_decode"]
    assert len(checker.turns[1].scores) == 256
    assert all(row["score"] < 0.5 for row in checker.turns[1].scores.values())
    assert checker.turns[1].saw_positive
    next_turn = checker.evaluate(frames, 140, 142, 2, 140)
    assert next_turn["state"] == "negative" and not next_turn["allow_decode"]


@pytest.mark.parametrize("frame_count, expected_calls", [(15, True), (27, False)])
def test_optional_gate_reaches_actual_live_worker_without_dropping_short_turns(
    monkeypatch, frame_count, expected_calls
):
    import json
    import struct
    import time
    from dataclasses import replace
    import cv2
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.main import create_app
    from app.services import auto_stream
    from app.services.visual_activity import VisualMotionDetector, Observation
    from test_streaming_v2 import TimedEngine

    class Gate:
        failure = None

        def __init__(self, *_, **__):
            pass

        def load(self):
            pass

        def close(self):
            pass

        def evaluate(self, frames, begin, end, turn_id, turn_start):
            state = decide([event(1.56), event(1.68)], end - begin)
            return dict(enabled=True, state=state, allow_decode=state != "negative")

    monkeypatch.setenv("LIP_EXPERIMENTAL_VISUAL_CONFIRMATION", "test-only.npz")
    monkeypatch.setattr(auto_stream, "SpeechConfirmation", Gate)
    monkeypatch.setattr(VisualMotionDetector, "load", lambda self: None)
    monkeypatch.setattr(VisualMotionDetector, "analyze", lambda self, rgb: Observation(2.0))
    engine = TimedEngine()
    calls = []
    original = engine.transcribe_frames

    def decode(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(engine, "transcribe_frames", decode)
    config = replace(Settings.from_env(), realtime_min_seconds=2.0)
    with TestClient(create_app(settings=config, engine=engine)) as client:
        with client.websocket_connect("/v1/realtime") as ws:
            ws.send_json(dict(type="start", protocol=2, input_kind="raw_face", auto_endpoint=True))
            assert ws.receive_json()["experimental_visual_confirmation"]
            for i in range(frame_count):
                _, jpeg = cv2.imencode(".jpg", np.full((96, 96, 3), 70 + i * 3, np.uint8))
                ws.send_bytes(b"LIP2" + struct.pack(">Id", i, i * 120) + jpeg.tobytes())
                while ws.receive_json()["type"] != "ack":
                    pass
                time.sleep(0.055)
            ws.send_text(json.dumps(dict(type="stop")))
            while True:
                message = ws.receive_json()
                if message["type"] == "session_final":
                    assert bool(message["transcript"]) == expected_calls
                    assert bool(message["evidence"]["unavailable_windows"]) != expected_calls
                    break
    assert bool(calls) == expected_calls
