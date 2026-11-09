# Frozen Wi-Fi caption comparison and physical Android stop receipt

SO17 remains the live model. The two previously selected checkpoint averages
regress on both newly retrieved speech recordings. A CNN confirmation gate
removes false text in a controlled silence replay while preserving the speech
captions, but strict confirmation fails the short-fragment stress check and is
not enabled in production.

## Same tensors and same windows

The 25 / 12 / 4 archived scene-1 / scene-2 / scene-3 window times were copied
onto the saved MP4 clock. This defines a new replay schedule. Camera-clock zero
and MP4 zero were not recorded together, so these are **not reconstructions of
the original live predictions**. In particular, the original scene-3 trace had
12 inserted whitespace units; this new SO17 replay has seven.

Every 25 Hz sample uses the latest decoded source frame at or before that time,
then JPEG quality 80 and the production 360-pixel decode path. The aligned input
tensors are saved with SHA-256 hashes and reused unchanged for all checkpoint
candidates. All variants use float32, beam 3, CTC 0.1 and the existing caption
agreement policy. Reference sentences are used only for scoring predictions.
No audio, phrase list, or LLM enters recognition.

| Candidate | Scene 1 errors / 76 units | Scene 2 errors / 40 units | Scene 3 inserted units |
| --- | ---: | ---: | ---: |
| SO17 baseline | 43 (56.58% WER) | 15 (37.50% WER) | 7 |
| Six-checkpoint average | 50 (65.79%) | 20 (50.00%) | 9 |
| SO17 + six-checkpoint average, 50% | 45 (59.21%) | 17 (42.50%) | 8 |

The two alternatives were fixed by the earlier corpus-dev comparison; no new
mixture was fitted to these recordings. Their earlier phone regressions still
apply. This check supports keeping SO17, not a claim of optimality. Baseline
CER excluding spaces is 38.71% and 28.03% on scenes 1 and 2. Silence has an empty
reference: WER and CER are undefined, so insertion counts are reported instead.

## Confirmation gate: useful evidence with a remaining short-speech failure

The existing CNN2Plus1D Light scores were used with the predeclared 0.5 threshold.
A decode is authorized only after two consecutive positive classifier windows
wholly after the turn start. A score is available only after its measured crop
and classifier call have completed. Cached calls exclude scheduling contention;
this is not an end-to-end live timing benchmark.

All 37 speech windows are accepted and all four silent windows are rejected.
The complete captions and WER/CER on the two speech recordings stay identical;
scene 3 goes from seven inserted units to zero. The result holds with the score
clock shifted by -0.5, 0 or +0.5 seconds. These shifts are sensitivity checks,
not measured bounds on the original clock offset. Visible prefix revisions
remain zero. No speech-text accuracy improvement is claimed for the gate.

Before adopting it, short-speech behavior was checked using the existing
utterances' final visual fragments and natural trailing pause. No frames were
stitched or repeated. A hypothetical turn starts at the fragment beginning and
finalizes one second after the audio-estimated end. These fragments may begin
inside a word; they are not newly recorded complete short phrases.

| Speech fragment | Confirmed / 11 fragments |
| --- | ---: |
| 0.4 s | 0 |
| 0.6 s | 0 |
| 0.8 s | 7 |
| 1.0 s | 9 |
| 1.4 s | 11 |
| 1.8 s | 11 |
| 2.4 s | 11 |

The classifier needs 38 frames of history; missing context is unknown, not
evidence of silence. A strict gate would lose the short fragments. The next
implementation must preserve an explicit short/unknown path, measure the
resulting false-activation tradeoff and runtime, and compare complete captions
before changing the default. All cases reuse two source recordings, so they
are not independent accuracy trials.

## Physical Android receipt after stopping the camera

Installed VietLip 1.6.3 was exercised on the Samsung SM-G965F over the actual
LAN connection, phone peer `192.168.1.17`. A temporary QA bridge at PC port 7102
fed the saved scene-2 video into the real SO17 server and forwarded its events
to the phone. The phone's current camera images were acknowledged but excluded
from inference; this is an application/transport test, not a new camera-quality
or speech-accuracy recording. History identifies the model as `QA-prerecorded`.

The phone's real **Kết thúc phiên** action stopped the source after 340 frames.
All 340 source frames were acknowledged, and all eight caption events received
an actual Flutter post-frame receipt from the installed app. The nonempty final
caption added new text after the stop action, was acknowledged **1.017 s** after
the bridge received that action, and preceded `session_final`. A phone UI dump
and screenshot show the same final caption.

The two completed sentences before the interrupted third sentence have
approximately **2.04 s and 1.79 s** from offline audio-estimated speech end to
the render ACK. The existing bridge's nominal 25 Hz resampling was mapped back
to decoded source PTS; first-sample offsets are 35 ms and 4 ms. These values
include the ACK return trip and are not physical display scanout measurements.
Two replayed sentences do not establish a product-wide 2–3-second guarantee.

ADB had no reverse mappings. After the test the bridge exited, and the app's
server address was restored to `http://192.168.1.19:7100`; the physical settings
screen reported ready. No model or installed production code changed.

## Reproduction and retained evidence

Scripts live under `server/experiments/visual_activity_probe/`:

- `frozen_captions.py`: causal MP4 pixels, archived window schedule, SO17 output,
  saved tensors and paired CNN confirmation evaluation.
- `checkpoint_captions.py`: two prior dev-selected model candidates on those
  hash-verified tensors.
- `short_turn_audit.py`: short-fragment causal confirmation check.
- `server/experiments/device_replay_bridge.py`: LAN health forwarding and actual
  phone stop/receipt support; defaults to loopback unless an explicit host is given.

Private files remain under ignored `artifacts/visual_vad_20261110/`:
`frozen_captions_v1`, `wifi_checkpoint_candidates_v1`, `SHORT_TURN_AUDIT.json`,
and `phone_render_stop_v1/VERIFICATION.json`. Phone UI evidence is under
`artifacts/wifi_live_20261109_round01/device_162/qa_*`.

The causal sampler/confirmation/empty-reference test suite passes all nine
checks. The four experiment entry points compile successfully. Production
remains on the previously validated package; there is no new APK or Windows
installer in this iteration. The optimization goal remains active.
