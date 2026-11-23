from __future__ import annotations

import time
from dataclasses import replace

import numpy as np
import cv2
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from mock_engine import MockEngine
from app.services.nbest_consensus import summarize_nbest
from app.services.realtime import ContinuousTranscript, LocalAgreement


def fake_mp4() -> bytes:
    return b"\x00\x00\x00\x18ftypmp42" + (b"\x00" * 64)


class FailingEngine(MockEngine):
    def transcribe(self, *args, **kwargs):
        raise ModuleNotFoundError("No module named 'private-runtime'")


class RecordingRealtimeEngine(MockEngine):
    def __init__(self):
        self.frame_counts: list[int] = []

    def transcribe_frames(self, frames_rgb, **kwargs):
        self.frame_counts.append(len(frames_rgb))
        return super().transcribe_frames(frames_rgb, **kwargs)


def test_health_does_not_expose_checkpoint_path():
    with TestClient(create_app(engine=MockEngine())) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["model_loaded"] is True
    assert payload["requested_device"] == "auto"
    assert payload["device"] == "cpu-test"
    assert payload["precision"] == "float32"
    assert "checkpoint" not in response.text.lower()
    assert payload["realtime_available"] is True
    assert payload["realtime_mode"] == "continuous_visual_captions"


def test_local_agreement_only_commits_repeated_prefix():
    agreement = LocalAgreement()
    first = agreement.update("xin chào tất cả")
    second = agreement.update("xin chào các bạn")
    third = agreement.update("xin chào các bạn nhé")

    assert first["stable_transcript"] == ""
    assert second["stable_transcript"] == "xin chào"
    assert second["provisional_transcript"] == "các bạn"
    assert third["stable_transcript"] == "xin chào các bạn"
    assert third["provisional_transcript"] == "nhé"


def test_continuous_transcript_stitches_overlapping_windows():
    transcript = ContinuousTranscript()
    assert transcript.commit("xin chào tất cả mọi người") == ("xin chào tất cả mọi người")
    assert transcript.preview("mọi người hôm nay chúng ta học") == (
        "xin chào tất cả mọi người hôm nay chúng ta học"
    )
    assert transcript.commit("mọi người hôm nay chúng ta học") == (
        "xin chào tất cả mọi người hôm nay chúng ta học"
    )


def test_realtime_websocket_returns_visual_partial():
    settings = replace(
        Settings.from_env(),
        realtime_sample_fps=2,
        realtime_min_seconds=1,
        realtime_decode_interval_seconds=0.5,
        realtime_max_seconds=3,
    )
    image = np.full((120, 160, 3), 160, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok

    with TestClient(create_app(settings=settings, engine=MockEngine())) as client:
        with client.websocket_connect("/v1/realtime") as websocket:
            websocket.send_json({"type": "start"})
            ready = websocket.receive_json()
            assert ready["type"] == "ready"
            websocket.send_bytes(encoded.tobytes())
            websocket.send_bytes(encoded.tobytes())
            partial = websocket.receive_json()
            assert partial["type"] == "partial"
            assert partial["transcript"] == "xin chào"
            assert partial["review_required"] is True
            websocket.send_json({"type": "stop"})


def test_realtime_websocket_finalizes_continuous_session():
    settings = replace(
        Settings.from_env(),
        realtime_sample_fps=2,
        realtime_min_seconds=1,
        realtime_decode_interval_seconds=0.5,
        realtime_window_seconds=2,
        realtime_overlap_seconds=1,
        realtime_max_seconds=10,
    )
    image = np.full((120, 160, 3), 160, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok

    with TestClient(create_app(settings=settings, engine=MockEngine())) as client:
        with client.websocket_connect("/v1/realtime") as websocket:
            websocket.send_json({"type": "start"})
            assert websocket.receive_json()["mode"] == ("continuous_visual_captions")
            for _ in range(6):
                websocket.send_bytes(encoded.tobytes())

            saw_segment = False
            for _ in range(6):
                message = websocket.receive_json()
                if message["type"] == "segment_final":
                    saw_segment = True
                    break
            assert saw_segment

            websocket.send_json({"type": "stop"})
            final = None
            for _ in range(6):
                message = websocket.receive_json()
                if message["type"] == "session_final":
                    final = message
                    break
            assert final is not None
            assert final["transcript"] == "xin chào"


def test_realtime_uses_rolling_windows_and_keeps_absolute_limit():
    settings = replace(
        Settings.from_env(),
        realtime_sample_fps=2,
        realtime_min_seconds=1,
        realtime_decode_interval_seconds=0.5,
        realtime_window_seconds=2,
        realtime_overlap_seconds=1,
        realtime_max_seconds=5,
    )
    engine = RecordingRealtimeEngine()
    image = np.full((120, 160, 3), 160, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok

    with TestClient(create_app(settings=settings, engine=engine)) as client:
        with client.websocket_connect("/v1/realtime") as websocket:
            websocket.send_json({"type": "start"})
            assert websocket.receive_json()["type"] == "ready"
            for _ in range(12):
                websocket.send_bytes(encoded.tobytes())
            websocket.send_json({"type": "stop"})

            messages = []
            for _ in range(20):
                message = websocket.receive_json()
                messages.append(message)
                if message["type"] == "session_final":
                    break

    assert any(item["type"] == "limit" for item in messages)
    assert messages[-1]["type"] == "session_final"
    assert engine.frame_counts
    assert max(engine.frame_counts) <= 4


def test_device_selection_falls_back_to_cpu():
    from app.services.native_engine import NativeAvsrEngine

    assert (
        NativeAvsrEngine._select_device(
            "auto",
            cuda_available=False,
            allow_cpu_fallback=True,
        )
        == "cpu"
    )
    assert (
        NativeAvsrEngine._select_device(
            "cuda",
            cuda_available=False,
            allow_cpu_fallback=True,
        )
        == "cpu"
    )


def test_rejects_non_mp4_extension():
    with TestClient(create_app(engine=MockEngine())) as client:
        response = client.post(
            "/v1/transcriptions",
            files={"video": ("sample.mov", fake_mp4(), "video/quicktime")},
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_media_type"


def test_rejects_invalid_mp4_header():
    with TestClient(create_app(engine=MockEngine())) as client:
        response = client.post(
            "/v1/transcriptions",
            files={"video": ("sample.mp4", b"not a video file", "video/mp4")},
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_mp4"


def test_transcription_contract_is_review_only():
    with TestClient(create_app(engine=MockEngine())) as client:
        response = client.post(
            "/v1/transcriptions",
            files={"video": ("sample.mp4", fake_mp4(), "video/mp4")},
            data={
                "request_id": "contract-001",
                "input_kind": "raw_face",
                "context_hint": "chào hỏi",
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "contract-001"
    assert payload["transcript"] == "xin chào"
    assert payload["status"] == "review_required"
    assert payload["num_frames"] == 25
    assert payload["diagnostics"]["context_hint_applied"] is False
    assert len(payload["alternatives"]) == 2
    assert payload["processing_mode"] == "visual_only"
    assert payload["assisted_transcript"] is None
    assert payload["consensus_transcript"] == "xin chào"
    assert payload["diagnostics"]["nbest_consensus"]["transcript_owner_changed"] is False


def test_nbest_consensus_can_surface_a_medoid_without_replacing_top1():
    diagnostic = summarize_nbest(
        [
            {"text": "xin chào tất cả", "raw_score": 0.0},
            {"text": "xin chào bạn", "raw_score": -0.1},
            {"text": "xin chào bạn", "raw_score": -0.2},
        ]
    )
    assert diagnostic is not None
    assert diagnostic["candidate_text"] == "xin chào bạn"
    assert diagnostic["agrees_with_top1"] is False
    assert diagnostic["is_calibrated_probability"] is False


def test_async_job_returns_202_then_completed_result():
    with TestClient(create_app(engine=MockEngine())) as client:
        accepted = client.post(
            "/v1/jobs",
            files={"video": ("sample.mp4", fake_mp4(), "video/mp4")},
            data={"request_id": "job-contract-001"},
        )
        assert accepted.status_code == 202
        payload = accepted.json()
        assert payload["status"] == "queued"
        assert payload["request_id"] == "job-contract-001"

        status = None
        for _ in range(100):
            response = client.get(f"/v1/jobs/{payload['job_id']}")
            assert response.status_code == 200
            status = response.json()
            if status["status"] in {"completed", "failed"}:
                break
            time.sleep(0.01)

        assert status is not None
        assert status["status"] == "completed"
        assert status["result"]["transcript"] == "xin chào"
        assert status["result"]["status"] == "review_required"

        health = client.get("/healthz").json()
        assert health["job_capacity"] >= 1
        assert health["queued_jobs"] == 0


def test_removed_modes_are_rejected_on_both_upload_routes():
    with TestClient(create_app(engine=MockEngine())) as client:
        for route in ("/v1/transcriptions", "/v1/jobs"):
            for mode in ("llm_assist", "context_select", "unknown"):
                response = client.post(
                    route,
                    files={"video": ("sample.mp4", fake_mp4(), "video/mp4")},
                    data={"mode": mode, "accept_llm_risk": "true", "context_hint": "chào hỏi"},
                )
                assert response.status_code == 422
                assert response.json()["detail"]["code"] == "invalid_mode"
        health = client.get("/healthz").json()
        assert "llm_model" not in health
        assert "llm_available" not in health
        assert not hasattr(client.app.state, "llm")


def test_model_error_does_not_leak_internal_exception():
    with TestClient(create_app(engine=FailingEngine())) as client:
        response = client.post(
            "/v1/transcriptions",
            files={"video": ("sample.mp4", fake_mp4(), "video/mp4")},
        )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "model_unavailable"
    assert "private-runtime" not in response.text
    assert "ModuleNotFoundError" not in response.text
