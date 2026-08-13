from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.config import Settings
from app.services.auto_avsr_engine import AutoAvsrEngine


def _reference_from_csv(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        words = [row["Word"].strip() for row in rows if row.get("Word")]
    return " ".join(words)


def _tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFC", text).casefold()
    return re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)


def _word_error_rate(reference: str, hypothesis: str) -> tuple[float, int]:
    expected = _tokens(reference)
    actual = _tokens(hypothesis)
    previous = list(range(len(actual) + 1))
    for row_index, expected_word in enumerate(expected, start=1):
        current = [row_index]
        for column_index, actual_word in enumerate(actual, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column_index] + 1,
                    previous[column_index - 1]
                    + (expected_word != actual_word),
                )
            )
        previous = current
    edits = previous[-1]
    return edits / max(1, len(expected)), edits


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Run the production adapter on a video and score a word CSV."
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--device", default="cpu", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--cpu-threads", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not args.video.is_file() or not args.csv.is_file():
        parser.error("Video and CSV must both exist.")

    os.environ["LIP_DEVICE"] = args.device
    os.environ["LIP_CPU_THREADS"] = str(args.cpu_threads)
    settings = Settings.from_env()
    engine = AutoAvsrEngine(settings)
    reference = _reference_from_csv(args.csv)

    print(
        f"Loading {settings.model_id} (requested device={args.device})...",
        flush=True,
    )
    started = time.perf_counter()
    result = engine.transcribe(
        args.video,
        input_kind="raw_face",
        context_hint=None,
    )
    elapsed_seconds = time.perf_counter() - started
    wer, edits = _word_error_rate(reference, result.transcript)
    payload = {
        "video": str(args.video.resolve()),
        "reference_csv": str(args.csv.resolve()),
        "model_id": settings.model_id,
        "reference": reference,
        "transcript": result.transcript,
        "alternatives": result.alternatives,
        "word_error_rate": round(wer, 6),
        "word_edits": edits,
        "reference_words": len(_tokens(reference)),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "num_frames": result.num_frames,
        "diagnostics": result.diagnostics,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Saved result to {args.output.resolve()}", flush=True)
    print(rendered, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
