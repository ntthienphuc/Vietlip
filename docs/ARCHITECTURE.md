# VietLip architecture

The Android client and Windows launcher ship as **VietLip 1.10.5**. The visual
backend reports **1.10.1** in `/healthz`. The desktop launcher shows a pairing QR
code and a LAN address. Android also accepts a manually entered address.
The Windows installer bundles Python 3.11, CPU/CUDA dependencies and SO17.
See the [build guide](BUILD.md) and [Windows packaging notes](../packaging/windows_server/README.md).

The active product is a Flutter Android capture client and a Python inference
server. Android has been verified on SM-G965F / Android 10.

## Runtime responsibilities

| Area | Entry point | Responsibility |
| --- | --- | --- |
| Capture lifecycle | `lib/src/features/capture/capture_screen.dart` | Camera permissions, recording, live connection, saving results |
| Camera presentation | `capture_camera_panel.dart`, `camera_viewport.dart` | Actual CameraX surface rotation/crop/mirror, uniform fit, image-aligned guide |
| Live layout | `live_capture_layout.dart`, `live_caption_panel.dart` | Large preview/captions, accessible scrolling, provisional text, full transcript |
| App navigation | `lib/src/widgets/app_shell.dart` | Hide bottom navigation during live, release camera when leaving capture |
| Transport | `lib/src/data/live_lip_session.dart` | Bounded frames, timeouts, monotonic timestamps, caption render receipts |
| Android image path | `FrameEncoder.kt`, local CameraX package | JPEG outside Dart; camera and websocket acknowledgements are separate |
| HTTP jobs / WS dispatch | `server/app/main.py` | Input validation, one inference semaphore, bounded job queue |
| Startup | `server/app/services/startup.py` | Prepare model, kernels and visual activity runtime before capture |
| Windows companion | `server/desktop_launcher.py`, `desktop_runtime.py` | Show LAN IP, readiness, bounded logs and isolate the installed model profile |
| Automatic sessions | `auto_stream.py`, `visual_activity.py` | Visual onset/pause, pre-roll, bounded pending turns |
| Recognition | `native_engine.py`, `incremental_decoder.py`, `cpu_ctc_prefix.py` | SO17 visual encoder/decoder and cached search |
| Caption stability | `caption_stability.py`, `word_alignment.py` | Word ownership and agreement across overlapping windows |
| Diagnostics | `caption_delivery.py`, `live_trace.py`, `live_evidence.py` | Size-bounded local traces, delivery timing, explicit unavailable spans |
| Optional sentence suggestions | `transcript_rewrite.py`, `gemini.py`, `lib/src/data/transcript_review.dart` | Send finalized text to Gemini and attach its suggestion to the original caption in session history |

Paths in the first three capture rows are relative to the capture feature folder;
server service rows are relative to `server/app/services`.

## Maintenance boundaries

- Live recognition uses SO17 visual inference. Version 1.10.5 requests
  Gemini suggestions independently of visual inference and caption delivery.
  Legacy assisted metadata is retained but is not shown as a newly generated review.
- `server/vendor` and `packages/camera_android_camerax` retain upstream notices.
  Format application code without mass-editing vendor code.
- The SO17 checkpoint is a public release asset. The [download script](../tools/get_so17.ps1)
  verifies its SHA-256 digest before placing it in the checkout. Keep model
  hardlinks read-only. Recordings and signing credentials are managed outside Git.
- Video audio is for reference only. Live inference consumes JPEG frames.
- A post-frame acknowledgement measures Flutter delivery plus return transport;
  it does not measure physical screen scanout or human-labeled speech end.
- Keep protocol 2 compatible independently of the app version. API 1.5.0 retains
  upload/job/WS routes and accepts only visual_only mode. Old assisted-mode
  submissions are rejected explicitly instead of silently rewriting text.
- `/v1/rewrite-methods` exposes only configured method IDs; `/v1/rewrites` accepts
  text and a fixed method ID. The Windows launcher manages the Gemini key.
  See [caption and suggestion behavior](LIVE_AI_1_10.md).

## Checks

```powershell
flutter analyze
flutter test
cd server
.\.venv\Scripts\python.exe -m ruff check app
.\.venv\Scripts\python.exe -m ruff format --check app
.\.venv\Scripts\python.exe -m pytest -q
```

`server/requirements-dev.txt` pins the formatter. The Android build wrapper
resolves local Pub/Gradle caches, runs Flutter checks, then builds the APK.
Use `tools/sign_device_apk.ps1` to update the existing internal installation
without deleting app data; keys and DPAPI credentials are never in Git.

Fixed-window model comparisons and true automatic device replays answer different
questions. Preserve both protocols and their inputs when investigating regressions.
