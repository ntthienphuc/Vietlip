# Application maintenance

Current app: **VietLip 1.6.0**. User connections use local Wi-Fi/LAN. The desktop
server shows its IP; Android accepts an IP or full URL and defaults to port 7100.
The Windows installer bundles Python 3.11, CPU/CUDA dependencies and SO17.
See `PROJECT_MAP.md` and `packaging/windows_server/README.md` for packaging.

Previous architecture notes are preserved in `ARCHITECTURE_1_1_HISTORICAL.md`.

The active product is a Flutter Android capture client and a Python inference
server. Android is verified on SM-G965F / Android 10. iOS project files exist;
the current release has not been built or validated on an iPhone.

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

Paths in the first three capture rows are relative to the capture feature folder;
server service rows are relative to `server/app/services`.

## Maintenance boundaries

- `server/app` is production runtime code; `server/experiments` contains optional
  trials. Phoneme and LLM experiments are disabled in the standard launcher.
- `server/vendor` and `packages/camera_android_camerax` retain upstream notices.
  Format application code without mass-editing vendor code.
- Models, recordings, signing credentials and generated reports remain local.
  Never modify model hardlinks in place. A fresh checkout requires the separately
  supplied checkpoint; `tools/import_model.ps1` validates its manifest hash.
- Video audio is for reference only. Live inference consumes JPEG frames.
- A post-frame acknowledgement measures Flutter delivery plus return transport;
  it does not measure physical screen scanout or human-labeled speech end.
- Keep protocol 2 / API 1.2.0 compatible independently of the app version.

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
