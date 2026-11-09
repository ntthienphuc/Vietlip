# Visual speech confirmation and a fresh short-sentence phone test

SO17 remains the selected recognizer. The new CNN confirmation service is an
explicit source-only experiment, disabled in the desktop release. It improves
one controlled silence replay and preserves tested speech, but has not shown a
speech-text accuracy improvement. The application still makes substantial errors
on unrestricted Vietnamese sentences.

## What was implemented

`speech_confirmation.py` examines raw face images using PAZ CNN2Plus1D Light.
Two distinct consecutive positive windows confirm a turn. Rejection requires
at least two valid, uniformly negative full windows and at least two seconds of
input. Short, mixed, missing-face or failed-model inputs preserve normal VSR.
An isolated positive is retained for the whole turn, including after the bounded
score cache expires. This avoids turning an uncertain long utterance into silence.

The PyTorch port needs no TensorFlow runtime. Converted weights occupy 433,355
bytes; hashes pin the upstream source, original weights and conversion. The port
was checked against all 1,498 cached upstream windows from five recordings:
zero threshold-decision disagreements, maximum absolute score difference
4.47e-7. Four-thread CPU median calls were 57.73–61.09 ms per recording. Scores
are not calibrated confidence percentages on this phone. Attribution and scope
are retained in `server/vendor/paz`.

The service runs in its own executor and retains confirmed status within each
turn. It does not change recognition tensors, model vocabulary, motion boundaries
or captions for an allowed window. In the frozen replay, first confirmation took
up to 395 ms including crop work; already-confirmed windows took under a millisecond.
Uniformly negative windows required more scanning, up to 651 ms. These are
isolated execution measurements, not added end-to-end delay guarantees.

## Paired comparison: identical images and window times

These are MP4 replays on an explicitly declared clock, not reconstructions of the
original native camera JPEG stream. Every VSR tensor is hash-verified; the gate
variants reuse the same decoder hypotheses. Text references are used only after
prediction. WER counts normalized Vietnamese whitespace units; CER excludes spaces.

| Recording | Baseline | Conservative confirmation | Change |
| --- | --- | --- | --- |
| Scene 1, 25 windows | 43/76 errors, WER 56.58%, CER 38.71% | Identical | 0 speech windows rejected |
| Scene 2, 12 windows | 15/40 errors, WER 37.50%, CER 28.03% | Identical | 0 speech windows rejected |
| Scene 3, confirmed silence, 4 windows | 7 inserted units | 0 inserted units | 4 negative windows rejected |
| New scene 4, 9 windows | 11/18 errors, WER 61.11%, CER 50.00% | Identical | 0 speech windows rejected |

Silence has no reference words, so its WER/CER are undefined. The short-input
fallback also preserved all 77 tested suffix fragments (0.4–2.4 seconds) from
scenes 1/2. These fragments can start inside words and are not 77 independent
complete utterances. Committed visible-prefix revisions were zero; this does not
prove that every provisional word was correct.

## Actual new camera session over Wi-Fi

The user confirmed these four sentences: “Xin chào”, “Cảm ơn bạn”, “Tôi muốn
uống nước”, and “Chiều nay tôi đi siêu thị mua trái cây”. The candidate ran at
LAN port 7103. Samsung SM-G965F used installed VietLip 1.6.3+15. ADB was used
for UI/export diagnostics; there were no USB reverse mappings.

The app exported the 29.086729-second MP4 via its document picker. Its SHA-256
matched on the phone and PC: `734290093b91c843246a56ec67c37c218082ca5a47faf56cd69459a2c9507dd0`.
All H.264/AAC frames decoded. FFmpeg's null muxer reported two repeated rounded
DTS values; the causal OpenCV replay independently checked strictly increasing
source PTS and completed all nine windows without a timestamp error.

- 729 received frames; final recent capture rate 25.04 fps; zero gaps over 500 ms.
- App WebSocket ready log: 131 ms. Native JPEG encode mean: 6.477 ms.
- Four automatic turns, nine decoded windows, zero unavailable windows, all nine
  caption events acknowledged after a real Flutter frame.
- All four short/long turns were confirmed. No additional decoded turn or text
  appeared after the fourth turn. This is one new session, not proof that smiles
  or chewing can never trigger recognition.
- Original live WER **66.67% (12/18)** and CER **50.00% (30/60)**. Examples include
  “xin chào” → “chị chào”, “cảm ơn bạn” → “cảm ơn mà”. The gate did not fix these.
- Final visual-window-end to Flutter render ACK: **1.623, 1.608, 1.558, 1.778 s**.
  These include return network delay and use the padded visual endpoint. They
  are not exact acoustic-speech-end or physical display scanout measurements.

Offline Silero estimates find four speech intervals, ending around 2.88, 6.37,
10.14 and 15.97 seconds in the MP4. MP4 and live capture zero were not measured
together. Therefore no exact acoustic-end latency is inferred for this phone
session. The earlier physical prerecorded-replay test has explicit source-time
mapping and remains the relevant approximate acoustic timing evidence.

## Paced server execution and decision

Completed 25 Hz PC replays sent 1,623 / 579 / 435 identical JPEG packets to each
server for scenes 1/2/3, with every packet acknowledged. Runtime scheduling
allowed window boundaries to vary. Scene-1 errors were 44 versus 43; scene-2
errors were 12 for both. This variation is not a paired model improvement.
Both servers produced no text on scene 3: its original failure did not reproduce
under this paced schedule, so that run cannot establish a live silence fix.

Approximate audio-end to PC receipt on the candidate was 1.95–2.68 s for scene 1
and 1.77–3.50 s for scene 2. These are PC replay timings using offline audio
estimates, not phone-camera timing. The final scene-2 motion endpoint shifted
later with the sampling schedule. The product does not yet guarantee 2–3 s.

Retain the selected SO17/float32/beam3/CTC0.1 profile and the existing motion
endpoint policy for the release. The CNN is available for further controlled
tests with `LIP_EXPERIMENTAL_VISUAL_CONFIRMATION` pointing to the pinned local
NumPy weights. The packaged desktop profile clears this switch and ships no
experimental weights. Missing/bad weights fail open with diagnostic state.

31 streaming/activity/confirmation/delivery tests passed, including a 140-second
synthetic turn that evicts old score cache entries without losing earlier positive
evidence. Four desktop-profile tests passed, including isolation from this flag.
Release-wide checks and installed-package results are recorded separately.

## Evidence and reproduction

Aggregate, transcript-free evidence is in
[`evidence/visual_confirmation_20261110.json`](evidence/visual_confirmation_20261110.json).
Private originals remain under `artifacts/visual_vad_20261110` and
`artifacts/wifi_live_20261110_scene04`. Video, audio, transcripts, tensors and
weights are excluded from Git and the installer.

Reproduction scripts under `server/experiments/visual_activity_probe`:
`export_torch.py`, `torch_parity.py`, `confirmation_replay.py`, `live_replay.py`
and `session_comparison.py`. Each creates a new output directory and preserves
prior results. Original research checkpoints and source recordings are unchanged.
