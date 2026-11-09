# Direct phoneme decoding and the fourth phone session

Work stays in `E:\Project\Lip_App\lip_reader`. Production retains SO_seed17,
beam 3, CTC weight .1, six-second windows and 1.5-second updates. The new direct
decoder is available in the app repository for controlled replay, but is not
enabled in the phone's production captions: its complete-caption results do not
justify promotion. The application still has high error rates for free speech.

## What was implemented

`server/app/services/phoneme_direct.py` searches a pronunciation trie from the
window-trained head's framewise CTC posteriors. It produces word sequences without
receiving SO17's three candidate sentences. Blank/repeat handling, complete
syllable boundaries, incomplete right edges and CTC word timing are explicit.
The broad approach combines a lexicon and a small text language model with CTC
beam search, as described in the [PyTorch decoder tutorial](https://docs.pytorch.org/audio/2.8/tutorials/asr_inference_with_ctc_decoder_tutorial.html).

The lexicon has 7,841 Vietnamese whitespace syllable entries. Pronunciations come
from the pinned [vPhon dependency](https://github.com/kirbyj/vPhon), whose GPL
license attribution remains in the existing experimental dependency record.
The small unigram/bigram/trigram model uses 57,848 unique training transcripts
from 271 source groups, totaling 1,156,379 tokens. Development/test source groups,
the 12 designated lexical holdouts and exact duplicate texts were excluded.
The phone scripts and test references never enter decoding or language-model counts.

The phoneme head is the already trained window model, SHA-256
`f9435fd632c66d3af74433d1f87134278c39fa0ecf86a7fd95b6c959ab9ee20d`.
SO17 SHA-256 is `cddfb8c79f1db9d66695c0b1b7e2d98837187c600668a8aee3ccdd5b58981ecc`.
No new visual training or cloud rental was needed for this experiment.

## Same tensors, same windows

We reused 383 source-separated corpus windows and 146 historical live windows,
then added 13 windows from the newly confirmed four-sentence phone recording.
Visual tensor and encoded-feature hashes are checked. Direct decoding sees only
the encoded features, its phoneme head, dictionary and training-only n-gram model.
Twelve configurations were selected by development WER/CER only; the chosen
configuration is segmental phones, LM weight .5, word insertion score 2,
beam 48, 12 candidate phone symbols per frame.

| Evaluation | SO17 WER | Direct phoneme WER | Direct proposals checked by SO17 |
|---|---:|---:|---:|
| Dev, 127 windows | 522/1607 = 32.48% | 769/1607 = 47.85% | 520/1607 = 32.36% |
| Test, 128 windows | 444/1511 = 29.38% | 630/1511 = 41.69% | 444/1511 = 29.38% |
| Lexical holdout, 128 windows | 437/1558 = 28.05% | 723/1558 = 46.41% | 439/1558 = 28.18% |
| Round03 complete caption | 48/76 = 63.16% | 53/76 = 69.74% | 48/76 |
| Round02 complete caption | 25/44 = 56.82% | 25/44 = 56.82% | 25/44 |
| Long ROI video complete caption | 400/599 = 66.78% | 432/599 = 72.12% | 400/599 |
| New round04 complete caption | 23/40 = 57.50% | 21/40 = 52.50% | 23/40 |

The direct decoder reduces errors on the newest clip but increases the historical
three-clip total from 473 to 510 errors out of 719 reference units. Across all four
replays the totals are 496/759 versus 531/759. This is insufficient evidence for
switching the application. The hybrid scorer evaluates direct proposals and the
baseline text using the same frozen text attention/CTC model; its gate is chosen
on dev. It has no complete-caption improvement and is also left experimental.

CER and all predictions are saved in
`artifacts/phoneme_direct_20261109/native_check_v1/evaluation/RESULTS.json`.
Vietnamese WER here uses lowercase, Unicode-normalized whitespace units, which
often represent syllables; CER removes spaces. The lexicon is finite. Lexical
holdout from the new branch does not establish absence from SO17 pretraining.
There is no demonstrated general recognition of arbitrary unseen words.

## Physical phone evidence

The connected device reports `SM_G965F`, Android 10. The user confirmed the four
sentences and ended recording. The MP4 is 31.279 seconds, H.264 480x720 with AAC
48 kHz stereo; decoded audio is nonzero. Its SHA-256 is
`eb98878dd3f5a16d15744e16b085af4036d128693bfa8bdc842ba048e460de70`.
Audio is retained for reference and is not passed to any visual decoder.

The actual phone session received 785 frames, had zero recorded capture gaps,
25.04 fps at all four automatic endpoints, and 23/40 word errors (57.50% WER),
55/132 character errors (41.67% CER). Median window processing was 957 ms.
Four endpoints were automatic; no manual sentence-finish button was needed.

The original transport telemetry estimates 1.91–2.31 seconds from the **padded
visual endpoint** to the server caption. This is not a measured acoustic word
ending or screen-render delay. Pure amplitude silence detection at -32 dB did not
yield reliable pauses in this recording, so no acoustic-end latency is claimed.
The target of 2–3 seconds after actual speech remains a user-visible acceptance
criterion to measure with synchronized device rendering and speech-end annotations.

The phone and PC are on 172.16.0.x. Wi-Fi server access was not established; the
verified route is `adb reverse tcp:7100 tcp:7100`, with the app set to
`http://127.0.0.1:7100`. This route requires the USB connection. No firewall or
network-profile changes were applied.

## Applied live-flow changes

The default server launcher now initializes neural inference kernels and the
MediaPipe activity runtime before accepting sessions. `-SkipWarmup` is available
for diagnosis. This moves cold initialization to server startup.

A fresh-process PC replay measured first ready handshake 1.861 s without warmup
and .018 s with it. Two subsequent actual phone start/stop rounds logged 31 ms
and 35 ms ready handshakes, and both UI samples displayed 25 fps. These are
individual observations, not network percentile guarantees. Initial camera
binding can still have short gaps; the original spoken-session zero-gap result
must not be generalized to every reconnect.

New trace fields expose capture-clock time, window-end-to-caption delay and
separate preprocessing/decoding costs. They do not treat initial handshake time
as speech-processing latency.

An empty unfinished window retains its unavailable-window evidence but no longer
asks the still-speaking user to repeat immediately. Empty final utterances and
actual inference/input failures still show a notice. Caption commitment remains
unchanged: prefixes require agreement, followed by automatic finalization.

The live PC replays send 782 frames each with zero transport drops and four
automatic endpoints. They use fresh automatic activity timing, so their 25/40
errors in both cold/warm runs must not be compared as model gains against the
frozen-window 23/40 result. One warm-run early window was empty; its evidence is
preserved. The warning-behavior regression specifically covers early versus final
empty output. Cold/warm timing did not establish faster steady-state decoding.

## Reproduction and artifacts

Use `server/.venv/Scripts/python.exe` from the `server` directory. The executable
modules under `experiments.phoneme_probe` accept `--help` and refuse existing output
directories: `prepare_direct`, `evaluate_direct`, `score_direct_candidates`,
`evaluate_direct_proposals`, and `direct_ws_replay`.

The last module sends the newest phone video at 25 Hz through a local WebSocket,
checks all 13 preprocessed image tensor hashes, and checks both sets of predicted
texts against the cached evaluation. Original window boundaries are fixed;
endpoint release offsets are estimated from original transport telemetry. This
checks the paired inference/transport path, not new automatic endpoint detection.
The app's actual automatic WebSocket endpoint is covered separately by the two
PC replays and the physical phone sessions.

The isolated paired run received and acknowledged 782/782 frames and checked all
13 tensor/candidate matches. Direct decoding adds a median 59 ms (p95 86 ms) after
the shared SO17 decode. This is a sequential comparison harness, not the latency
of a deployed replacement decoder. Final frozen-window captions arrived 1.89–2.23 s
after the padded endpoint. The final production-code automatic replay received
782 frames with no drops, finalized four turns and had 23/40 errors; differences
from the preceding 25/40 automatic runs include scheduling and window boundaries.
No new model accuracy gain is inferred from those differing schedules.

All 93 server tests passed. The Android APK did not require a rebuild. The USB
connection helper can re-establish forwarding after unplug/replug:
`powershell -File tools/connect_android_usb.ps1`. The server launcher must already
be running and ready. A third physical start/stop check after the final server
restart is saved in `device/final_reconnect/`.

All new evidence lives below `artifacts/phoneme_direct_20261109/`:

- `resources/LEXICON_LM.json`: training-only text resource and provenance.
- `evaluation_v1/`: 12-way development sweep and frozen configuration.
- `native_check_v1/`: all 542 paired windows and visual checking experiment.
- `device/recording/`: copied original MP4 and stream/audio validation.
- `device/PHONE_BASELINE.json`: actual user-session metrics.
- `device/{LIVE_WINDOWS,WS_WINDOWS}.json`: fixed boundary manifests.
- `device/{COLD_REPLAY,WARM_REPLAY}.json`: automatic live PC replays.
- `device/direct_ws_clean/`: final isolated paced paired replay.
- `device/reconnect/`: phone UI and ready-time logs.
- `DELIVERY_RECEIPT.json`: final validation, hashes and runtime configuration.

The APK remains 1.4.4+9 because this iteration changes the server and evaluation
code. No source/model publication or remote deployment was performed.
