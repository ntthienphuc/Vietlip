# Application method review

The decision is application accuracy, stable captions and latency on this phone.
The phoneme experiment is optional. No benchmark prompt/reference is provided to
visual inference, weight averaging or the live decoder.

## Methods inspected and practical decisions

- **Model soups:** [Wortsman et al., ICML 2022](https://proceedings.mlr.press/v162/wortsman22a.html)
  motivates averaging checkpoints fine-tuned from a common initializer. The six
  app checkpoints have the same initializer hash. We implemented strict state
  compatibility checks, read-only sources and float32 averaging. This adds no
  per-window model evaluations. The paper's gains are not evidence of gains in
  Vietnamese; the app's paired evaluation determines adoption.
- **VALLR:** the [official implementation](https://github.com/MarshallT-99/VALLR)
  has a visual phoneme CTC model followed by a fine-tuned language model. Its
  [phoneme inventory](https://github.com/MarshallT-99/VALLR/blob/main/config.py)
  uses English ARPAbet symbols. Its reported LRS3 result is not a Vietnamese phone
  result. The app already tested a Vietnamese phoneme branch and an independent
  lexicon decoder; complete-caption errors increased. A generic language-model
  rewrite is therefore not enabled in production. The earlier restricted LLM
  experiment also failed to improve errors and added latency.
- **Vietnamese ResNet3D/Zipformer:** the [2025 HUST paper](https://onlinelibrary.wiley.com/doi/full/10.1155/mse/2087573)
  describes a transducer model and reports 27.14% WER on its own dataset. The
  examined article provides architecture/training details but no verified model
  download for direct use here. Its published score cannot be compared directly
  to this app's phone sessions. A usable checkpoint would justify a new comparison;
  recreating its training is not a small application patch.
- **MultiVSR:** the [official repository](https://github.com/Sindhu-Hegde/multivsr)
  supplies multilingual checkpoints and video inference. Its tokenizer contains
  a Vietnamese language token, which by itself does not establish Vietnamese
  visual training or accuracy. No Vietnamese deployment gain is claimed from
  this repository, and its weights were not substituted into this app.
- **VLR data:** the [Zenodo release](https://zenodo.org/records/19709456) is a video
  and transcript dataset, not a new app-ready pretrained model. Local parent Lip
  data and weights were inspected and reused without modifying their originals.
  A new 70.5 GB download is not needed for the present paired checks.
- **Timing evaluation:** [Silero VAD](https://github.com/snakers4/silero-vad)
  is used only in an isolated offline audit of the recorded audio. Version 6.2.3
  is installed under `artifacts/app_finalize_20261109/eval_deps`, outside the live
  server environment. Threshold sensitivity and spurious extra activity are
  retained; these are automatic timing estimates, not human word-end labels.

## Stop rule for this application iteration

Compare the existing seven checkpoints, three uniform averages and three SO17
interpolations with fixed visual tensors and boundaries. Choose each experiment's
candidate on development WER/CER only. Check reserved corpus windows, all four
complete captions and the physical Android transport/render path before adoption.
Do not keep tuning weights against the four known phone scripts.

Keep the best supported phone configuration if a candidate improves corpus data
but regresses phone captions. Retain the alternative and its full results for
reproduction. This is a bounded practical selection, not proof of a globally
optimal model or high-accuracy free-form speech recognition.

No new training or Vast rental is needed for these inference-only comparisons.
Future training should add independently labeled camera recordings and a separate
acceptance set; fitting the existing phone scripts would not demonstrate general
recognition of unseen speech.
