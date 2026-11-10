import torch
from experiments.phoneme_probe.prepare_windows import complete_word_core, window_spans
from experiments.phoneme_probe.train_windows import core_logits


def test_cut_words_are_not_given_whole_word_labels():
    timing = [
        dict(text="a", start=0, end=0.5),
        dict(text="b", start=0.5, end=1.0),
        dict(text="c", start=1.0, end=1.5),
    ]
    chosen, left, right = complete_word_core(timing, 5, 32)
    assert [w["text"] for w in chosen] == ["b"]
    assert (left, right) == (7, 20)


def test_window_grid_stops_at_observed_frame_and_has_rolling_windows():
    spans = window_spans(195)
    assert all(0 <= a < b <= 195 and b - a <= 150 for a, b in spans)
    assert (45, 195) in spans
    assert (0, 50) in spans
    assert len(spans) == len(set(spans))


def test_ctc_core_excludes_partial_edge_frames_without_detaching_gradients():
    logits = torch.randn(2, 10, 4, requires_grad=True)
    examples = [
        dict(row=dict(loss_start=2, loss_stop=7)),
        dict(row=dict(loss_start=1, loss_stop=9)),
    ]
    values, lengths = core_logits(logits, examples)
    assert lengths.tolist() == [5, 8]
    values[0, :, 1].sum().backward()
    assert logits.grad[0, :2].abs().sum() == 0
    assert logits.grad[0, 2].abs().sum() > 0
    assert logits.grad[0, 7:].abs().sum() == 0
