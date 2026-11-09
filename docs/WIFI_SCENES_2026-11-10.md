# VietLip: Wi-Fi scenes 2 and 3, 2026-11-10

The speaker confirmed scene 2 contained exactly the four scripted sentences,
and scene 3 contained no speech. The production profile remained SO17 float32,
beam 3, CTC 0.1, a six-second window, and one-second visual endpoint debounce.
No model or decoder was changed between these recordings.

| Measure | Scene 2: connected speech | Scene 3: no speech |
| --- | --- | --- |
| Session duration | 24.204 s | 18.328 s |
| Received frames | 585 | 439 |
| FPS at caption events | 24.96–25.04 | 25.04 |
| Capture timestamp gaps over 500 ms | 1 | 0 |
| Automatic segments | 3 for 4 sentences | 2 false activations |
| Render receipts | 11/12 | 4/4 |
| Final whitespace-unit WER | 18/40 = 45.00% | Undefined: empty reference |
| CER excluding spaces | 43/132 = 32.58% | Undefined: empty reference |
| Inserted units with no speech | Not applicable | 12 |
| First nonempty caption receipt from session start | 10.079 s | 9.078 s |
| Final window end to render receipt | 2.058–2.097 s, 2 of 3 finals | 1.611–1.804 s |
| Visible prefix revisions | 0 | 0 |

The two initial sentences in scene 2 were merged into the first detected turn.
Do not zip detected turns to reference sentences when scoring. The session-wide
edit distance is valid; sentence-level timing needs the source recording.
The one capture gap was already present at the first activity event, but this
trace cannot locate its exact frames. A missing final receipt is not evidence
that the user did not see that caption.

These latency values start at a padded visual window endpoint. They include the
ACK return trip and Flutter's post-frame callback, not physical display scanout
or an independently measured acoustic speech end. They do not establish that
every spoken sentence appears within 2–3 seconds.

## Controlled caption-policy comparison

All comparisons use identical saved model hypotheses and window timestamps.
The default policy reproduces 12/12 scene-2 caption events. Changing right
context from 1.0 s to 0.5, 1.5, or 2.0 s changes none of those events or final WER.

The earlier time-only policy produces first text at 4.750 s instead of 10.032 s
in scene 2, but incurs six prefix revisions and retains WER 45%. In scene 1 it
changes WER from 41/76 to 39/76 with eleven prefix revisions. In the no-speech
scene, it inserts 13 units instead of 12. These are simulated policy outputs,
not new model runs or phone measurements. The stable policy remains selected.

## Confirmed stop/receipt defect and fix

Three parts of shutdown prevented final receipt collection: the client treated
capture stop as a disconnected state for ACKs; the capture screen discarded its
session reference and switched layout before finalization; the server stopped
receiving controls immediately after `stop`.

Android 1.6.2+14 keeps the large live caption panel while finalization is pending
and can acknowledge that caption after camera stop. The server continues to
receive controls during finalization. Clients requesting render receipts get a
maximum 300 ms grace period for the latest caption before `session_final`.
Older clients do not receive this extra wait. The grace period affects session
closure, not inference or automatic endpoints during continuous live capture.

Regression tests reproduced the dropped receipt in both Python and Dart before
the fix. The corrected code passes the streaming/activity/delivery suite
(33 tests), Flutter analyze, and all 29 Flutter tests. The new behavior has not
yet been verified on the physical phone. This patch does not claim a WER or
false-activation improvement.

## Recognition issue still open

Scene 3 is a failed negative test: motion gating and a nonempty model hypothesis
are insufficient evidence of speech. Even agreement across windows does not
eliminate its false caption. Do not hide this by reporting zero unavailable
windows as successful recognition, or by filtering the exact phrases seen here.

A candidate visual speech/non-speech model is being examined separately. The
[PAZ VVAD-LRS3 model documentation](https://oarriaga.com/paz/models/classification/)
provides image-sequence classifiers and pretrained weights. These are candidates,
not validated replacements; crop, normalization, causal window latency, missed
real speech, and false activations must be checked on phone recordings before
changing the live gate. The [3DI-based alternative](https://github.com/sariyanidi/VoiceActivityDetection)
expects canonical 3DI landmarks and cannot directly consume the existing
MediaPipe landmarks.

Both pretrained image classifiers were executed in a separate TensorFlow CPU
environment. On three diagnostic windows (speech, a pause in a previous phone
clip, and a synthetic repeated-frame negative), CNN2Plus1D_Light had scores
0.9958 / 0.0009 / 0.0035 and warm inference medians 63–73 ms with two CPU threads.
The MobileNet-LSTM alternative took 92–93 ms. These scores are not calibrated
probabilities on this phone. Crop detection, the initial 38-frame buffer, and
full-session endpoint scheduling are excluded from those timings. Three windows
are only a runtime and input-pipeline check; scene-3 smiling/head motion and
missed short real utterances remain untested. Neither classifier is deployed.

The Android APK is 1.6.2+14, package/signing identity unchanged, with a successful
release build and SHA-256 matched after download over the LAN page. Windows
installer 1.6.0 remains the last complete installer; the receipt/shutdown fix is
a local server patch for this test iteration, not a newly validated full installer.

Private raw traces, confirmed references, SHA-256 receipts, and detailed outputs
are local under `artifacts/wifi_live_20261109_round01`; video and transcripts
remain excluded from Git. Videos for these three scenes have not yet reached the
PC. The LAN exchange at port 7101 accepts explicitly selected recordings; the
recognition service remains at port 7100. The optimization goal remains active.
