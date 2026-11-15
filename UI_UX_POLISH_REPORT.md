# VietLip 1.7.0 — UI/UX polish

Completed on 15/11/2026 in `E:\Project\Lip_App\lip_reader`.

## What changed

- **A permanent caption destination on the main screen.** Preview and the
  “Phụ đề trực tiếp” frame are visible together before starting. The empty frame
  explains the next action. Live captions use the same component below the
  preview; ending the session retains the received text. Compact screens and
  enlarged text can scroll while the primary control stays reachable.
- **Clear action hierarchy.** A large “Bắt đầu đọc môi” / “Kết thúc phiên” button,
  compact video-import control, consistent help and a real server-readiness row.
  Portrait fitting/rotation and image-aligned guide are preserved.
- **One visual recognition flow.** Removed mode selection, context field,
  LLM consent, assisted transcript presentation, LLM HTTP/provider factory and
  launch scripts. The native decoder no longer loads/reorders with a phoneme
  head. SO17 and the normal visual sliding-window/endpointing profile remain.
  Legacy history metadata still round-trips without displaying assisted text.
- **Settings with recovery.** Address validation beside the field, stale success
  cleared on edit, bounded network check, disabled duplicate actions, truthful
  preparing/error/ready states, direct return to capture. Tips/privacy details
  are expandable rather than a long initial checklist.
- **Transcript-first review.** Large readable text, specific copy feedback,
  video export, technical details behind disclosure. Live duration is labeled
  “Thời lượng phiên”, separately from batch processing time.
- **History that can recover.** A failed read has a retry state; pull-to-refresh
  awaits the load. Empty state gives a starting action. Clear-history confirmation
  explains that video is retained; destructive semantics are unchanged.
- **One visual system.** Teal, solid brand mark, actual shipped Nunito weights
  400–700, consistent surfaces and spacing, darker warning text, 48+ touch
  targets, readable status labels, scrollable details sheets. Reduced-motion
  preference disables the automatic video-reveal scroll animation.
- **Windows companion.** Larger address field, explicit readiness, secondary
  logs collapsed by default, copy/refresh actions, resize-aware wrapping and
  footer reservation. Three missed health polls replace stale readiness with
  a recovery message. Upgrade removes the retired LLM modules/bytecode only
  within the app's installation folder; new installer excludes bytecode caches.

## Components and contracts

| Files | Responsibility |
| --- | --- |
| `lib/src/features/capture/capture_screen.dart` | One supported flow, persistent controls and captions |
| `capture_ready_layout.dart`, `live_capture_layout.dart` | Adaptive preview/caption layout before/during capture |
| `live_caption_panel.dart`, `server_connection_banner.dart` | Idle/live states, real readiness, readable captions |
| `lib/src/features/settings/settings_screen.dart` | Validation, connection/recovery, disclosure |
| `lib/src/features/history/history_screen.dart` | Retry, refresh, clearer history presentation |
| `lib/src/features/result/*` | Visual transcript, copy, export and correct timing labels |
| `lib/src/theme/app_theme.dart`, `lib/src/widgets/*` | Shared typography, color, touch targets, notices |
| `lib/src/data/lip_reader_api.dart` | Visual-only upload, five-second connection timeout, clearer errors |
| `server/app/main.py`, `config.py`, `schemas.py`, `services/native_engine.py` | Remove LLM runtime and native phoneme rescoring |
| `server/desktop_launcher.py`, `desktop_runtime.py` | Windows UI, readiness and isolated profile |
| `packaging/windows_server/*`, `.env.example` | Rebuildable single-profile 1.7.0 installer and safe upgrade cleanup |
| `test/*`, `server/tests/*`, Android QA helpers | Regression/contract/layout checks and real-device evidence |

`/read`, `/history`, `/settings`, `/result`, upload/job/WS URLs and local history
key remain. Protocol 2 is retained. API 1.3.0 deliberately accepts only
`mode=visual_only`; retired assisted modes return an explicit 422 error.
Reserved response/history metadata is retained for older data readers. Research
records and prior model evaluations are historical evidence, not product modes.

## Verification actually performed

| Check | Result/evidence |
| --- | --- |
| Flutter analyze | No issues in final signed-build log |
| Flutter tests | **34 passed**; includes legacy history, stale responses, input errors, retry, long content, 360/412/800 layouts and text scales through 2 |
| Main caption placement | Extra layout check asserts the idle caption frame is above the primary control at normal text size; real phone screenshot confirms it |
| Server tests | **98 passed, 9 skipped**; skips are optional offline vPhon research dependency, not active app inference |
| Ruff | Check passed; 48 Python files already formatted |
| Android signed release | Built; updated installed SM-G965F / Android 10 without clearing app data; existing history opened |
| Wi-Fi capture | Two start/stop cycles on QA port 7103: 24–25 fps; application handshake logs 60–75 ms. The final installed-server cycle on port 7100 reached 25 fps and logged a 172 ms handshake |
| Connection error/recovery | Real phone: closed port 7104 shows actionable error; restoring installed server at 7100 reports ready |
| Copy/history | Real saved record opens; copy confirmation observed; original entries retained after APK updates |
| Export | Android picker cancellation recovers; actual save to Downloads succeeded as `VietLip_UI_QA_20261115.mp4` (5,169,358 bytes); local readback decoded a frame and measured 306 frames at 30.05 fps |
| Windows installer | Compile succeeded; silent upgrade exit 0; no restart needed |
| Installed runtime | **11,922 payload files verified, zero failures**; SO17 ready on CUDA/float32; removed LLM modules and bytecode absent |
| Two-file delivery | Every source hash checked; every ZIP entry read back and SHA-256 verified; receipt includes final APK/ZIP hashes |

An early Python run exhausted Windows commit memory while two server processes
and Android compilation were concurrent. The old audit server was closed and
the complete server suite passed on retry. Final payload verification was run
after the installer completed; intermediate checks during installation are not
release evidence.

## Screenshots and receipts

Evidence is local and gitignored because history/camera images can be personal.

- Before: `artifacts/ui_polish_20261115/before/`.
- Final main screen: `after/HOME_FINAL.png` (caption visible before starting,
  installed server on 7100); `after/capture-caption-verified.png` is the first
  confirmed caption-frame screenshot.
- Settings: `after/settings-final-state.png`, `settings-bad-result.png`,
  `settings-recovery-check.png`.
- Review/history: `after/result-final.png`, `history-final.png`.
- Actual live UI/logs: `device-live/`, `device-final-live/`.
- Checks: `android-caption-frame-release.log`, `server-test-final.log`,
  `caption-layout-acceptance.log`, `installed-verify-final.log`,
  `installed-health.json`, `install.log`, `delivery-receipt-final.json`, `ACCEPTANCE.json`
  and `export-verification.json`.

All relative evidence paths above start at `artifacts/ui_polish_20261115/`.
Windows readiness/layout was inspected in the running native window using
computer-use; no third-party design audit executables were installed or run.

## Delivery and limits

`output/VietLip-1.7.0/` contains exactly:

1. `VietLip-1.7.0.apk`
2. `VietLip-Windows-1.7.0.zip`

The ZIP contains the Windows installer, its two BIN payloads, instructions and
checksums. Extract all files before running Setup. Android and Windows were
updated locally for verification.

Live hardware checks used an unattended camera without a speaking face. They
verify transport, layout and lifecycle; they do **not** establish a new WER/CER
or speech-end-to-caption latency. SO17's known free-speech accuracy limits
remain; 2–3 seconds is not guaranteed by this UI release. No iPhone build,
TalkBack certification, full external-keyboard audit or blanket WCAG compliance
is claimed. Broad improvements to model accuracy require separate paired
video/reference evaluation.
