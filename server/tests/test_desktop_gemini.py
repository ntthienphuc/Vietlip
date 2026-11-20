import json
import os

import pytest

from desktop_gemini import configure_gemini, saved_key
from app.services.transcript_rewrite import TranscriptRewriter


@pytest.mark.skipif(os.name != "nt", reason="Windows current-user DPAPI")
def test_installed_gemini_profile_reloads_without_publishing_a_key(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "unrelated-project")
    for name in ("VIETLIP_DESKTOP_GEMINI_KEY", "VIETLIP_REWRITE_CONFIG"):
        monkeypatch.setenv(name, "")
    assert not configure_gemini()
    service = TranscriptRewriter()
    assert not any(row["configured"] for row in service.methods()["providers"])
    legacy = tmp_path / "VietLip" / "api-keys.json"
    legacy.write_text(json.dumps({"groq": "legacy-fixture", "openrouter": "unused"}))
    assert not configure_gemini() and saved_key() == ""
    assert configure_gemini("new-fixture") and saved_key() == "new-fixture"
    assert b"new-fixture" not in (legacy.parent / "gemini.dpapi").read_bytes()
    assert "new-fixture" not in service.path.read_text()
    assert os.environ["VIETLIP_DESKTOP_GEMINI_KEY"] == ""
    provider = json.loads(service.path.read_text())["providers"]["gemini"]
    assert service._key(provider) == "new-fixture"
    assert configure_gemini("replacement-fixture")
    assert service._key(provider) == "replacement-fixture"
    assert [p["id"] for p in service.methods()["providers"] if p["configured"]] == ["gemini"]
    assert json.loads(legacy.read_text())["groq"] == "legacy-fixture"
