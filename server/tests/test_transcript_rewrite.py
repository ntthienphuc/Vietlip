"""Exercise the actual text-only HTTP boundary without a paid/external API."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.services.engine import MockEngine
from app.services.transcript_rewrite import (
    PROMPTS,
    RewriteRequest,
    TranscriptRewriter,
)


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    received = []
    response = {"status": 200, "text": "Xin chào bạn.", "finish": "stop"}
    entered, release = threading.Event(), threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append((dict(self.headers), body))
            if response.get("block"):
                entered.set()
                release.wait(2)
            payload = {
                "model": "test-model",
                "choices": [
                    {
                        "message": {"content": response["text"]},
                        "finish_reason": response["finish"],
                    }
                ],
            }
            self.send_response(response["status"])
            self.end_headers()
            try:
                self.wfile.write(json.dumps(payload).encode())
            except OSError:
                pass  # A timeout test deliberately closes the connection.

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = tmp_path / "rewrite.json"
    config.write_text(
        json.dumps(
            {
                "providers": {
                    "gateway": {
                        "endpoint": f"http://127.0.0.1:{server.server_port}/chat/completions",
                        "model": "test-model",
                        "api_key": "SYNTHETIC_TEST_SECRET",
                        "reasoning_effort": "low",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VIETLIP_REWRITE_CONFIG", str(config))
    yield config, received, response, entered, release
    release.set()
    server.shutdown()
    server.server_close()


def test_unconfigured_methods_are_explicit_and_visual_stays_default(tmp_path, monkeypatch):
    monkeypatch.setenv("VIETLIP_REWRITE_CONFIG", str(tmp_path / "missing.json"))
    with TestClient(create_app(engine=MockEngine())) as client:
        methods = client.get("/v1/rewrite-methods").json()
        assert methods["default_method"] == "visual"
        assert sum(m["configured"] for m in methods["methods"]) == 1
        output = client.post(
            "/v1/rewrites",
            json={
                "method": "gateway_direct",
                "text": "xin chào",
            },
        ).json()
        assert output["status"] == "unavailable"
        assert output["text"] == "xin chào"
        assert client.get("/healthz").json()["realtime_available"]


def test_real_transport_keeps_reference_and_credentials_out_of_response(gateway):
    _, received, _, _, _ = gateway
    with TestClient(create_app(engine=MockEngine())) as client:
        methods = client.get("/v1/rewrite-methods")
        assert "SYNTHETIC_TEST_SECRET" not in methods.text
        output = client.post(
            "/v1/rewrites",
            json={
                "method": "gateway_direct",
                "text": "xin chao ban",
            },
        )
    assert output.json()["text"] == "Xin chào bạn."
    assert output.json()["status"] == "completed"
    assert "SYNTHETIC_TEST_SECRET" not in output.text
    headers, payload = received[0]
    assert headers["Authorization"] == "Bearer SYNTHETIC_TEST_SECRET"
    assert payload["messages"] == [
        {"role": "system", "content": PROMPTS["direct"]},
        {"role": "user", "content": json.dumps({"text": "xin chao ban"}, ensure_ascii=False)},
    ]
    assert payload["reasoning_effort"] == "low"
    assert payload["temperature"] == 0


@pytest.mark.parametrize(
    "changed",
    [
        {"text": None},
        {"finish": "length"},
        {"status": 429},
    ],
)
def test_failed_or_incomplete_generation_keeps_raw(gateway, changed):
    _, received, response, _, _ = gateway
    response.update(changed)
    with TestClient(create_app(engine=MockEngine())) as client:
        output = client.post(
            "/v1/rewrites",
            json={
                "method": "gateway_conservative",
                "text": "bản gốc cần giữ",
            },
        ).json()
    assert output["status"] == "unavailable"
    assert output["text"] == "bản gốc cần giữ"
    assert len(received) == 1


def test_empty_and_visual_do_not_contact_provider_and_request_cannot_redirect(gateway):
    _, received, _, _, _ = gateway
    with TestClient(create_app(engine=MockEngine())) as client:
        for method, text in [("gateway_direct", ""), ("visual", "xin chào")]:
            output = client.post("/v1/rewrites", json={"method": method, "text": text})
            assert output.json()["status"] == "unchanged"
        for payload in [
            {"text": "xin chào", "method": "gateway_direct", "endpoint": "http://other"},
            {"text": "xin chào", "method": "unknown"},
            {"text": "a" * 4001, "method": "gateway_direct"},
        ]:
            assert client.post("/v1/rewrites", json=payload).status_code == 422
    assert not received


def test_slow_rewrite_leaves_event_loop_responsive_and_second_request_falls_back(gateway):
    path, received, response, entered, release = gateway
    response["block"] = True

    async def exercise():
        service = TranscriptRewriter(path)
        first = asyncio.create_task(
            service.rewrite(RewriteRequest(text="xin chao", method="gateway_direct"))
        )
        assert await asyncio.to_thread(entered.wait, 1)
        second = await asyncio.wait_for(
            service.rewrite(RewriteRequest(text="phiên hai", method="gateway_direct")), 0.2
        )
        assert second.status == "unavailable"
        assert second.text == "phiên hai"
        release.set()
        assert (await first).status == "completed"

    asyncio.run(exercise())
    assert len(received) == 1


def test_timeout_keeps_raw_and_releases_service(gateway):
    path, received, response, entered, release = gateway
    response["block"] = True
    service = TranscriptRewriter(path, timeout=0.05)
    output = asyncio.run(service.rewrite(RewriteRequest(text="bản gốc", method="gateway_direct")))
    release.set()
    assert output.status == "unavailable"
    assert output.text == "bản gốc"
    assert entered.is_set()
    assert len(received) == 1


def test_local_provider_uses_its_own_model_and_conservative_prompt(gateway):
    path, received, _, _, _ = gateway
    config = json.loads(path.read_text(encoding="utf-8"))
    config["providers"]["local"] = {
        **config["providers"]["gateway"],
        "model": "Qwen-local-test",
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    output = asyncio.run(
        TranscriptRewriter(path).rewrite(
            RewriteRequest(text="xin chào", method="local_conservative")
        )
    )
    assert output.status == "completed"
    assert received[0][1]["model"] == "Qwen-local-test"
    assert received[0][1]["messages"][0]["content"] == PROMPTS["conservative"]


def test_disabled_provider_never_sends_text(gateway):
    path, received, _, _, _ = gateway
    config = json.loads(path.read_text(encoding="utf-8"))
    config["providers"]["gateway"]["enabled"] = False
    path.write_text(json.dumps(config), encoding="utf-8")
    service = TranscriptRewriter(path)
    assert not next(r for r in service.methods()["methods"] if r["id"] == "gateway_direct")[
        "configured"
    ]
    output = asyncio.run(
        service.rewrite(RewriteRequest(text="không được gửi", method="gateway_direct"))
    )
    assert output.status == "unavailable"
    assert output.text == "không được gửi"
    assert not received


def test_production_prompt_matches_frozen_experiment():
    import importlib.util

    path = Path(__file__).parents[2] / "research/llm_rewrite_eval.py"
    spec = importlib.util.spec_from_file_location("frozen_rewrite", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert PROMPTS == module.PROMPTS
