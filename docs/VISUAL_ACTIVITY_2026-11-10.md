# VietLip visual activity: complete-recording check

Follow-up: [frozen complete-caption comparison and physical phone stop receipt](FROZEN_WIFI_CAPTIONS_2026-11-10.md).
The new paired replay confirms suppression of seven inserted units, with
unchanged speech captions, but also exposes a strict-confirmation failure on
short speech fragments. The candidate is still not deployed.

## Latest: all three Wi-Fi source recordings retrieved

VietLip 1.6.2+14 was installed over 1.6.0+12 on the connected Samsung SM-G965F.
All three history entries survived the update. Each recording was exported using
the app's Android document picker to Downloads, then copied over the authorized
ADB connection. Phone/PC SHA-256 hashes match for all three files. This transfer
was over the diagnostic cable, not the LAN upload page. No USB reverse mapping
is present. The installed app's settings page successfully checked the real LAN
server at 192.168.1.19:7100 and displayed its ready state.

| Scene | Saved recording duration | Full H.264 + AAC decode |
| --- | --- | --- |
| 1, seven confirmed sentences | 64.9205 s | Pass |
| 2, four confirmed sentences | 23.159733 s | Pass |
| 3, confirmed no speech | 17.403067 s | Pass |

Local receipt: `artifacts/wifi_live_20261109_round01/device_162/DEVICE_EXPORT_RECEIPT.json`.
Videos and UI observations stay private in that ignored directory.

For the three new clips, inputs were JPEG-encoded at quality 80 and passed through
the actual live activity decoder with max_width=360. This approximates the camera
transport processing; an MP4 cannot reconstruct the original camera JPEG packets.
The current installed motion detector source hash matches the repository.

| Three-scene diagnostic | CNN2Plus1D Light | VVAD LRS3 LSTM |
| --- | --- | --- |
| Complete causal windows scored | 840 | 840 |
| Missed unambiguous speech windows, out of 190 | 0 | 0 |
| False speech on unambiguous quiet windows, out of 319 | 0 | 149 |
| Mixed/boundary windows excluded | 331 | 331 |
| Buffer warmup samples excluded | 39 | 39 |
| Scene 3 false speech windows, out of 132 | 0 | 101 |

Threshold remains 0.5, fixed before this check. These overlapping windows do not
establish a population accuracy percentage. Scene 3 is speaker-confirmed silence;
speech boundaries for scenes 1/2 are offline Silero estimates checked across
0.4/0.5/0.6 thresholds. No audio enters the visual classifiers.

Direct CNN endpoint replacement merges the first two sentences in scene 2;
direct LSTM replacement merges all four. Confirmation-only scoring preserves
all 11 motion turns from scenes 1/2, with confirmation available before each
two-second decode minimum. This still excludes execution/network/display time.

**The original scene-3 live failure has not yet been reproduced by the offline
motion replay:** the saved MP4 gives zero motion turns at this deterministic
sampling phase, whereas the original live trace has two. Therefore the empty
confirmation decision list on that replay cannot be reported as fixing the
12 inserted words. The CNN's negative decisions support further evaluation, not
deployment. Freeze actual live turn/window schedules, measure the source clock
alignment, and compare complete captions before enabling a new live gate.

New outputs: `artifacts/visual_vad_20261110/wifi_scene01_transport_v2`,
`wifi_scene02_transport_v2`, and `wifi_scene03_transport_v2`.
Each has INPUT, SCORES, REPORT and CONFIRMATION JSON. The raw-resolution
scene-3 preliminary trial is retained separately as `wifi_scene03_v1`.

## Earlier complete recordings, original decoded resolution

Two existing phone videos, 50.68 s and 31.28 s (81.96 s total), were decoded at
25 Hz using causal source timestamps. The same 658 complete 38-frame windows
were scored by each PAZ candidate with threshold 0.5, no smoothing, and two CPU
threads. The existing motion detector was replayed at the same 120 ms update
cadence. Unlike the newer transport probes above, this earlier run used original
decoded resolution for motion as well as face crops. Treat its motion timings
as diagnostics, not exact production-pipeline measurements.

| Check | CNN2Plus1D Light | VVAD LRS3 LSTM |
| --- | --- | --- |
| Median classifier call, 7-sentence / 4-sentence video | 61.74 / 61.64 ms | 92.70 / 90.63 ms |
| Misses in 204 unambiguous speech windows | 9 | 16 |
| Positive decisions in 86 unambiguous quiet windows | 0 | 0 |
| Mixed/boundary windows excluded from the above counts | 368 | 368 |
| Warmup samples excluded | 26 | 26 |
| Crop-unavailable samples | 0 | 0 |

These heavily overlapping windows are not independent trials. Reference
boundaries come from prior audio estimates, not frame-level human annotation.
The four-sentence audio VAD includes two short additional regions whose
interpretation has not been verified. The first video's fifth onset is unknown
and excluded from onset metrics. No audio is supplied to either visual model.

## Direct endpoint replacement is not selected

The direct CNN replacement cuts approximately 0.52 s from the first known
speech onset in the seven-sentence clip, and 0.822 s from the corresponding
audio estimate in the four-sentence clip. The original motion pre-roll retains
both beginnings. Other CNN turns also lose some initial frames.

In the seven-sentence clip, the LSTM policy takes 1.18–2.71 s from estimated
speech end to automatic endpoint, before classifier execution, recognition
decoding, network or display cost. The current motion policy takes 1.28–1.66 s
on those six automatic endpoints. The seventh turn ends with session stop and
is not counted as an automatic endpoint. This replacement would consume too
much of the requested 2–3 s total caption budget on several sentences.

## Confirmation while preserving motion boundaries remains a candidate

A second offline policy preserves each original motion start/end and asks for
two consecutive classifier scores at least 0.5, using full windows after the
turn start and decisions available before finalization. Both models confirm all
11 motion turns in the two recordings before the existing two-second minimum
decode window is available. No turn is rejected in this check, and the original
boundaries are retained.

That is evidence against a timing regression for these 11 older turns only. It does
not establish false-positive rejection, correct transcripts, behavior on short
utterances, or actual wall-clock overhead. No candidate has been enabled in live
recognition; newer scene-3 findings are reported above.

## Current connection and required evidence

The installed server and LAN exchange respond at `192.168.1.19:7100` and
`192.168.1.19:7101`. After the user attached the cable, ADB recovered and all
recordings were obtained. The next decisive comparison is confirmation gating
at frozen scene-1/2/3 live windows, plus real-phone final-caption receipt testing.
Check short utterances as well, since the classifier uses 1.52 s of visual history.

Physical inspection also found the settings version label hard-coded to 1.6.0
even with package 1.6.2 installed. Source now reads the Android package version
through a method channel; app version 1.6.3+15 contains this UI fix.

Version 1.6.3+15 was built, installed in place, and its settings label was checked
on the physical phone. Flutter analyze reports no issues, all 29 Flutter tests
pass, and the five experiment protocol checks pass. APK SHA-256:
`d1adcd65cbf110e93626f6ca6021ce881db29517ae43ba97d2eb5712ec6ee354`.
The LAN download at port 7101 serves a byte-identical APK and shows 1.6.3.

A subsequent physical-phone LAN startup/stop check received 554 frames in
23.125 s, reported 24.96 fps near closure, and had no capture timestamp gaps over
500 ms. The app reported WebSocket ready after 73 ms. The server observed the
phone's LAN peer, and ADB had no reverse mapping. This was a ceiling/no-face
connection check, with empty captions and zero attempted recognition windows.
It is excluded from speech accuracy and final nonempty-caption receipt claims.
Evidence: `device_162/SMOKE_PHONE_LAN_RESULT.json`, the corresponding trace,
app log and UI snapshots under the Wi-Fi artifact directory.

## Artifacts and checks

Scripts are in `server/experiments/visual_activity_probe/`. Local private output:

- `artifacts/visual_vad_20261110/full_round03_v1/REPORT_V2.json` and `CONFIRMATION.json`.
- `artifacts/visual_vad_20261110/full_four_sentences_v1/REPORT.json` and `CONFIRMATION.json`.
- `INPUT.json` and `SCORES.json` in both folders retain timestamps, input hashes,
  quality failures, full scores, and per-call runtime.

The earlier first-video `REPORT.json` is retained for provenance; use
`REPORT_V2.json`, which omits unknown-onset latency and distinguishes session
stop from automatic endpoints. The VSR model, live gate, installed server and
APK were not modified during this experiment.
