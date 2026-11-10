import asyncio
import httpx
from app.services.candidate_selector import CandidateSelector


def test_selector_times_out_and_retains_exact_visual_text(monkeypatch):
    async def delayed(*args, **kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(httpx.AsyncClient, "post", delayed)
    selector = CandidateSelector("http://localhost:7110/v1", "test", 0.02)
    result = asyncio.run(selector.select(["không được uống thuốc", "được uống thuốc"]))
    assert result.status == "timeout_fallback"
    assert result.text == "không được uống thuốc"
    assert result.elapsed_ms < 300


def test_selector_rejects_generated_text_or_invalid_index(monkeypatch):
    async def response(*args, **kwargs):
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://local"),
            json={"choices": [{"message": {"content": '{"id":true,"text":"invented"}'}}]},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", response)
    selector = CandidateSelector("http://localhost:7110/v1", "test")
    result = asyncio.run(selector.select(["tôi không đi", "tôi đi"]))
    assert result.status == "invalid_fallback" and result.text == "tôi không đi"
