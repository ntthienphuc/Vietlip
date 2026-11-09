# Vietnamese visual phoneme probe

This is an offline application experiment, not a replacement live model. It adds
two trainable CTC outputs to frozen SO_seed17 visual states: segmental IPA and
segmental IPA with six tone classes. The text decoder and all original checkpoint
bytes remain unchanged. No audio enters the encoder, head, or candidate selector.

The head is LayerNorm → 768-to-256 projection → depthwise temporal convolution
(five frames, two frames of right context) → parallel classifiers. The existing
encoder already uses the entire input window; this experiment does not make that
encoder causal. The second loss has weight 0.3. Training selects the epoch using
development segmental phone error rate (PER).

## Dependencies and attribution

Use the existing server environment. The experiment additionally requires
[James Kirby's vPhon](https://github.com/kirbyj/vPhon), pinned to
`076a5d3611d688325a71ad6dbbcd5868399bf5e7`, kept separately under
`artifacts/phoneme_probe_20261106/deps/vPhon`. Its GPL-3.0-or-later license and
copyright files are preserved. It is not packaged into the Android APK.

vPhon supplies broad Northern Vietnamese forms. Onsets, glides, nuclei and codas
are atomic IPA tokens; e.g. /tʰ/ and /uə/ are not split into characters. Six tone
classes are separate tokens. Checked D1/D2 are mapped to B1/B2. This canonical
pronunciation convention does not model each speaker's actual dialect.
Foreign strings, numbers and malformed syllables are rejected explicitly.
Training excludes entire unsupported clips and records exclusion counts.

The phoneme-first idea is informed by
[VALLR](https://arxiv.org/abs/2503.21408); this implementation does not use its
English phone inventory, weights, LLM or reported accuracy.

## Reproduction

Run from the app root with `$env:PYTHONPATH='server'` and
`$env:PYTHONIOENCODING='utf-8'`. Use `server/.venv/Scripts/python.exe -m` for
these modules; every module has `--help`:

1. `experiments.phoneme_probe.prepare`: freeze source-group splits and lexical
   holdouts from the local training manifest. All experiment data is written
   under a NEW output directory. No media is modified.
2. `experiments.phoneme_probe.extract`: verify video hashes and cache detached
   float32 visual states. Supports resume only with matching dataset/checkpoint
   identity. Stop the owned live GPU server before loading a second large model.
3. `experiments.phoneme_probe.train`: train the small heads and save both best
   and last weights. Test and phone examples are not loaded during training.
4. `experiments.phoneme_probe.evaluate`: compare beam-3 text predictions and
   candidate rescoring with the phoneme CTC likelihood. Select weight from
   [0, 0.1, 0.3, 0.6, 1] using dev WER only, preferring zero in ties.
   If ANY candidate lacks a supported pronunciation, keep the original top one.
5. `experiments.phoneme_probe.audit`: count exact IPA syllables for lexical
   holdouts, audit pronunciation overlap, and compare ordered / shuffled /
   static cached features.

For an explicit local trial, `server/run_phoneme_trial.ps1` loads the learned
head together with SO17 and checks the visual checkpoint hash. It reorders the
same three candidates and aligns timestamps to the selected candidate's token
IDs. `server/run_realtime.ps1` remains the default, with this feature off.
The trial launcher is experimental: the first continuous phone replay regressed,
so the head is not recommended for the active live profile.

All reference text is restricted to labels, evaluation and deterministic split
selection. The visual forward pass never receives reference text. Candidate
rescoring sees only the model's own candidates.

## Partial-utterance window continuation (2026-11-07)

The app-local `prepare_windows` module reuses the frozen v1 train/dev/test splits.
It creates growing prefixes and rolling windows up to six seconds, cutting on the
25 Hz frame grid. `window_features` runs the frozen visual encoder separately
on every cropped input: full-utterance states would include unseen future frames.
Only words fully contained in a window supervise CTC, within their time span;
partial edge words are excluded from the loss rather than assigned invented
partial phoneme labels. This relies on the existing word timings, not phoneme
alignments. `train_windows` starts from the v1 head and selects on dev core PER.

Application artifacts are under `artifacts/phoneme_window_20261107/`.
The authorized workstation receives an isolated packet under
`D:/Lip_App_Window_20261107/run_v1/`; the original research checkpoints and
datasets are only read. `tools/remote_app.py` uses the already trusted SSH host
key and limits file transfers to this app experiment directory.

The reproducible comparison consists of:

1. `fixed_windows --kind corpus`: one predetermined window per held-out clip,
   preferring a partial right edge. Store SO17 top-three candidates and visual
   states. Core WER/CER use existing complete-word bounds for evaluation only.
2. `fixed_windows --kind live`: replay the historical 25 Hz JPEG preparation
   at identical window boundaries for two phone clips and one long ROI clip.
3. `score_windows`: run old/new heads on the very same cached states/candidates;
   choose each weight using dev WER only. Replay the application's caption
   agreement and finalization to score complete video captions.
4. `fixed_ws_replay`: send the source JPEG frames at 25 Hz through a loopback
   WebSocket, decode again, and assert exact prepared-tensor hashes and candidate
   strings against the fixed cache. Use the original decode release times as well
   as the original window bounds. All branches share one visual forward pass.
   This benchmark endpoint is internal to the script: it tests the app's model,
   rescoring, and caption merge, but does not retest the production endpoint
   detector, phone UI, or a Wi-Fi/Tailscale inference connection.

All commands refuse existing output directories. Example scoring, from app root:

```powershell
$env:PYTHONPATH='server'
.\server\.venv\Scripts\python.exe -m experiments.phoneme_probe.score_windows `
  --old-head artifacts/phoneme_probe_20261106/train_v1/best.pt `
  --new-head artifacts/phoneme_window_20261107/remote_result/training/best.pt `
  --corpus-cache artifacts/phoneme_window_20261107/corpus_cache `
  --live-cache artifacts/phoneme_window_20261107/live_cache `
  --vphon artifacts/phoneme_probe_20261106/deps/vPhon `
  --output artifacts/phoneme_window_20261107/evaluation_v2
```

## Interpretation

- WER uses Vietnamese whitespace units; these are often syllables, not complete
  linguistic words. CER excludes spaces. PER excludes predicted syllable
  boundaries; tonal-token error includes the six tone symbols.
- Source-group separation prevents source IDs overlapping train/dev/test.
  It does not establish speaker independence.
- Lexical holdouts are absent from NEW HEAD training. The frozen visual encoder
  may already have seen them. This is not an unseen-word result for the complete
  pretrained system.
- Two spellings can have identical segmental phones. The audit reports both
  segmental and tonal pronunciation overlap with head-training labels.
- The seven phone sentences are evaluation only. Their audio-assisted slices
  are oracle diagnostic inputs, not continuous live accuracy measurements.
- Head-only timing on cached features excludes video transport, mouth cropping,
  visual encoding, beam decoding, and phone rendering.
- A successful phoneme head does not by itself establish better text accuracy.
  Keep the production model unchanged unless independent text/live evaluations
  justify a change. There is no free-form LLM correction in this experiment.
