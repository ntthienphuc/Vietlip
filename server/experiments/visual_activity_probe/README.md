# Offline visual activity probe

This experiment compares the existing motion endpoints and two pretrained PAZ
VVAD classifiers on complete phone recordings. Nothing imports this package
from the production server. Audio is used only by the separate report command
to supply estimated reference boundaries.

Run from the app repository root. `prepare.py` uses the server environment;
`score.py` uses an isolated TensorFlow CPU 2.15.1 environment with the downloaded
PAZ sources and weights. Do not install TensorFlow into the release runtime.

```powershell
server/.venv/Scripts/python.exe server/experiments/visual_activity_probe/prepare.py --video <recording.mp4> --output <new-private-output-directory> --camera-transport
<candidate-env>/Scripts/python.exe server/experiments/visual_activity_probe/score.py --input <output-directory> --candidate-root <candidate-root>
server/.venv/Scripts/python.exe server/experiments/visual_activity_probe/report.py --input <output-directory> --references <confirmed-boundaries.json>
server/.venv/Scripts/python.exe server/experiments/visual_activity_probe/confirm.py --input <output-directory> --report <output-directory>/REPORT.json --references <confirmed-boundaries.json>
```

Input JSON supports the existing `REFERENCE_CONFIRMED.json` segments with
`audio_start_estimate` / `audio_end_estimate`, or the output of
`audio_endpoint_audit.py`. An unknown speech onset is excluded from onset
metrics. An audio VAD output may contain noise regions; its intervals are not
automatically treated as additional spoken sentences.

Every 25 Hz sample uses the latest source frame at or before that timestamp.
Use --camera-transport for JPEG quality 80 and the live activity decoder's
360-pixel resize. Omitting it is a full-resolution diagnostic, not an exact
production input path. Neither mode reconstructs original camera JPEG payloads.
Both candidates see identical 38-frame RGB windows at a three-frame stride.
The threshold is fixed at 0.5 and no score smoothing is applied. Runtime is
measured per call with batch size one and two CPU threads. Crop failures and
buffer warmup are reported separately from negative decisions. Full-window
classification excludes reference boundaries by 160 ms and excludes mixed
speech/silence windows; these exclusions must accompany any accuracy count.

`report.py` compares direct replacement of the motion observation with the
candidate decision, retaining the existing endpoint policy. `confirm.py`
instead preserves the motion boundaries and checks whether two consecutive
positive windows were available before each turn ended. The confirmation
windows must be entirely after that turn's original start. This second option
is a diagnostic policy, not an implemented live feature.

Neither experiment invokes the recognition decoder, proves a WER improvement,
or measures phone display latency. They do not validate short utterances or
non-speech smiling/head turns without corresponding source recordings.
Input crops and source videos remain under ignored `artifacts/` directories.
Commands refuse to overwrite existing results.

## Frozen caption follow-up

Run from the repository root:

```powershell
server/.venv/Scripts/python.exe server/experiments/visual_activity_probe/frozen_captions.py --scenes artifacts/wifi_live_20261109_round01 --probes artifacts/visual_vad_20261110 --checkpoint server/models/SO_seed17.pt --output <new-output-directory>
server/.venv/Scripts/python.exe server/experiments/visual_activity_probe/checkpoint_captions.py --frozen <previous-output-directory> --scenes artifacts/wifi_live_20261109_round01 --models server/models --output <new-candidate-directory>
server/.venv/Scripts/python.exe server/experiments/visual_activity_probe/short_turn_audit.py --probes artifacts/visual_vad_20261110 --output <new-short-audit.json>
```

The first command copies archived window times onto the MP4 clock as a declared
replay convention. It does not claim to reconstruct the original native JPEGs
or capture-clock offset. Candidate checkpoint comparisons verify and reuse the
same aligned tensors. The short audit uses existing visual suffixes, not newly
spoken complete short phrases. See `docs/FROZEN_WIFI_CAPTIONS_2026-11-10.md` for
the decision and limitations. None of these modules runs inside the live server.
