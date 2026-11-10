from app.services.caption_stability import AgreementTimeline
from app.services.live_trace import LiveTrace
import json


def words(text, offset=0.0):
    return [
        dict(text=w, start=offset + i * 0.3, end=offset + (i + 1) * 0.3)
        for i, w in enumerate(text.split())
    ]


def test_single_window_guess_is_not_shown_or_joined_to_revision():
    timeline = AgreementTimeline()
    assert timeline.update(words("không thay đổi"), 0, 2)["transcript"] == ""
    assert timeline.update(words("hôm nay tôi"), 0, 3.5)["transcript"] == ""
    update = timeline.update(words("hôm nay tôi muốn"), 0, 5)
    assert update["transcript"] == "hôm nay tôi"
    assert update["unstable_transcript"] == "muốn"
    assert (
        timeline.update(words("hôm nay tôi muốn thử"), 0, 5.5, final=True)["transcript"]
        == "hôm nay tôi muốn thử"
    )


def test_same_cached_decode_is_not_two_independent_votes():
    timeline = AgreementTimeline()
    for _ in range(3):
        assert timeline.update(words("xin chào"), 0, 2)["transcript"] == ""
    assert timeline.update(words("xin chào"), 0, 2, final=True)["transcript"] == "xin chào"


def test_right_edge_waits_and_repeated_words_and_turns_are_preserved():
    timeline = AgreementTimeline()
    timeline.update(words("rất rất tốt", 1), 0, 2)
    assert timeline.update(words("rất rất tốt", 1.04), 0, 2.5)["transcript"] == "rất"
    assert (
        timeline.update(words("rất rất tốt", 1.08), 0, 3.5, final=True)["transcript"]
        == "rất rất tốt"
    )
    assert (
        timeline.update(words("rất rất tốt"), 5, 7, final=True)["transcript"]
        == "rất rất tốt rất rất tốt"
    )


def test_long_speech_does_not_lose_prefix_outside_next_window():
    timeline = AgreementTimeline()
    timeline.update(words("tôi muốn uống nước"), 0, 2)
    result = timeline.update(words("nước ấm", 0.1), 0.8, 3)
    assert result["expired_committed_words"] == 3
    result = timeline.update(words("nước ấm", 0.1), 0.8, 3.5, final=True)
    assert result["transcript"] == "tôi muốn uống nước ấm"


def test_committed_caption_never_changes_when_a_later_window_disagrees():
    timeline = AgreementTimeline()
    timeline.update(words("bạn có thể"), 0, 2)
    first = timeline.update(words("bạn có thể giúp"), 0, 3.5)["transcript"]
    later = timeline.update(words("bạn có ghế giúp tôi"), 0, 4.5, final=True)["transcript"]
    assert first == "bạn có thể"
    assert later.startswith(first + " ")
    assert later == "bạn có thể giúp tôi"


def test_trace_keeps_raw_and_visible_text_but_no_frame_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("LIP_REALTIME_TRACE_DIR", str(tmp_path))
    trace = LiveTrace()
    trace.record(dict(type="ack", sequence=0))
    trace.record(dict(type="partial", transcript="xin", window_transcript="xin chào"))
    trace.close()
    rows = [
        json.loads(line)
        for line in next(tmp_path.iterdir()).read_text(encoding="utf8").splitlines()
    ]
    assert len(rows) == 1 and rows[0]["transcript"] == "xin"
    assert rows[0]["window_transcript"] == "xin chào" and rows[0]["wall_seconds"] >= 0


def test_failed_decode_does_not_confirm_or_resurrect_unshown_words():
    timeline = AgreementTimeline()
    timeline.update(words("xin chào"), 0, 2)
    timeline.discard_pending()
    assert timeline.update(words("xin chào"), 0, 3.5)["transcript"] == ""
    timeline.discard_pending()
    assert timeline.update(words("tạm biệt"), 5, 7, final=True)["transcript"] == "tạm biệt"


def test_revision_with_same_onset_and_longer_span_does_not_duplicate_spoken_slot():
    timeline = AgreementTimeline()
    original = [
        dict(text="mấy", start=0.96, end=1.0),
        dict(text="quẹt", start=1.2, end=1.48),
        dict(text="lấy", start=1.64, end=1.68),
    ]
    timeline.update(original, 10, 13)
    timeline.update(original, 10, 14)
    revised = original[:2] + [
        dict(text="lái", start=1.64, end=1.76),
        dict(text="do", start=1.96, end=2.0),
    ]
    update = timeline.update(revised, 10, 14.5, final=True)
    assert update["transcript"] == "mấy quẹt lấy do"


def test_adjacent_short_words_are_not_removed_by_overlap_guard():
    timeline = AgreementTimeline()
    original = [dict(text="rất", start=0.4, end=0.44)]
    timeline.update(original, 0, 2)
    timeline.update(original, 0, 3)
    revised = original + [
        dict(text="rất", start=0.44, end=0.48),
        dict(text="tốt", start=0.52, end=0.56),
    ]
    assert timeline.update(revised, 0, 4, final=True)["transcript"] == "rất rất tốt"
