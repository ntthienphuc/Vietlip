"""Guard against future-frame leakage and misleading endpoint metrics in the probe."""

import numpy as np
import pytest

from experiments.visual_activity_probe import prepare, report
from experiments.visual_activity_probe.confirm import confirm_turn


def test_causal_sampler_never_uses_the_next_decoded_frame(monkeypatch):
    class Capture:
        def __init__(self, _):
            self.index = -1

        def isOpened(self):
            return True

        def read(self):
            self.index += 1
            return (
                (True, np.full((2, 2, 3), self.index, np.uint8))
                if self.index < 4
                else (False, None)
            )

        def get(self, _):
            return self.index * 100.0

        def release(self):
            pass

    monkeypatch.setattr(prepare.cv2, "VideoCapture", Capture)
    frames = list(prepare.causal_frames("unused.mp4"))
    assert [round(t, 2) for _, t, _, _ in frames] == [0, 0.04, 0.08, 0.12, 0.16, 0.2, 0.24, 0.28]
    assert [int(rgb[0, 0, 0]) for _, _, _, rgb in frames] == [0, 0, 0, 1, 1, 2, 2, 2]
    assert all(source <= sample + 1e-7 for _, sample, source, _ in frames)


def test_boundary_and_partial_speech_windows_are_not_clean_negative_examples():
    certain, possible = [(2.0, 5.0)], [(2.0, 5.0), (8.0, 10.0)]
    assert report.label_window(2.2, 4.8, certain, possible) is True
    assert report.label_window(0.0, 1.8, certain, possible) is False
    assert report.label_window(1.9, 2.5, certain, possible) is None
    assert report.label_window(8.2, 9.8, certain, possible) is None


def test_unavailable_visual_classifier_is_not_treated_as_positive():
    events = [
        dict(index=i * 3, time=i * 0.12, quality="face_unavailable", score=None) for i in range(50)
    ]
    assert report.turns_from_events(events, classifier=True, duration=6.0) == []


def test_merged_turn_does_not_get_two_independent_latency_successes():
    turns = [dict(start=0.5, end=9.0, detected_at=1.0, finalized_at=10.0)]
    refs = [dict(start=1.0, end=4.0), dict(start=5.0, end=8.0)]
    result = report.compare_turns(turns, refs)
    assert result["total_covered_seconds"] == pytest.approx(6.0)
    assert [r["merged_with_references"] for r in result["reference_intervals"]] == [[1], [0]]
    assert all(
        "finalization_after_estimated_end_seconds" not in r for r in result["reference_intervals"]
    )


def test_confirmation_cannot_use_scores_from_before_turn_or_after_endpoint():
    turn = dict(start=2.0, finalized_at=5.0)

    def event(t, start, score=0.9):
        return dict(time=t, window_start=start, score=score, quality="visible")

    early = [event(2.8, 1.32), event(2.92, 1.44)]
    late = [event(5.04, 3.56), event(5.16, 3.68)]
    assert confirm_turn(turn, early + late) is None
    assert confirm_turn(turn, early + [event(3.6, 2.12), event(3.72, 2.24)] + late) == 3.72
    assert confirm_turn(turn, [event(3.6, 2.12), event(3.72, 2.24, 0.1), event(3.84, 2.36)]) is None
