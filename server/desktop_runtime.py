"""Relocatable, visual-only defaults for the Windows companion application."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import urllib.request

APP_NAME = "VietLip Server"
APP_VERSION = "1.7.0"
ROOT = Path(__file__).resolve().parent


def configure_runtime(device: str = "auto", trace_directory: str = "") -> None:
    # The packaged application has one supported profile. A research shell's
    # experimental switches must never silently change the installed model.
    for key in list(os.environ):
        if key.startswith(("LIP_", "AUTO_AVSR_", "VSR_SPM_")):
            del os.environ[key]
    values = {
        "LIP_MODEL_BACKEND": "native_avsr",
        "LIP_MODEL_ID": "auto-avsr-vi-so_seed17",
        "LIP_MODEL_LOAD_ON_STARTUP": "true",
        "LIP_STARTUP_WARMUP": "1",
        "LIP_DEVICE": device,
        "LIP_PRECISION": "float32",
        "LIP_ALLOW_CPU_FALLBACK": "true",
        "LIP_CPU_THREADS": "4",
        "LIP_REALTIME_SAMPLE_FPS": "25",
        "LIP_REALTIME_WINDOW_SECONDS": "6",
        "LIP_REALTIME_OVERLAP_SECONDS": "1",
        "LIP_REALTIME_DECODE_INTERVAL_SECONDS": "1.5",
        "LIP_REALTIME_DECODER": "beam",
        "LIP_REALTIME_BEAM_SIZE": "3",
        "LIP_CTC_WEIGHT": "0.1",
        "AUTO_AVSR_CHECKPOINT": str(ROOT / "models" / "SO_seed17.pt"),
        "AUTO_AVSR_ROOT": str(ROOT / "vendor" / "auto_avsr"),
        "VSR_SPM_MODEL": str(ROOT / "assets" / "tokenizers" / "vi.model"),
        "VSR_SPM_UNITS": str(ROOT / "assets" / "tokenizers" / "vi_units.txt"),
    }
    for key in ("AUTO_AVSR_CHECKPOINT", "AUTO_AVSR_ROOT", "VSR_SPM_MODEL", "VSR_SPM_UNITS"):
        if not Path(values[key]).exists():
            raise FileNotFoundError(f"Thiếu thành phần bộ cài: {values[key]}")
    if trace_directory:
        values["LIP_REALTIME_TRACE_DIR"] = str(Path(trace_directory).resolve())
    os.environ.update(values)


def data_dir() -> Path:
    target = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "VietLip" / "logs"
    target.mkdir(parents=True, exist_ok=True)
    return target


def read_health(port: int, timeout: float = 0.8) -> dict | None:
    try:
        # Local health must not be sent through a configured HTTP proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/healthz", timeout=timeout) as response:
            data = json.load(response)
        return data if data.get("service") == "lip-reader-api" else None
    except (OSError, ValueError):
        return None


def port_available(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def local_ipv4() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("192.0.2.1", 80))
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def local_addresses(port: int) -> list[str]:
    import ipaddress

    preferred = local_ipv4()
    candidates = [preferred]
    try:
        candidates.extend(
            item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        )
    except OSError:
        pass
    addresses = []
    for value in candidates:
        ip = ipaddress.ip_address(value)
        url = f"http://{ip}:{port}"
        if ip.is_private and not ip.is_loopback and not ip.is_link_local and url not in addresses:
            addresses.append(url)
    return addresses
