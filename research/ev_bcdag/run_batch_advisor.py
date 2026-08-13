from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cdag.deployment import EVBCDAGController  # noqa: E402


def _read_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        source = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        source = payload.get("results", payload) if isinstance(payload, dict) else payload

    rows = []
    seen = set()
    for index, item in enumerate(source):
        if item.get("mode") not in {None, "visual_only"}:
            continue
        sample_id = str(item.get("sample_id") or item.get("video") or index)
        if sample_id in seen:
            continue
        seen.add(sample_id)
        alternatives = item.get("auto_nbest") or item.get("alternatives") or []
        normalized = [
            {
                "text": str(candidate.get("text") or ""),
                "score": float(
                    candidate.get("score", candidate.get("raw_score", 0.0))
                ),
            }
            for candidate in alternatives
            if str(candidate.get("text") or "").strip()
        ]
        transcript = str(item.get("auto_top1") or item.get("transcript") or "")
        if not normalized and transcript:
            normalized = [{"text": transcript, "score": 0.0}]
        if not transcript or not normalized:
            continue
        rows.append(
            {
                "sample_id": sample_id,
                "auto_top1": transcript,
                "auto_nbest": normalized,
                "frame_count": int(item.get("frame_count") or item.get("num_frames") or 1),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the frozen EV-B-C-DAG pre-verifier routing diagnostic."
    )
    parser.add_argument("input", type=Path, help="JSON/JSONL Auto-AVSR result rows")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = _read_rows(args.input)
    if not rows:
        parser.error("No usable Auto-AVSR rows were found")
    if len(rows) > 256:
        parser.error("One frozen accounting window accepts at most 256 rows")

    controller = EVBCDAGController(ROOT / "frozen_ev_bcdag")
    invoked, risks, utilities = controller.route_window(rows)
    decisions = [
        {
            "sample_id": row["sample_id"],
            "recommend_av_hubert_verifier": bool(call),
            "auto_risk": round(float(risk), 8),
            "expected_verifier_utility": round(float(utility), 8),
            "transcript_owner": "auto",
        }
        for row, call, risk, utility in zip(rows, invoked, risks, utilities)
    ]
    output = {
        "schema": "ev-b-cdag-batch-advisor-v1",
        "status": "research_diagnostic_not_production",
        "window_rows": len(rows),
        "canonical_window_rows": int(
            controller.policy["accounting_window_requests"]
        ),
        "complete_canonical_window": len(rows)
        == int(controller.policy["accounting_window_requests"]),
        "verifier_budget_fraction": float(
            controller.policy["invocation_fraction"]
        ),
        "recommended_verifier_calls": int(invoked.sum()),
        "verifier_executed": False,
        "final_decision_available": False,
        "warning": (
            "The frozen one-shot EV-B-C-DAG missed its coverage gate by 0.6447 "
            "percentage points and its risk models predate the deployed epoch-13 "
            "checkpoint. This command reproduces pre-verifier routing only; it "
            "neither runs AV-HuBERT nor changes the Auto-AVSR transcript."
        ),
        "decisions": decisions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()
