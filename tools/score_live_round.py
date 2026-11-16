"""Score a saved real session using its actual AI replies, plus optional :free replay.

Only raw visual text is submitted to the alternative provider. The reference is
opened after provider requests finish. All media, references and results stay local.
"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))


def normalize(text):
    return " ".join(re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFC", text).lower()).split())


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        next_row = [i]
        for j, y in enumerate(b, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j - 1] + (x != y)))
        row = next_row
    return row[-1]


def score(reference, hypothesis):
    a, b = normalize(reference).split(), normalize(hypothesis).split()
    ac, bc = "".join(a), "".join(b)
    we, ce = distance(a, b), distance(ac, bc)
    return dict(
        word_errors=we,
        reference_words=len(a),
        wer=we / len(a) if a else None,
        character_errors=ce,
        reference_characters=len(ac),
        cer=ce / len(ac) if ac else None,
    )


def read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def committed_segments(events):
    previous, segments = "", []
    for event in events:
        if event.get("type") not in {"segment_final", "session_final"}:
            continue
        text = (event.get("stable_transcript") or event.get("transcript") or "").strip()
        if previous and text != previous and not text.startswith(previous + " "):
            raise ValueError("Cumulative source changed; review this session before scoring")
        added = text[len(previous) :].strip()
        if added:
            segments.append(added)
        previous = text
    return previous, segments


async def run(args):
    from app.services.transcript_rewrite import RewriteRequest, TranscriptRewriter

    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.output / "REPORT.json"
    if report_path.exists():
        raise FileExistsError("Report exists; preserve it and use a new output directory")
    events = read_jsonl(args.live_trace)
    raw, segments = committed_segments(events)
    rows = [
        r
        for p in args.ai_trace
        for r in read_jsonl(p)
        if str(r.get("sentence_id", "")).startswith(args.client_session + "-")
    ]
    replies = {}
    for row in rows:
        key = row["sentence_id"]
        if key in replies:
            raise ValueError("Duplicate actual AI reply; review request provenance")
        replies[key] = row
    actual, alternative, delivered = [], [], []
    service = TranscriptRewriter()
    for i, source in enumerate(segments, 1):
        key = f"{args.client_session}-{i}"
        row = replies.get(key)
        if row is not None and row.get("source_text") != source:
            raise ValueError("Actual AI input does not match this source segment")
        actual.append(row)
        delivered.append(
            row["text"] if row and row["status"] in {"completed", "unchanged"} else source
        )
        if args.openrouter:
            cache = args.output / f"openrouter-{i:03d}.json"
            source_hash = hashlib.sha256(source.encode()).hexdigest()
            if cache.exists():
                cached = json.loads(cache.read_text(encoding="utf-8"))
                if cached["source_sha256"] != source_hash:
                    raise ValueError("Cached alternative belongs to different source text")
                output = cached["output"]
            else:
                output = (
                    await service.rewrite(
                        RewriteRequest(
                            text=source,
                            method="recovery",
                            provider="openrouter",
                            sentence_id=f"audit-{args.client_session}-{i}",
                        )
                    )
                ).model_dump()
                cache.write_text(
                    json.dumps(
                        dict(source_sha256=source_hash, output=output), ensure_ascii=False, indent=2
                    ),
                    encoding="utf-8",
                )
                # Keep comfortably below OpenRouter's shared 20 RPM free limit.
                await asyncio.sleep(3.2)
            alternative.append(output)
    # References enter only the scorer, after text-only provider calls.
    reference_record = json.loads(args.reference.read_text(encoding="utf-8-sig"))
    reference = reference_record.get("reference_text") or " ".join(reference_record["sentences"])
    outputs = {"visual": raw, "groq_delivered": " ".join(delivered)}
    if args.openrouter:
        outputs["openrouter_delivered"] = " ".join(
            r["text"] if r["status"] in {"completed", "unchanged"} else s
            for s, r in zip(segments, alternative)
        )
    timings = [r["elapsed_ms"] for r in actual if r and r["status"] in {"completed", "unchanged"}]
    report = dict(
        client_session=args.client_session,
        live_trace=str(args.live_trace),
        live_trace_sha256=hashlib.sha256(args.live_trace.read_bytes()).hexdigest(),
        complete=any(e.get("type") == "session_final" for e in events),
        reference_status=args.reference_status,
        reference=reference,
        source_segments=len(segments),
        actual_groq_replies=sum(r is not None for r in actual),
        actual_groq_unavailable=sum(r is None or r["status"] == "unavailable" for r in actual),
        transcripts=outputs,
        metrics={name: score(reference, text) for name, text in outputs.items()},
        groq_ai_ms=dict(
            median=statistics.median(timings) if timings else None,
            maximum=max(timings) if timings else None,
        ),
        actual_replies=actual,
        openrouter_alternative=alternative,
        failed_ai_policy="Retain source text; do not drop unavailable cases from total WER.",
        audio_sent_to_llm=False,
        reference_sent_to_llm=False,
        acoustic_end_to_display_measured=False,
    )
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "complete",
                    "reference_status",
                    "source_segments",
                    "actual_groq_replies",
                    "metrics",
                )
            },
            ensure_ascii=True,
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-trace", type=Path, required=True)
    parser.add_argument("--ai-trace", type=Path, action="append", required=True)
    parser.add_argument("--client-session", required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument(
        "--reference-status",
        choices=["script-unconfirmed", "script-user-confirmed", "audio-audited"],
        default="script-unconfirmed",
    )
    parser.add_argument("--openrouter", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
