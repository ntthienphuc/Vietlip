# VietLip inference server

The Windows service receives JPEG frames from the Android client, detects speech activity from visible movement, and streams Vietnamese captions back over the same WebSocket. The desktop launcher manages the SO17 runtime, LAN pairing, and optional Gemini credentials.

## Start from source

From the repository root on Windows, with Python 3.11 x64 installed:

```powershell
.\tools\get_so17.ps1
.\server\setup_server.ps1 -Runtime cpu
.\server\.venv\Scripts\python.exe .\server\desktop_launcher.py
```

The launcher displays a QR code once the server is ready. For console operation, add `--headless`; the default port is 7100. See the [build guide](../docs/BUILD.md) for GPU setup, packaging, and tests.

## Runtime interfaces

| Interface | Purpose |
| --- | --- |
| `GET /healthz` | Inspect model readiness, runtime device, and live recognition availability. |
| `WS /v1/realtime` | Send visual frames and receive updates for the active capture session. |
| `GET /v1/rewrite-methods` | List configured sentence suggestion methods. |
| `POST /v1/rewrites` | Request a text suggestion for a finalized caption. |

The desktop profile selects SO17 FP32, beam size 3, and CTC weight 0.1. Recognition runs locally. When enabled, Gemini receives finalized caption text from the PC. Windows protects the user’s saved key with DPAPI. For a source build, paste your own key in **Cài đặt key Gemini**. The privately supplied Windows installer provisions a key on first install. The client stores the visual caption and suggestion separately.

[Runtime configuration](desktop_runtime.py) · [API entry point](app/main.py) · [Streaming architecture](../docs/ARCHITECTURE.md)

Older command-line adapters and experimental configurations are documented in the [historical server notes](README_LEGACY.md).
