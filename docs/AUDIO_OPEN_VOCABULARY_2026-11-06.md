# Android 1.4.4: reference audio and open vocabulary audit

Application work remains in `E:\Project\Lip_App\lip_reader`. No research weights,
training data, or upstream projects were modified. No model was trained in this turn.

## Delivered recording behavior

- CameraController enables audio for the saved MP4. Android requests RECORD_AUDIO;
  microphone denial has an actionable Vietnamese message. iOS has a microphone
  purpose string, but has not been built or tested on an iPhone.
- The ready screen and live header disclose audio recording. LiveLipSession still
  sends only JPEG frames and control messages. The native model consumes video
  tensors. The recorded audio is reference material for evaluating actual speech.
- Installed 1.4.4 / versionCode 9 on Samsung SM-G965F, Android 10,
  serial `2108896924047ece`. The installed base APK matches the signed output:
  SHA-256 `cbb6f6c37fe654be22006457ed52e63eda4e6a0fa787b7589b4e9fad991d02f7`.
- Two consecutive start/stop sessions reached live at sampled UI 25 fps. Actual
  server capture_fps was 25.04 in both. There was no face in these checks, so they
  establish transport/recording behavior, not recognition accuracy.
- The two pulled MP4s contain H.264 480x720 and AAC stereo 48 kHz, with about 9.3
  and 9.1 seconds of audio. Both decode to nonzero PCM; track durations differ
  from video by less than 18 ms. This does not measure speech intelligibility
  or exact audio/video synchronization.
- One of the two sessions reported one capture gap over 0.5 s and incomplete=true;
  it is preserved as a remaining issue. First connection ready was 2,401 ms after
  cold startup; the next was 33 ms. Neither is speech-end-to-caption latency.
- Server was absent at the start of the turn. It was relaunched as a hidden
  PowerShell process with separate stdout/stderr and trace files, and checked
  ready across subsequent commands. Persistence through PC reboot is not configured.

Evidence: `artifacts/audio_v144/build.log`, `server-tests.log`, `package.txt`,
`device-flow/`, `live_traces_v2/`, `recording-check/RECORDING_VERIFICATION.json`,
`device-ready.png`, `DELIVERY_RECEIPT.json`. Original recordings remain on the device.

## Decoding corrections

The model uses 2,000 SentencePiece units, including UTF-8 byte fallback, with
CTC blank and EOS added by the adapter. Units match the tokenizer in exact order.
Previously the native adapter joined token strings: byte pieces could surface
as literal `<0xNN>` text. It now uses the existing SentencePiece model to decode
complete pieces. Word timestamps use the same decoder. A standalone whitespace
piece also now starts a new word instead of joining it to the preceding word.
This fixes text rendering/alignment; it does not teach the model a new pronunciation.

Validation: 20 Flutter tests, clean flutter analyze, 64 server tests. New regressions
cover ordinary Vietnamese, names, loanwords, multibyte fallback, and word boundaries.
A paced 5.12-second existing mouth-ROI sample exercised the running GPU server:
128 frames sent, zero transport drops, valid transcript, 1.04 s stop-to-final,
7 errors / 20 reference space units. This is only a runtime regression check,
not a new accuracy improvement or unseen-word benchmark.

## What "unseen" means here

`server/scripts/audit_vocabulary.py` checks normalized transcript exposure and
tokenizer round trips without reading video/audio or modifying models.

| Audited source | Records | Distinct space-like units | Occurrences |
|---|---:|---:|---:|
| Phase05 prepared train manifest | 92,632 | 14,106 | 1,851,681 |
| SO_seed17 continuation presentation schedule | 88,473 | 8,384 | 657,634 |

The SO17 receipt reports 6,000 completed updates and next_presentation=88,473.
The schedule hash matches its packaged Input_Manifest. Exact source paths and
SHA-256 are in `VOCABULARY_AUDIT.json` and `SO17_SCHEDULE_VOCABULARY_AUDIT.json`.

All 12 proposed sentences are absent as normalized contiguous text in both sources.
All 12 are representable without unknown-token loss. `lip`, `lens`, `lidar`,
`perovskite`, `bluetooth`, and `laser` are absent as standalone normalized units
in both sources. `pin` and `raman` are absent in the SO17 schedule but present in
the broader train manifest. Vietnamese space units are often syllables, not
linguistically segmented words. A new combination of familiar syllables is a
different test from a completely absent unit or a new loanword pronunciation.

These files do not establish the entire pretraining history, tokenizer-training
corpus, or text exposure of a future LLM. Label the test "absent in audited
training sources", never "guaranteed never seen by any model". Tokenizer support
means the output can be represented; it does not establish recognition accuracy.

## Next human recording

Use one continuous live session, camera front and portrait, face clearly lit,
ordinary speaking pace, no exaggerated mouth motion. Start with 5 seconds facing
the camera silently. Read these sentences without numbering and pause 3 seconds
between them:

1. Hôm nay tôi muốn kiểm tra camera trước.
2. Bạn đặt chiếc cốc màu xanh lên bàn giúp tôi.
3. Tôi muốn tìm một quán cà phê yên tĩnh.
4. Tôi đang thử ứng dụng Lip Lens trên điện thoại.
5. Tôi muốn kết nối tai nghe bằng bluetooth.
6. Máy quét laser đang hoạt động bình thường.
7. Sáng nay tôi định ra ngoài mua đồ nhưng trời mưa nên tôi ở nhà đọc sách và chờ đến chiều mới đi.

Then speak 2-3 spontaneous sentences about a topic of your choice, optionally
including a name or word you normally use. Wait silently for 6 seconds and end
the session once. The clip should take roughly 1-2 minutes, below the 5-minute limit.
Audio will determine what was actually said; do not assume the prompt was read exactly.

The scripted section is development diagnostics. Keep the spontaneous section
reserved when tuning on the scripted part, report it separately, and disclose
any later reuse. Preserve the original MP4 and original captions. Include empty
outputs and rejected intervals in coverage statistics, and review WER/CER on
the actual spoken transcript. Mark speech ends from audio for timing analysis;
server wall clocks and camera timestamps still require alignment before claiming
accurate phone-visible end-to-caption latency. Do not feed audio into visual inference.

## Research implications for implementation

- [Sub-word Level Lip Reading With Visual Attention](https://arxiv.org/abs/2110.07603)
  studies subword output and learned visual speech detection. The app already has
  subword output; replacing its motion heuristic with a trained visual activity
  classifier is a concrete next experiment, requiring relevant labeled data.
- [Official SentencePiece documentation](https://github.com/google/sentencepiece/blob/master/doc/special_symbols.md)
  describes byte fallback. It improves text representability, not unseen visual
  pronunciation learning. Changing the vocabulary/head requires a trained compatible model.
- [VALLR official implementation](https://github.com/MarshallT-99/VALLR) predicts
  phonemes from video and reconstructs text with a fine-tuned LLM. Its published
  [phoneme inventory](https://github.com/MarshallT-99/VALLR/blob/main/config.py)
  is English-oriented; it is not a drop-in Vietnamese checkpoint. A Vietnamese
  phoneme-to-text approach is a training/evaluation candidate, not a shipped feature.

Prioritize the upcoming real-phone error breakdown: crop/cadence, automatic
segmentation, decoder alternatives, then adaptation of the visual model. Test
LLM/context reranking on identical visual hypotheses with a latency budget and
separate raw output. The earlier small local selector did not improve WER, so
LLM remains off. Do not make free-form LLM rewriting look like visual evidence.
