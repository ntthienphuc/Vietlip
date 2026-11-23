"""Text-only sentence recovery, independent of the visual inference worker."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import time
from typing import Literal

from fastapi import APIRouter
import httpx
from pydantic import BaseModel, ConfigDict, Field
from .live_trace import LiveTrace
from . import gemini
from ..version import APP_VERSION

Method = Literal["visual", "recovery"]
Provider = Literal["gemini"]


class RewriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=4000)
    method: Method
    provider: Provider = "gemini"
    sentence_id: str | None = Field(default=None, max_length=120)


class RewriteResponse(BaseModel):
    method: Method
    provider: Provider = "gemini"
    sentence_id: str | None = None
    text: str
    status: Literal["completed", "unchanged", "unavailable"]
    model_id: str | None = None
    elapsed_ms: int = 0
    message: str | None = None
    code: str | None = None


def configuration_path() -> Path:
    explicit = os.getenv("VIETLIP_REWRITE_CONFIG")
    if explicit:
        return Path(explicit)
    return Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "VietLip" / "rewrite.json"


class TranscriptRewriter:
    def __init__(self, path: Path | None = None, *, timeout: float = 12):
        self.path = path or configuration_path()
        self.timeout = timeout
        self._active = 0
        self._billing_retry_at = 0.0
        self._requests: dict[tuple[str, str], tuple[str, float, asyncio.Task]] = {}
        self._trace = LiveTrace(prefix="ai")

    def _providers(self) -> dict:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8-sig"))
            providers = payload.get("providers", {})
            return providers if isinstance(providers, dict) else {}
        except (OSError, ValueError, AttributeError):
            return {}

    @staticmethod
    def _configured(provider) -> bool:
        return (isinstance(provider, dict) and provider.get("enabled", True) is True
                and isinstance(provider.get("model"), str) and provider["model"] in gemini.THINKING)

    def methods(self) -> dict:
        provider = self._providers().get("gemini")
        configured = self._configured(provider)
        available = [{"id": "gemini", "configured": configured,
                      "model_id": provider["model"] if configured else ""}]
        return {
            "default_method": "visual",
            "default_provider": "gemini",
            "phase": "per_sentence",
            "methods": [
                {"id": "visual", "configured": True},
                {"id": "recovery", "configured": any(p["configured"] for p in available)},
            ],
            "providers": available,
        }

    async def rewrite(self, request: RewriteRequest) -> RewriteResponse:
        base = dict(
            method=request.method,
            provider=request.provider,
            sentence_id=request.sentence_id,
            text=request.text,
        )
        if request.method == "visual" or not request.text.strip():
            return RewriteResponse(**base, status="unchanged")
        now = time.monotonic()
        self._requests = {
            key: row
            for key, row in self._requests.items()
            if not row[2].done() or now - row[1] < 300
        }
        key = (request.provider, request.sentence_id) if request.sentence_id else None
        if key in self._requests:
            text, _, task = self._requests[key]
            if text != request.text:
                return RewriteResponse(
                    **base,
                    status="unavailable",
                    code="sentence_conflict",
                    message="Mã câu đã được dùng. Bản gốc vẫn được giữ lại.",
                )
            return await asyncio.shield(task)
        provider = self._providers().get(request.provider)
        if not self._configured(provider):
            return RewriteResponse(
                **base,
                status="unavailable",
                code="not_configured",
                message="Dịch vụ AI này chưa được cấu hình trên máy tính.",
            )
        if now < self._billing_retry_at:
            return RewriteResponse(**base, status="unavailable", code="billing_required",
                                   message="Project Gemini đã hết tín dụng. Kiểm tra Google AI Studio trên PC.")
        if self._active >= 2:
            return RewriteResponse(
                **base,
                status="unavailable",
                code="busy",
                message="AI đang bận. Câu gốc đã được giữ lại.",
            )
        self._active += 1

        async def run():
            started = time.monotonic()
            try:
                try:
                    # A socket read timeout resets when a provider sends a keepalive.
                    # Bound the whole async HTTP operation and cancel its transport.
                    result = await asyncio.wait_for(
                        self._request(request, provider), timeout=self.timeout
                    )
                except TimeoutError:
                    result = RewriteResponse(
                        **base,
                        status="unavailable",
                        code="timeout",
                        message="AI phản hồi chậm. Câu gốc đã được giữ lại.",
                        elapsed_ms=round((time.monotonic() - started) * 1000),
                    )
                self._trace.record(
                    dict(type="ai_rewrite", source_text=request.text, **result.model_dump())
                )
                return result
            finally:
                self._active -= 1

        task = asyncio.create_task(run())
        if key:
            while len(self._requests) >= 128:
                oldest = next((k for k, r in self._requests.items() if r[2].done()), None)
                if oldest is None:
                    break
                del self._requests[oldest]
            self._requests[key] = (request.text, now, task)
        return await asyncio.shield(task)

    @staticmethod
    def _key(provider: dict) -> str:
        if provider.get("credential_store") == "windows_dpapi":
            from desktop_gemini import saved_key
            return saved_key()
        if provider.get("api_key_file"):
            path = Path(provider["api_key_file"])
            values = json.loads(path.read_text(encoding="utf-8-sig"))
            return str(values.get(provider.get("api_key_name", ""), ""))
        return provider.get("api_key") or os.getenv(provider.get("api_key_env", ""), "")

    async def _request(self, request: RewriteRequest, provider: dict) -> RewriteResponse:
        start = time.monotonic()
        base = dict(
            method=request.method,
            provider=request.provider,
            sentence_id=request.sentence_id,
            text=request.text,
        )
        code = "provider_error"
        message = "AI chưa hoàn tất. Câu gốc đã được giữ lại."
        try:
            model = provider["model"]
            payload = gemini.payload(request.text, model)
            endpoint = f"{gemini.API_ROOT}/{model}:generateContent"
            headers = {"Content-Type": "application/json", "User-Agent": f"VietLip/{APP_VERSION}"}
            key = self._key(provider)
            if not key:
                return RewriteResponse(**base, status="unavailable", code="not_configured",
                                       message="Thêm key Gemini trong VietLip Server trên PC.")
            headers["x-goog-api-key"] = key
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                async with client.stream(
                    "POST", endpoint, headers=headers, json=payload
                ) as response:
                    response.raise_for_status()
                    response_bytes = bytearray()
                    async for chunk in response.aiter_bytes():
                        response_bytes.extend(chunk)
                        if len(response_bytes) > 256 * 1024:
                            raise ValueError("oversized response")
                result = json.loads(response_bytes)
            text = gemini.response_text(result)
            return RewriteResponse(
                **{**base, "text": text},
                status="unchanged" if text == request.text else "completed",
                model_id=str(result.get("modelVersion") or model),
                elapsed_ms=round((time.monotonic() - start) * 1000),
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 402:
                self._billing_retry_at = time.monotonic() + 60
                code = "billing_required"
                message = "Project Gemini đã hết tín dụng. Kiểm tra Google AI Studio trên PC."
            elif error.response.status_code == 429:
                code, message = (
                    "rate_limited",
                    "AI đã chạm hạn mức. Câu gốc vẫn hiển thị; hãy thử lại sau.",
                )
            elif error.response.status_code in (401, 403):
                code, message = (
                    "access_denied",
                    "Dịch vụ AI từ chối truy cập. Kiểm tra key và quyền model trên PC.",
                )
        except (TimeoutError, httpx.TimeoutException):
            code, message = "timeout", "AI phản hồi chậm. Câu gốc đã được giữ lại."
        except (httpx.RequestError, OSError, ValueError, TypeError, KeyError, IndexError):
            pass
        return RewriteResponse(
            **base,
            status="unavailable",
            code=code,
            message=message,
            elapsed_ms=round((time.monotonic() - start) * 1000),
        )


def rewrite_router(service: TranscriptRewriter) -> APIRouter:
    router = APIRouter()

    @router.get("/v1/rewrite-methods")
    async def methods():
        return service.methods()

    @router.post("/v1/rewrites", response_model=RewriteResponse)
    async def rewrite(request: RewriteRequest):
        return await service.rewrite(request)

    return router
