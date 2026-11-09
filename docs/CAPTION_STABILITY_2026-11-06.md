# Caption stability after the second human test

Work remains in Lip_App/lip_reader. Original device captures were copied via
ADB run-as and SHA-256 verified; no originals were edited or deleted.
Evidence is under artifacts/device_s9_20261106/round02/.

## Observed result and diagnosis

The participant confirmed reading the five prompted sentences and reported
words sometimes becoming incorrect in a subsequent window. The final physical
phone transcript has 21/44 whitespace-word edits (WER 47.73%). This is a small
prompted application test, not an independent accuracy benchmark. The app had
not persisted its intermediate messages, so the exact original sequence of
visible revisions cannot be recovered. SOURCE_RECEIPTS.json and HISTORY.json
preserve the original video provenance and final caption.

The 36-second saved video was replayed at 25 fps through the actual WebSocket
server. It produced five visual_pause endpoints. On this compressed-video
replay, the original policy erased/replaced six displayed suffix tokens and
had 29/44 word errors. For example, the first early guess, `không thay đổi`,
became a committed `không` plus a later `ôm lấy...` guess. Time-only ownership
committed an early unstable word and combined incompatible hypotheses.

## Implemented behavior

AgreementTimeline waits for a matching prefix in two distinct successive
windows, still respecting one second of right context. Reprocessing an
identical cached window does not count as a second vote. Already displayed
words are append-only. Single-pass guesses remain in diagnostic events instead
of appearing as a changing main caption. At an automatic endpoint, the last
decode finalizes the remaining words. If a long utterance exceeds the rolling
buffer, unresolved words whose timestamp centers have left the new window are
preserved from the previous decode; this fallback is separately counted and
does not claim agreement or correctness. Decode failures discard unshown words
without removing committed text or leaking an old guess into the next turn.

The mobile empty state now says it is reading lip movements while speech is
active. It no longer describes underlined draft text when none is displayed.
The camera aspect-ratio/orientation fix from 1.4.1 remains.

The policy is an adaptation of local agreement from
[Whisper-Streaming](https://github.com/ufal/whisper_streaming), described in
[Machacek et al., 2023](https://aclanthology.org/2023.ijcnlp-demo.3/).
That work concerns audio ASR; its accuracy/latency results are not evidence
for this visual-only application. No audio, LLM or reference sentence is used
by the implemented policy.

## Paired comparison on identical model outputs

| Saved stream | Old word errors | New word errors | Old removed suffix tokens | New |
|---|---:|---:|---:|---:|
| Latest 5-sentence replay, 44 words | 29 | 26 | 6 | 0 |
| Previous human replay, 24 words | 14 | 14 | 1 | 0 |
| Same previous clip plus frozen tail, 24 words | 14 | 14 | 2 | 0 |
| Existing face-video concatenation, 99 words | 34 | 36 | 16 | 0 |
| Existing ROI concatenation, 599 words | 401 | 401 | 148 | 0 |

The previous clip and its padded version are not independent samples. The
larger existing corpora retain their earlier provenance/scope limitations.
Do not pool these into a general accuracy claim. Removing visible revisions
is a deliberate display policy, not evidence that the frozen words are right.
There is a 2-word accuracy regression on the face-video concatenation.

## New end-to-end replay

The changed server replayed the same latest video: 25/44 errors (WER 56.82%),
zero removed visible tokens, five automatic endpoints, 900 sent frames and no
sender drops. Relative to the detector's estimated speech ends, final events
were sent after 1.838, 1.526, 1.564, 1.683 and 1.757 seconds. These are server
caption availability times, not hand-labeled speech-end-to-phone-paint latency.
Some uncertain phrases now appear only at their endpoint rather than as early
changing guesses; the first phrase was such a case.

Scheduling changes affect window contents in separate replays. Applying both
policies to the new replay's identical raw hypotheses gives 28 versus 25 word
errors. This paired result and the paired 29 versus 26 result above isolate
the stitching change better than comparing two live replay runs. Neither
replay replaces the original physical-phone WER of 47.73%.

## Verification and follow-up evidence

Server suite: 56 tests passed before the final failure-reset refinement;
14 targeted tests passed after that refinement, including the new regression.
Flutter suite: 15 tests passed; analyze reported no issues. The Android profile
build is version 1.4.2+7. Delivery receipt records its actual installation check.

The local server now runs with an explicit LIP_REALTIME_TRACE_DIR. It records
sent caption/activity events, raw window hypotheses, displayed text and server
timestamps to unique local JSONL files, capped at 4 MiB per session. No camera
frames or audio are written by this trace. This makes future revisions
inspectable; it is not a background phone-screen observer and does not measure
actual phone paint time. Trace logging is optional outside this test launcher.

Artifacts: ROUND02_RESULTS.json, STABILITY_ABLATION_FINAL.json,
BASELINE_REPLAY.json, AFTER_REPLAY.json, AFTER_PAIRED.json, live_traces/,
server-all-tests.log, server-final-targeted-tests.log, flutter-tests.log,
build-1.4.2-final.log, and DELIVERY_RECEIPT.json.

## Installed-device check

Installed the signed 1.4.2+7 APK in place on SM-G965F; package version verified.
Started and stopped live over the saved LAN server. The preview remained
upright/proportional and the UI showed 25 fps. The 55.286-second check sent
1,359 encoded frames (24.58 fps), mean encode 12.11 ms. Camera faced the room,
so no speech was expected: server trace recorded zero attempted windows,
empty final caption, 1,361 received frames and zero capture gaps. The ready
event confirms local_agreement_2. Stopped capture and left the app ready.

Signed APK SHA-256:
307aed6a4d7411616c4fa220828153195bfb0ae4f8b017cefa365af322fa20be.

Device evidence: device-live.png, device-final-ready.png, device-final.log,
device-ready.xml, device-stopped.xml and
live_traces/live-83440362ca5a40d08336c3f8211cf464.jsonl. New human speech accuracy
on installed 1.4.2 remains to be tested by the participant.
