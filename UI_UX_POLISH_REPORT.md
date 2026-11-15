# VietLip 1.8.0 — UI/UX implementation and verification

Completed 15/11/2026 in `E:\Project\Lip_App\lip_reader`.
Android 1.8.0+17; Windows companion remains compatible 1.7.0 / API 1.3.0.

## What changed

- Cobalt and deep blue replace the prior teal/card treatment. Be Vietnam Pro
  provides the Vietnamese typography. Lip contour mark is shared by the header
  and regenerated Android/web/Windows source icons; OFL license is bundled.
- Camera occupies more of the ready screen and uniformly fills its frame.
  Outer-edge cropping replaces black side bands. No rotation/transport change,
  no unequal scaling and no change to the raw frames used for recognition.
  Corner guides keep a portrait face shape. Help explains the visible crop.
- The **Phụ đề trực tiếp** frame stays visible before capture. Large white
  text on deep blue is clearly separated from preview and controls. During live,
  the same panel shows committed/provisional text and a compact meaningful state.
  Full transcript, copy and diagnostics remain available.
- Main control remains pinned and video import is secondary. History adds the
  real saved-session count and clearer rows. Result uses a readable transcript
  surface with an explicit copy action. Settings adds a simple local-connection
  diagram while retaining real address validation and readiness checks.
- Discarding a selected video from an empty completed session returns to the
  ready state. Nonempty captions remain available. Existing persistence and
  delete/export semantics remain intact.

## Main files

| Area | Files |
| --- | --- |
| Visual system | `lib/src/theme/app_theme.dart`, `widgets/app_brand.dart`, `widgets/app_shell.dart`, `widgets/connection_diagram.dart`, `assets/fonts/BeVietnamPro-*` |
| Capture | `camera_viewport.dart`, `capture_camera_panel.dart`, `capture_ready_layout.dart`, `capture_screen.dart`, `live_caption_panel.dart`, `server_connection_banner.dart` |
| Other journeys | `features/settings/settings_screen.dart`, `features/history/history_screen.dart`, `features/result/result_screen.dart` |
| Brand assets | `tools/generate_brand_assets.py`, generated launcher/source icons |
| Separate LLM experiment | `research/llm_rewrite_eval.py`, `docs/LLM_REWRITE_2026-11-15.md` |

Recognition runtime remains SO17 visual-only. No LLM dependency, model selector
or cloud key requirement was added to the installed application. The separate
experiment sends raw text only, scores against hidden references, records API
failures and stops new submissions after a quota response.

## Verified checks

| Check | Actual result |
| --- | --- |
| Flutter analyze | No issues in accepted release log |
| Flutter suite | **35 passed**, including 360/412/800 layouts, large text, long results, history, contracts and export regressions |
| Preview transform | Added a meaningful regression check: cover scales both source axes equally; previous rotation/mirroring tests also pass |
| Real Android update | Signed release installed over the existing app; old history still opens |
| Actual Wi-Fi camera | About 101.4 s; 2520 emitted native frames, about 24.8 fps; mean JPEG encode 9.87 ms; 0 rejected stale timestamps; ready log 30 ms |
| Actual phone captions | Prerecorded scene-4 visual input fed to real SO17; physical Android received and rendered **9/9** caption events, including the final text; 727/727 source-frame ACKs |
| Navigation / copy | Home → settings → history → old result → copy feedback → new capture; working on physical phone |
| Address / recovery | Old saved IP fails truthfully; current PC `192.168.1.9:7100` succeeds through local Wi-Fi; QA address is restored after replay |
| Python research tooling | Ruff check/format pass; local controlled endpoint verifies normalization, reference isolation, quota circuit, raw fallback and request counts |
| Four PC video replays | 134.56 s total, all source frames acknowledged; same inputs reused for each raw/LLM comparison |

The first connection-diagram layout overflowed at 2× text. It was fixed and
the accepted 35-test release passed. Initial raw Flutter commands inherited a
missing D: cache; the established build helper selected valid local caches.
Neither intermediate failure is counted as successful verification.

Server production source was not changed in this pass; the full 98-test server
suite from 1.7.0 was **not rerun**. Current installed-server health and real
SO17 inference were checked. New cloud tests are separate from the app runtime.

## Evidence and limits

All UI evidence starts at `artifacts/ui_refresh_20261115/`:

- `before/phone.png`: actual 1.7.0 baseline.
- `after/home-final.png`, final delivery screenshot: camera/caption frame on ready screen.
- `after/history.png`, `result.png`, `settings-connection.png`: actual journeys.
- `after/live-with-captions.png`, `caption-replay-final.png`: physical display
  with text from prerecorded visual input; not camera recognition of a live person.
- `device-caption-replay/RESULTS.json`: all 9 captions have real Flutter receipts.
- `device-log.txt`: actual unattended-camera transport.
- `android-release-accepted.log`, `layout-final.log`: successful checks.
- Delivery/installed APK hashes and final state are in `DELIVERY_VERIFIED.json`.

Camera transport used an unattended phone pointed at the room. The bridge
test substitutes prerecorded face frames and clearly tags history as
**Kiểm thử phát lại**. These are transport/rendering checks; they do not measure
new live-person WER or acoustic-end-to-display latency. No 2–3 second guarantee
is inferred. No microphone audio was supplied to recognition or the LLM.

For LLM results, the complete eight-sentence comparison, partial 15-sentence
quota-limited run, silence failure and extra latency are documented separately.
The positive replay result is a development diagnostic, not a validated model
upgrade. Raw transcripts and personal recordings stay outside Git/installers.

## Delivery

`output/VietLip-1.8.0/` has two files:

1. `VietLip-1.8.0.apk` — new mobile UI.
2. `VietLip-Windows-1.7.0.zip` — the existing verified, compatible server.

The Windows archive is byte-identical to the prior release; a local NTFS hard
link avoids duplicating its 3.4 GB payload. The internal server/install guide
still names the 1.7.0 release; use the new 1.8.0 APK beside it. An already
installed 1.7.0 server needs no upgrade for this Android build.
