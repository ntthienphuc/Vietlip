"""Release behavior: relocation, isolation and accurate readiness."""

import importlib.util
from pathlib import Path

from dataclasses import replace
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.engine import MockEngine

spec = importlib.util.spec_from_file_location(
    "desktop_runtime", Path(__file__).parents[1] / "desktop_runtime.py"
)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def test_default_paths_resolve_inside_actual_server(monkeypatch):
    for key in ("AUTO_AVSR_CHECKPOINT", "AUTO_AVSR_ROOT", "VSR_SPM_MODEL", "VSR_SPM_UNITS"):
        monkeypatch.delenv(key, raising=False)
    root = Path(__file__).resolve().parents[1]
    settings = Settings.from_env()
    assert settings.checkpoint_path == root / "models/SO_seed17.pt"
    assert settings.auto_avsr_root == root / "vendor/auto_avsr"


def test_desktop_uses_bundled_files_and_ignores_experiment_environment(tmp_path, monkeypatch):
    for name in (
        "models/SO_seed17.pt",
        "assets/tokenizers/vi.model",
        "assets/tokenizers/vi_units.txt",
    ):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fixture")
    (tmp_path / "vendor/auto_avsr").mkdir(parents=True)
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    monkeypatch.setattr(runtime.os, "environ", dict(runtime.os.environ))
    monkeypatch.setenv("LIP_EXPERIMENTAL_PHONEME_HEAD", "external.pt")
    monkeypatch.setenv("LIP_EXPERIMENTAL_VISUAL_CONFIRMATION", "external.npz")
    monkeypatch.setenv("LIP_LLM_PROVIDER", "ollama")
    runtime.configure_runtime("cpu")
    settings = Settings.from_env()
    assert settings.checkpoint_path == tmp_path / "models/SO_seed17.pt"
    assert settings.device == "cpu"
    assert settings.llm_provider == "none"
    assert "LIP_EXPERIMENTAL_PHONEME_HEAD" not in runtime.os.environ
    assert "LIP_EXPERIMENTAL_VISUAL_CONFIRMATION" not in runtime.os.environ
    assert settings.realtime_decode_interval_seconds == 1.5


def test_health_does_not_advertise_live_for_unloaded_engine():
    engine = MockEngine()
    engine.loaded = False
    engine.state = "unloaded"
    settings = replace(Settings.from_env(), model_load_on_startup=False)
    with TestClient(create_app(settings=settings, engine=engine)) as client:
        health = client.get("/healthz").json()
    assert health["realtime_available"] is False


def test_warmup_failure_does_not_advertise_readiness(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("warmup fixture")

    monkeypatch.setattr("app.main.prepare_engine", fail)
    settings = replace(Settings.from_env(), model_load_on_startup=True)
    with TestClient(create_app(settings=settings, engine=MockEngine())) as client:
        health = client.get("/healthz").json()
    assert health["status"] == "degraded"
    assert health["realtime_available"] is False
    assert health["last_error"]
