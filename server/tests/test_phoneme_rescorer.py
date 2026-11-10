from types import SimpleNamespace

import torch

from app.services.native_engine import NativeAvsrEngine
from app.services.phoneme_rescorer import PhonemeRescorer


def test_reordered_caption_is_aligned_to_reordered_token_ids(monkeypatch):
    engine = NativeAvsrEngine.__new__(NativeAvsrEngine)
    engine._torch = torch
    model = torch.nn.Module()
    model.register_parameter("weight", torch.nn.Parameter(torch.zeros(1)))
    model.frontend = lambda x: x
    model.proj_encoder = lambda x: x
    model.encoder = lambda x, mask: (x, None)
    model.ctc = SimpleNamespace(log_softmax=lambda x: torch.zeros(1, 5, 4).log_softmax(-1))
    model.eos = 3
    model.decoder = SimpleNamespace()
    engine._model = model
    engine._use_incremental = True
    engine._cpu_ctc = True
    engine.tokens = ["<blank>", "one", "two", "<eos>"]
    engine._spm = SimpleNamespace(decode=lambda xs: " ".join(xs))
    engine.settings = SimpleNamespace(
        realtime_decoder="beam",
        realtime_beam_size=3,
        beam_size=3,
        nbest=3,
        ctc_weight=0.1,
        target_fps=25,
    )
    engine._beams = {
        3: lambda x: [
            SimpleNamespace(yseq=[3, 1, 3], score=-1),
            SimpleNamespace(yseq=[3, 2, 3], score=-2),
        ]
    }
    engine._phoneme_rescorer = SimpleNamespace(
        rank=lambda x, candidates: (list(reversed(candidates)), dict(applied=True))
    )
    captured = []

    def align(logp, ids, *args, **kwargs):
        captured.extend(ids)
        return [dict(text="two", start=0, end=0.2)]

    monkeypatch.setattr("app.services.native_engine.align_words", align)
    result = engine._decode_native(
        SimpleNamespace(tensor=torch.zeros(5, 4), num_frames=5, diagnostics={}), realtime=True
    )
    assert result.transcript == "two"
    assert captured == [2]
    assert all("_token_ids" not in c for c in result.alternatives)
    assert result.diagnostics["experimental_phoneme_rescoring"]["enabled"]


def test_unsupported_candidate_does_not_run_phoneme_head():
    from experiments.phoneme_probe.codec import UnsupportedSyllable

    rescorer = PhonemeRescorer.__new__(PhonemeRescorer)

    def unsupported(text):
        raise UnsupportedSyllable(text)

    rescorer.codec = SimpleNamespace(encode=unsupported)
    original = [dict(text="bluetooth", raw_score=-3)]
    output, detail = rescorer.rank(torch.zeros(12, 768), original)
    assert output is original
    assert detail == dict(applied=False, reason="unsupported_candidate_pronunciation")
