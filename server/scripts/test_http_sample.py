from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from scripts.run_sample import _reference_from_csv, _word_error_rate


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Exercise the real HTTP upload contract and calculate WER."
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:7100")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument(
        "--mode",
        choices=("visual_only", "context_select", "llm_assist"),
        default="visual_only",
    )
    parser.add_argument("--context-hint")
    parser.add_argument("--accept-llm-risk", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode != "visual_only" and not args.context_hint:
        parser.error("--context-hint is required for an LLM mode")
    if args.mode != "visual_only" and not args.accept_llm_risk:
        parser.error("--accept-llm-risk is required for an LLM mode")

    reference = _reference_from_csv(args.csv)
    results = []
    with httpx.Client(timeout=httpx.Timeout(1200.0, connect=10.0)) as client:
        health_before = client.get(f"{args.base_url}/healthz").raise_for_status().json()
        for index in range(max(1, args.runs)):
            started = time.perf_counter()
            with args.video.open("rb") as handle:
                response = client.post(
                    f"{args.base_url}/v1/transcriptions",
                    files={"video": (args.video.name, handle, "video/mp4")},
                    data={
                        "input_kind": "raw_face",
                        "mode": args.mode,
                        "context_hint": args.context_hint or "",
                        "accept_llm_risk": str(args.accept_llm_risk).lower(),
                    },
                )
            response.raise_for_status()
            payload = response.json()
            wer, edits = _word_error_rate(reference, payload["transcript"])
            results.append(
                {
                    "run": index + 1,
                    "http_elapsed_seconds": round(
                        time.perf_counter() - started, 3
                    ),
                    "api_elapsed_ms": payload["elapsed_ms"],
                    "transcript": payload["transcript"],
                    "assisted_transcript": payload["assisted_transcript"],
                    "processing_mode": payload["processing_mode"],
                    "risk_notice": payload["risk_notice"],
                    "word_error_rate": round(wer, 6),
                    "word_edits": edits,
                    "diagnostics": payload["diagnostics"],
                }
            )
        health_after = client.get(f"{args.base_url}/healthz").raise_for_status().json()

    report = {
        "video": str(args.video.resolve()),
        "reference": reference,
        "mode": args.mode,
        "context_hint": args.context_hint,
        "health_before": health_before,
        "health_after": health_after,
        "runs": results,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Saved result to {args.output.resolve()}", flush=True)
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
