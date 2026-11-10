"""Evidence checks for causal speech confirmation and empty references."""

from experiments.visual_activity_probe.frozen_captions import confirmation, score


def sample(time, *, probability=0.9, cost=60):
    return dict(
        time=time,
        window_start=time - 1.48,
        processing_ms=cost,
        crop_ms=10,
        quality="visible",
        score=probability,
    )


def test_confirmation_waits_for_the_second_result_to_finish():
    events = [sample(2.52), sample(2.64)]
    assert not confirmation(events, 1.0, 2.70)["confirmed"]
    assert confirmation(events, 1.0, 2.71)["confirmed"]


def test_preceding_turn_and_nonconsecutive_positives_cannot_confirm():
    assert not confirmation([sample(2.4), sample(2.52)], 1.0, 3)["confirmed"]
    assert not confirmation([sample(2.52), sample(2.64, probability=0.1), sample(2.76)], 1.0, 3)[
        "confirmed"
    ]


def test_unknown_short_turn_is_distinct_from_repeated_negative_evidence():
    short = confirmation([sample(1.56), sample(1.68)], 1.0, 2.0)
    negative = confirmation([sample(2.52, probability=0.1), sample(2.64, probability=0.1)], 1.0, 3)
    assert not short["confirmed"] and short["valid_windows"] == 0
    assert not negative["confirmed"] and negative["valid_windows"] == 2


def test_silence_has_insertion_counts_and_undefined_wer():
    result = score("", "có thể nói")
    assert result["wer"] is None and result["cer"] is None
    assert result["inserted_units_without_speech"] == 3
