"""Reference normalization and endpoint reconstruction must not hide errors."""

import importlib.util
from pathlib import Path
import unicodedata

import pytest

spec = importlib.util.spec_from_file_location(
    "live_round_score", Path(__file__).parents[2] / "tools/score_live_round.py"
)
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def test_case_punctuation_and_unicode_form_do_not_count_as_errors():
    assert scorer.score("Xin chào, bạn.", unicodedata.normalize("NFD", "xin chào bạn"))["wer"] == 0
    assert scorer.score("Xin chào, bạn.", "xin chào bạn")["cer"] == 0


def test_missing_source_words_still_count():
    result = scorer.score("tôi muốn uống nước", "tôi muốn")
    assert result["word_errors"] == 2 and result["reference_words"] == 4
    assert result["wer"] == 0.5
    assert scorer.score("xin chào", "")["wer"] == 1


def test_insertions_can_exceed_one_hundred_percent_and_tones_are_retained():
    assert scorer.score("xin chào", "xin chào cảm ơn bạn")["wer"] == 1.5
    assert scorer.score("ma", "má")["word_errors"] == 1


def test_endpoint_reconstruction_ignores_partial_and_duplicate_packets():
    events = [
        {"type": "partial", "transcript": "xin"},
        {"type": "segment_final", "transcript": "xin chào"},
        {"type": "segment_final", "transcript": "xin chào"},
        {"type": "partial", "transcript": "xin chào xin"},
        {"type": "session_final", "transcript": "xin chào xin chào"},
    ]
    assert scorer.committed_segments(events) == ("xin chào xin chào", ["xin chào", "xin chào"])


def test_rewritten_cumulative_source_requires_manual_review():
    with pytest.raises(ValueError):
        scorer.committed_segments(
            [
                {"type": "segment_final", "transcript": "xin chào"},
                {"type": "session_final", "transcript": "chị chào"},
            ]
        )


def test_late_success_does_not_improve_live_score_and_remains_raw():
    late = dict(status="completed", text="corrected", elapsed_ms=85000)
    assert scorer.delivered_text("raw", late) == "raw"
    assert scorer.deliverable(late) is False
    assert scorer.delivered_text("raw", dict(late, elapsed_ms=1000)) == "corrected"
    assert scorer.delivered_text("raw", dict(late, status="unavailable", elapsed_ms=20)) == "raw"
    assert scorer.delivered_text("raw", None) == "raw"
