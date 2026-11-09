"""Score a confirmed live script without assuming one detected turn per sentence."""

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import unicodedata


def units(text):
    text = unicodedata.normalize("NFC", text).lower()
    return "".join(" " if unicodedata.category(c).startswith("P") else c for c in text).split()


def distance(reference, hypothesis):
    row = list(range(len(hypothesis) + 1))
    for i, a in enumerate(reference, 1):
        old, row = row, [i]
        for j, b in enumerate(hypothesis, 1):
            row.append(min(row[-1] + 1, old[j] + 1, old[j - 1] + (a != b)))
    return row[-1]


def score(reference, hypothesis):
    ref, hyp = units(reference), units(hypothesis)
    chars, guesses = "".join(ref), "".join(hyp)
    we, ce = distance(ref, hyp), distance(chars, guesses)
    return dict(
        word_errors=we,
        reference_units=len(ref),
        wer=we / len(ref) if ref else None,
        character_errors=ce,
        reference_characters=len(chars),
        cer_no_spaces=ce / len(chars) if chars else None,
    )


def summarize(values):
    values = [v for v in values if v is not None]
    return (
        dict(count=len(values), min=min(values), median=statistics.median(values), max=max(values))
        if values
        else None
    )


def evaluate(events, reference):
    if not reference.get("reference_status", "").startswith("speaker_confirmed"):
        raise ValueError("Reference must be explicitly speaker_confirmed before scoring")
    finals = [e for e in events if e["type"] == "session_final"]
    if len(finals) != 1:
        raise ValueError("Expected exactly one completed session; do not score a truncated trace")
    session = finals[0]
    captions = [e for e in events if e["type"] in {"partial", "segment_final"}]
    acks = {e["caption_event_id"]: e for e in events if e["type"] == "caption_render_ack"}
    endpoints = [e for e in captions if e["type"] == "segment_final"]
    revisions, previous = [], ""
    for e in captions:
        text = e["transcript"]
        if previous and text != previous and not text.startswith(previous + " "):
            revisions.append(
                dict(caption_event_id=e["caption_event_id"], before=previous, after=text)
            )
        previous = text
    turns, previous = [], ""
    for e in endpoints:
        cumulative = e["transcript"]
        turns.append(
            dict(
                turn_id=e["turn_id"],
                window_start=e["window_start"],
                window_end=e["window_end"],
                endpoint_reason=e.get("endpoint_reason"),
                added_text=cumulative[len(previous) :].strip()
                if cumulative.startswith(previous)
                else None,
                raw_last_window=e["window_transcript"],
                render_receipt=acks.get(e["caption_event_id"]),
            )
        )
        previous = cumulative
    visible = [e for e in captions if e["transcript"].strip()]
    return dict(
        reference_status=reference["reference_status"],
        normalization="NFC lowercase; punctuation removed; Vietnamese whitespace units; CER excludes spaces; numerals not expanded",
        reference_sentences=reference["sentences"],
        transcript=session["transcript"],
        session_score=score(" ".join(reference["sentences"]), session["transcript"]),
        session_seconds=session["wall_seconds"],
        received_frames=session["received_frames"],
        capture_gaps_over_500ms=session["capture_gaps"],
        caption_fps=summarize([e["capture_fps"] for e in captions]),
        automatic_segments=len(endpoints),
        reference_sentence_count=len(reference["sentences"]),
        caption_events=len(captions),
        render_receipts=len(acks),
        missing_render_receipt_ids=[
            e["caption_event_id"] for e in captions if e["caption_event_id"] not in acks
        ],
        first_nonempty_caption_server_seconds=visible[0]["wall_seconds"] if visible else None,
        first_nonempty_caption_receipt_seconds=acks.get(visible[0]["caption_event_id"], {}).get(
            "wall_seconds"
        )
        if visible
        else None,
        final_window_to_render_ack_ms=summarize(
            [
                acks.get(e["caption_event_id"], {}).get("window_end_to_render_ack_ms")
                for e in endpoints
            ]
        ),
        final_window_to_server_caption_ms=summarize(
            [e.get("window_end_to_caption_ms") for e in endpoints]
        ),
        server_send_to_render_ack_ms=summarize(
            [e["server_send_to_render_ack_ms"] for e in acks.values()]
        ),
        phone_receive_to_flutter_frame_ms=summarize(
            [e["receive_to_flutter_frame_ms"] for e in acks.values()]
        ),
        preprocessing_ms=summarize(
            [e.get("engine_runtime", {}).get("preprocess_ms") for e in captions]
        ),
        decoding_ms=summarize([e.get("engine_runtime", {}).get("decode_ms") for e in captions]),
        evidence=session["evidence"],
        incomplete=session["incomplete"],
        visible_prefix_revisions=revisions,
        turns=turns,
        limits=[
            "Turns are not aligned one-to-one to reference sentences.",
            "Visual padded window end is not acoustic speech end.",
            "Render ACK includes return network delay and Flutter post-frame, not physical scanout.",
            "A missing receipt is not proof that the caption was absent on screen.",
            "Trace contains no source video; different scene recordings are not paired model comparisons.",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.trace.read_bytes()
    result = evaluate(
        [json.loads(line) for line in raw.decode("utf8").splitlines()],
        json.loads(args.reference.read_text(encoding="utf8")),
    )
    result["trace_sha256"] = hashlib.sha256(raw).hexdigest()
    result["reference_sha256"] = hashlib.sha256(args.reference.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in {"turns", "reference_sentences", "transcript", "limits", "normalization"}
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
