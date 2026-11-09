# Round 03: audio-referenced phone test and streaming corrections

Work performed in `E:\Project\Lip_App\lip_reader`. Android remains the installed
1.4.4+9; this turn changes the server's sampling and caption ownership, not APK code.
Original research checkpoints and data remain unchanged.

## Input and reference

Original phone recording: `lip_1793957235390038.mp4`, 50.712 s H.264 480x720,
AAC stereo 48 kHz. SHA-256:
`1d73bebaff67eb8f7b125a46eb21b241d50aa4439ecc9f7f867e76709a732e6d`.
Copied to `artifacts/device_s9_20261106/round03/` without changing the device file.
Raw preferences/history, app logs and the corresponding server trace are retained.

The speaker confirmed in chat: **"Đúng 7 câu, chưa nói thêm"**. Reference is the
seven previously supplied sentences. The recording has no spontaneous held-out
section. Faster-Whisper small CPU int8 was used only to draft reference text and
estimate speech timings. It made several word errors and its text was not adopted
as unquestioned ground truth. Audio never entered visual inference. Exact confirmed
references are in `REFERENCE_CONFIRMED.json`; provisional artifacts remain preserved.

## Actual phone findings

- Ready handshake 43 ms, 1,273 received frames, reported capture 25.04 fps,
  zero capture gaps, seven automatic sentence endpoints, no unavailable decode windows.
- Original output: 53 errors / 76 reference space units = **69.74% WER**;
  127 / 271 characters = **46.86% CER excluding spaces**.
- Zero unavailable windows is not accuracy. All seven turns returned words, often wrong.
  Lip Lens, bluetooth and laser were not recognized correctly.
- Face frames were upright with a visible mouth. The automatic boundary count fits
  the seven spoken sentences; most errors persist even with assisted boundaries.

## Fixed-input model diagnostics

All seven local checkpoints were tested on the same prepared image tensors. Slices
used approximate audio-informed boundaries, so these are oracle diagnostics rather
than live scores. Neural decoding never received reference text or audio.

| Checkpoint | Errors / 76 | Median neural decode, seconds |
|---|---:|---:|
| SO_seed17 | 48 | 0.328 |
| SO_seed29 | 46 | 0.305 |
| SO_seed43 | 45 | 0.316 |
| WW_seed17 | 58 | 0.368 |
| WW_seed29 | 57 | 0.341 |
| WW_seed43 | 58 | 0.345 |
| VLR_pretrained | 111 | 0.448 |

WER can exceed 100% because insertions count. The pretrained checkpoint repeatedly
hallucinated subscription/video boilerplate. It is not used by the app.
SO43's three-error advantage on this one development clip is insufficient to
replace the current SO17 deployment. Earlier held-out selection is preserved.

Six decoder configurations were also compared on the same tensors. SO17 beam3 /
CTC .1 had 48 errors; beam3 /.3 and beam5 /.3 had 46; beam10 /.3 had 45 with more
search time. None reliably recovered the new words. Production stays beam3 /.1.
Horizontal flipping worsened SO17 to 55 errors. A short-range-first face detector
worsened SO17 to 55 and SO43 to 54. That preprocessing candidate was archived and
the application preprocessor restored byte-for-byte to its pre-turn state.

## Applied server corrections

1. **One spoken interval gets one caption slot.** A CTC token could keep its onset
   but acquire a slightly longer ending in a later decode. Filtering by midpoint
   then appended its revised spelling after the already committed spelling, e.g.
   `mấy quẹt lấy lái do`. The overlap guard requires nearly identical onset, actual
   interval overlap and nearby center. It retains already shown text and excludes
   the duplicate slot; adjacent repeated words are preserved.
2. **A fixed 25 Hz session sampling grid.** Rolling windows previously started on
   a phase derived from the newest jittered camera timestamp. The overlap could
   choose different source images each time. Sampling now uses the same absolute
   grid, maintains bounded storage and respects gaps/turn boundaries. This improves
   consistency and allows reuse of identical landmark inputs.

The ownership-only ablation on identical saved predictions reduces the original
phone output from 53 to 52 errors, with zero visible-text erasures. Both previous
round-02 logs and the small ROI runtime test keep their earlier error totals.
This is a small correctness fix, not a remedy for incorrect visual recognition.

The deterministic cadence simulation (30 Hz sensor selected near 25 Hz, 1 ms jitter,
6 s windows every 1.5 s) used 1,455 new detection inputs before and 1,169 after,
about 19.7% fewer. This is a work-reuse diagnostic, not measured phone speedup.

## End-to-end server replays

The original MP4 was sent at camera pace through the real WebSocket endpoint,
with automatic visual endpointing and visual-only input.

| Run | WER | Final sentence count | Transport drops |
|---|---:|---:|---:|
| Round03 replay before | 47/76 = 61.84% | 7 | 0 |
| Round03 replay after | 43/76 = 56.58% | 7 | 0 |
| Previous round02 replay after | 25/44 = 56.82% | 5 | 0 |

The previous round02 AFTER_REPLAY also had 25/44 errors. Fresh replay differences
include window scheduling/resampling, so the four-error improvement should not be
interpreted as a controlled model accuracy gain. Original phone live and MP4 replay
have different capture/compression paths; do not compare 69.74% directly to 56.58%
as an achieved device improvement.

Estimated audio-end-to-server-final time on the round03 after-replay is
2.24-2.57 s, median 2.34 s, using ASR word-end estimates. Before-replay median
was 2.32 s: no end-to-end speedup is claimed. These timings exclude phone paint
and do not have manually annotated speech ends. Window processing median was
871 ms before and 919 ms after; the first seconds of the latter overlapped CPU
unit tests, so this is not an isolated performance benchmark.

## Validation and remaining boundary

All **68 server tests passed**, including real interval substitution, adjacent
repeated words, jittered overlap sampling, gaps and startup-boundary regressions.
Android was not rebuilt because its code did not change. The phone disconnected
from USB before the final device recheck; only the emulator remained. Fresh physical
camera validation after these server changes is outstanding. The LAN server was
restored and checked ready; no boot-time service or public deployment was added.

This clip is now development data. General free-form or unseen-word accuracy is
still inadequate. A practical next experiment is adaptation to varied phone
recordings with genuinely separate sentences/sessions for evaluation. The
[speaker-adaptive study](https://arxiv.org/abs/2409.00986) uses visual/language
adaptation, including LoRA and prompts, but its English results do not establish
Vietnamese performance. Training on these seven sentences and reporting their
improvement as generalization would not answer the user's requirement.

The [MediaPipe documentation](https://chuoling.github.io/mediapipe/solutions/face_detection.html)
motivated the short-range detector experiment; the local measured regression is
why that candidate was not retained. No new LLM rewriting or model training has
been deployed. All evidence is indexed in `EVALUATION.json` and `DELIVERY_RECEIPT.json`.
