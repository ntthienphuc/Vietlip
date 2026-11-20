"""Gemini credentials belong to the Windows user running the server."""

import json
import os

from app.services.gemini import DEFAULT_MODEL
from desktop_secrets import _folder, _windows_protect, _write


def saved_key():
    secret = _folder() / "gemini.dpapi"
    if secret.exists():
        try:
            return _windows_protect(secret.read_bytes(), decrypt=True).decode()
        except (OSError, ValueError):
            return ""
    return ""


def configure_gemini(key=None):
    if key is None:
        key = saved_key()
    else:
        key = key.strip()
        if not key or not key.isascii() or not key.isprintable() or any(c.isspace() for c in key):
            raise ValueError("Key Gemini không hợp lệ.")
        _write(_folder() / "gemini.dpapi", _windows_protect(key.encode()))
    config = _folder() / "desktop-gemini-profile.json"
    provider = {"model": DEFAULT_MODEL, "enabled": bool(key), "credential_store": "windows_dpapi"}
    _write(config, json.dumps({"providers": {"gemini": provider}}, indent=2).encode())
    os.environ["VIETLIP_REWRITE_CONFIG"] = str(config)
    return bool(key)
