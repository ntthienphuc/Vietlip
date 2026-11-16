"""Exercise the real HTTP boundary without sending data to an external API."""

import asyncio
import json
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.services.engine import MockEngine
from app.services.transcript_rewrite import PROMPTS, RewriteRequest, TranscriptRewriter


@pytest.fixture
def gateway(tmp_path):
    received = []
    response = {"status": 200, "text": "Xin chào bạn.", "finish": "stop"}
    entered, release = threading.Event(), threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            received.append(
                (
                    dict(self.headers),
                    json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                )
            )
            if response.get("block"):
                entered.set()
                release.wait(2)
            self.send_response(response["status"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {
                "choices": [
                    {"finish_reason": response["finish"], "message": {"content": response["text"]}}
                ],
                "model": "model-test",
            }
            try:
                for _ in range(response.get("trickle_count", 0)):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(response.get("trickle_interval", 0.02))
                self.wfile.write(json.dumps(payload).encode())
            except OSError:
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    path = tmp_path / "rewrite.json"
    keys = tmp_path / "keys.json"
    keys.write_text(json.dumps({"groq": "test-private-key"}), encoding="utf-8")
    path.write_text(
        json.dumps(
            {
                "providers": {
                    name: {
                        "endpoint": f"http://127.0.0.1:{server.server_port}",
                        "model": model,
                        "api_key_file": str(keys),
                        "api_key_name": "groq",
                    }
                    for name, model in (("groq", "gpt-test"), ("openrouter", "model-test:free"))
                }
            }
        ),
        encoding="utf-8",
    )
    yield path, received, response, entered, release
    release.set()
    server.shutdown()
    server.server_close()
    thread.join()


def request(**kwargs):
    return RewriteRequest(
        **{"text": "xin chao", "method": "recovery", "sentence_id": "session-1", **kwargs}
    )


def test_discovery_exposes_two_modes_and_no_credentials(gateway):
    path, *_ = gateway
    methods = TranscriptRewriter(path).methods()
    assert [m["id"] for m in methods["methods"]] == ["visual", "recovery"]
    assert methods["phase"] == "per_sentence"
    assert all(p["configured"] for p in methods["providers"])
    encoded = json.dumps(methods)
    assert "test-private-key" not in encoded and "api_key_file" not in encoded
    assert "127.0.0.1" not in encoded


def test_only_text_is_sent_and_id_is_preserved(gateway):
    path, received, *_ = gateway
    result = asyncio.run(TranscriptRewriter(path).rewrite(request()))
    assert result.status == "completed" and result.sentence_id == "session-1"
    assert result.text == "Xin chào bạn."
    headers, body = received[0]
    assert headers["Authorization"] == "Bearer test-private-key"
    assert body["reasoning_effort"] == "low"
    assert body["messages"][0]["content"] == PROMPTS["direct"]
    assert json.loads(body["messages"][1]["content"]) == {"text": "xin chao"}
    assert len(body["messages"]) == 2


def test_openrouter_can_only_use_free_route(gateway):
    path, received, *_ = gateway
    service = TranscriptRewriter(path)
    result = asyncio.run(service.rewrite(request(provider="openrouter")))
    assert result.provider == "openrouter" and result.status == "completed"
    body = received[0][1]
    assert body["model"].endswith(":free")
    assert body["provider"] == {
        "allow_fallbacks": False,
        "max_price": {"prompt": 0, "completion": 0},
    }
    config = json.loads(path.read_text())
    config["providers"]["openrouter"]["model"] = "model-paid"
    path.write_text(json.dumps(config))
    result = asyncio.run(service.rewrite(request(provider="openrouter", sentence_id=None)))
    assert result.status == "unavailable" and len(received) == 1


def test_same_sentence_repeated_or_concurrent_calls_provider_once(gateway):
    path, received, response, entered, release = gateway
    response["block"] = True

    async def exercise():
        service = TranscriptRewriter(path)
        first = asyncio.create_task(service.rewrite(request()))
        assert await asyncio.to_thread(entered.wait, 1)
        second = asyncio.create_task(service.rewrite(request()))
        await asyncio.sleep(0)
        release.set()
        a, b = await asyncio.gather(first, second)
        assert a == b
        assert await service.rewrite(request()) == a
        conflict = await service.rewrite(
            RewriteRequest(text="different", method="recovery", sentence_id="session-1")
        )
        assert conflict.code == "sentence_conflict"

    asyncio.run(exercise())
    assert len(received) == 1


def test_bounded_concurrency_does_not_block_visual_event_loop(gateway):
    path, received, response, entered, release = gateway
    response["block"] = True

    async def exercise():
        service = TranscriptRewriter(path)
        tasks = [
            asyncio.create_task(
                service.rewrite(RewriteRequest(text=str(i), method="recovery", sentence_id=str(i)))
            )
            for i in range(2)
        ]
        assert await asyncio.to_thread(entered.wait, 1)
        third = await asyncio.wait_for(
            service.rewrite(RewriteRequest(text="three", method="recovery")), 0.2
        )
        assert third.code == "busy" and third.text == "three"
        release.set()
        assert all(r.status == "completed" for r in await asyncio.gather(*tasks))

    asyncio.run(exercise())
    assert len(received) == 2


@pytest.mark.parametrize(
    "status,finish,text",
    [(429, "stop", "x"), (401, "stop", "x"), (200, "length", "cut off"), (200, "stop", "")],
)
def test_quota_auth_empty_or_truncated_output_keeps_raw(gateway, status, finish, text):
    path, received, response, *_ = gateway
    response.update(status=status, finish=finish, text=text)
    result = asyncio.run(TranscriptRewriter(path).rewrite(request()))
    assert result.status == "unavailable" and result.text == "xin chao"
    assert len(received) == 1
    if status == 429:
        assert result.code == "rate_limited"


def test_timeout_preserves_raw(gateway):
    path, received, response, _, release = gateway
    response["block"] = True
    result = asyncio.run(TranscriptRewriter(path, timeout=0.5).rewrite(request()))
    release.set()
    assert result.status == "unavailable" and result.text == "xin chao"
    assert len(received) == 1


def test_total_deadline_stops_keepalives_and_releases_capacity(gateway):
    path, received, response, *_ = gateway
    response.update(trickle_count=100, trickle_interval=0.02)

    async def exercise():
        service = TranscriptRewriter(path, timeout=0.5)
        started = time.monotonic()
        result = await service.rewrite(request())
        assert time.monotonic() - started < 1.2
        assert result.code == "timeout" and result.text == "xin chao"
        assert service._active == 0
        # A delayed completion must not rewrite the cached timeout or call again.
        assert await service.rewrite(request()) == result
        response["trickle_count"] = 0
        next_result = await service.rewrite(request(sentence_id="next-sentence"))
        assert next_result.status == "completed"
        assert service._active == 0

    asyncio.run(exercise())
    assert len(received) == 2


def test_visual_empty_and_disabled_never_call_ai(gateway):
    path, received, *_ = gateway
    service = TranscriptRewriter(path)
    assert (
        asyncio.run(service.rewrite(RewriteRequest(text="visual", method="visual"))).status
        == "unchanged"
    )
    assert asyncio.run(service.rewrite(RewriteRequest(text="", method="recovery"))).text == ""
    path.write_text('{"providers":{}}')
    assert asyncio.run(service.rewrite(request())).code == "not_configured"
    assert not received


def test_http_schema_rejects_client_credentials_media_and_retired_modes(monkeypatch, gateway):
    path, received, *_ = gateway
    monkeypatch.setenv("VIETLIP_REWRITE_CONFIG", str(path))
    with TestClient(create_app(engine=MockEngine())) as client:
        for extra in (
            {"api_key": "x"},
            {"endpoint": "https://untrusted"},
            {"video": "x"},
            {"reference": "x"},
        ):
            assert (
                client.post(
                    "/v1/rewrites", json={"text": "x", "method": "recovery", **extra}
                ).status_code
                == 422
            )
        assert (
            client.post(
                "/v1/rewrites", json={"text": "x", "method": "gateway_conservative"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/v1/rewrites", json={"text": "x", "method": "recovery", "provider": "local"}
            ).status_code
            == 422
        )
        assert client.get("/v1/rewrite-methods").json()["phase"] == "per_sentence"
    assert not received


def test_recovery_prompt_matches_existing_benchmark():
    import importlib.util

    path = Path(__file__).parents[2] / "research/llm_rewrite_eval.py"
    spec = importlib.util.spec_from_file_location("frozen_rewrite", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert PROMPTS["direct"] == module.PROMPTS["direct"]


def test_opt_in_trace_records_actual_reply_once_without_credentials(gateway, monkeypatch, tmp_path):
    path, *_ = gateway
    monkeypatch.setenv("LIP_REALTIME_TRACE_DIR", str(tmp_path / "traces"))
    service = TranscriptRewriter(path)

    async def exercise():
        await service.rewrite(request())
        await service.rewrite(request())

    asyncio.run(exercise())
    files = list((tmp_path / "traces").glob("ai-*.jsonl"))
    assert len(files) == 1
    data = files[0].read_text(encoding="utf-8")
    rows = [json.loads(line) for line in data.splitlines()]
    assert len(rows) == 1
    assert rows[0]["source_text"] == "xin chao"
    assert rows[0]["text"] == "Xin chào bạn."
    assert rows[0]["sentence_id"] == "session-1"
    assert "test-private-key" not in data and "Authorization" not in data
    service._trace.close()
