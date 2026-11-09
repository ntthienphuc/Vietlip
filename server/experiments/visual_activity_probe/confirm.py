"""Offline check: preserve motion boundaries, confirm speech before decoding.

Two successive positive causal classifier windows must be wholly inside the
motion turn and available before its finalization. No live gate is modified.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.visual_activity_probe.report import compare_turns, references


def confirm_turn(turn, events):
    previous = None
    for e in events:
        if e["time"] > turn["finalized_at"]:
            break
        valid = (
            e["score"] is not None
            and e["quality"] == "visible"
            and e.get("window_start", -1) >= turn["start"]
            and e["score"] >= 0.5
        )
        if valid and previous is not None and e["time"] - previous <= 0.121:
            return e["time"]
        previous = e["time"] if valid else None
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    args = parser.parse_args()
    output = args.input / "CONFIRMATION.json"
    if output.exists():
        raise FileExistsError(output)
    scores = json.loads((args.input / "SCORES.json").read_text(encoding="utf8"))
    original = json.loads(args.report.read_text(encoding="utf8"))
    if scores["video_sha256"] != original["video_sha256"]:
        raise ValueError("Report and scores belong to different videos")
    baseline = next(m for m in original["models"] if m["model"] == "production_motion_replay")
    refs, _, _, scope = references(args.references)
    models = []
    for model in scores["models"]:
        decisions, kept = [], []
        for i, turn in enumerate(baseline["turns"]):
            when = confirm_turn(turn, model["events"])
            row = dict(turn_index=i, accepted=when is not None, confirmed_at=when)
            if when is not None:
                kept.append(turn)
                row["extra_wait_after_two_second_decode_minimum"] = round(
                    max(0, when - (turn["start"] + 2.0)), 3
                )
            decisions.append(row)
        models.append(dict(model=model["model"], decisions=decisions, **compare_turns(kept, refs)))
    result = dict(
        video_sha256=original["video_sha256"],
        reference_scope=scope,
        policy="two consecutive scores >=0.5, full window after original start, decision before finalization",
        production_changed=False,
        limits=[
            "Diagnostic only; no decoder run, no WER claim",
            "Confirmation timestamps exclude classifier and transport execution time",
            "A rejected motion turn is not proven silent; measure missed real utterances",
            "Speech clips alone cannot validate rejection; inspect confirmed non-speech recordings",
        ],
        models=models,
    )
    output.write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
