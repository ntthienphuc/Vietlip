"""Compare causal visual gates against estimated audio boundaries, offline only."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.services.visual_activity import EndpointPolicy, Observation


def references(path):
    data = json.loads(path.read_text(encoding="utf8"))
    if "thresholds" in data:
        # Use intersection for unambiguous speech; union for unambiguous silence.
        middle = data["thresholds"]["0.5"]
        certain = []
        for r in middle:
            intersections = [(r["start"], r["end"])]
            for key in ("0.4", "0.6"):
                intersections = [
                    (max(a, s["start"]), min(b, s["end"]))
                    for a, b in intersections
                    for s in data["thresholds"][key]
                    if max(a, s["start"]) < min(b, s["end"])
                ]
            certain.extend(intersections)
        possible = [(r["start"], r["end"]) for rows in data["thresholds"].values() for r in rows]
        return middle, certain, possible, data["scope"]
    rows = data["segments"]
    certain = [
        (r["audio_start_estimate"], r["audio_end_estimate"])
        for r in rows
        if r["audio_start_estimate"] is not None
    ]
    possible = [
        (
            r["audio_start_estimate"] if r["audio_start_estimate"] is not None else r["start"],
            r["audio_end_estimate"],
        )
        for r in rows
    ]
    middle = [
        dict(id=r["id"], start=a, end=b, onset_known=r["audio_start_estimate"] is not None)
        for r, (a, b) in zip(rows, possible)
    ]
    return middle, certain, possible, data["boundary_scope"]


def label_window(start, end, certain, possible, margin=0.16):
    if any(a + margin <= start and end <= b - margin for a, b in certain):
        return True
    if not any(start <= b + margin and end >= a - margin for a, b in possible):
        return False
    return None


def turns_from_events(events, classifier, duration):
    gate, turns, active = EndpointPolicy(), [], None
    for row in events:
        valid = row["quality"] == "visible" and row["score"] is not None
        score = (2.0 if row["score"] >= 0.5 else 0.0) if classifier and valid else row["score"]
        update = gate.observe(row["time"], Observation(score or 0, row["quality"]))
        if update.start is not None:
            if active is not None:
                raise ValueError("Overlapping turns")
            active = dict(start=update.start, detected_at=row["time"])
        if update.end is not None:
            if active is None:
                raise ValueError("End without start")
            active.update(end=update.end, finalized_at=row["time"], reason=update.reason)
            turns.append(active)
            active = None
    if active is not None:
        active.update(end=duration, finalized_at=duration, reason="session_stop")
        turns.append(active)
    return turns


def overlap(a, b, c, d):
    return max(0.0, min(b, d) - max(a, c))


def compare_turns(turns, refs):
    rows = []
    for i, ref in enumerate(refs):
        indices = [
            j
            for j, t in enumerate(turns)
            if overlap(ref["start"], ref["end"], t["start"], t["end"]) > 0
        ]
        covered = sum(
            overlap(ref["start"], ref["end"], turns[j]["start"], turns[j]["end"]) for j in indices
        )
        row = dict(
            reference_index=i,
            start=ref["start"],
            end=ref["end"],
            overlapping_turns=indices,
            covered_seconds=round(covered, 3),
            duration_seconds=round(ref["end"] - ref["start"], 3),
        )
        if indices:
            first = turns[indices[0]]
            if ref.get("onset_known", True):
                row["missing_prefix_seconds"] = round(max(0, first["start"] - ref["start"]), 3)
                row["onset_detection_delay_seconds"] = round(first["detected_at"] - ref["start"], 3)
            else:
                row["onset_unknown"] = True
            if len(indices) == 1:
                t = turns[indices[0]]
                other = [
                    k
                    for k, r in enumerate(refs)
                    if k != i and overlap(r["start"], r["end"], t["start"], t["end"]) > 0
                ]
                row["merged_with_references"] = other
                if not other and t.get("reason") == "visual_pause":
                    row["finalization_after_estimated_end_seconds"] = round(
                        t["finalized_at"] - ref["end"], 3
                    )
                elif not other:
                    row["end_reason"] = t.get("reason", "unknown")
        rows.append(row)
    false_turns = [
        j
        for j, t in enumerate(turns)
        if not any(
            overlap(t["start"], t["end"], r["start"] - 0.16, r["end"] + 0.16) > 0 for r in refs
        )
    ]
    return dict(
        reference_intervals=rows,
        false_turn_indices=false_turns,
        total_reference_seconds=sum(r["duration_seconds"] for r in rows),
        total_covered_seconds=sum(r["covered_seconds"] for r in rows),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.input / "REPORT.json"
    if output.exists():
        raise FileExistsError(output)
    info = json.loads((args.input / "INPUT.json").read_text(encoding="utf8"))
    scores = json.loads((args.input / "SCORES.json").read_text(encoding="utf8"))
    if (
        scores["input_sha256"]
        != hashlib.sha256((args.input / "INPUT.json").read_bytes()).hexdigest()
    ):
        raise ValueError("Input changed since scoring")
    refs, certain, possible, scope = references(args.references)
    motion_events = [
        dict(index=r["index"], time=r["time"], **r["motion"])
        for r in info["frames"]
        if "motion" in r
    ]
    results = []
    for model in [dict(model="production_motion_replay", events=motion_events)] + scores["models"]:
        classifier = model["model"] != "production_motion_replay"
        events = model["events"]
        turns = turns_from_events(events, classifier, info["duration_seconds"])
        result = dict(model=model["model"], turns=turns, **compare_turns(turns, refs))
        if classifier:
            counts = dict(
                true_speech=0,
                missed_speech=0,
                true_silence=0,
                false_speech=0,
                ambiguous=0,
                unavailable=0,
                buffering=0,
            )
            for e in events:
                if e["score"] is None:
                    counts["buffering" if e["quality"] == "buffering" else "unavailable"] += 1
                    continue
                label = label_window(e["window_start"], e["time"], certain, possible)
                if label is None:
                    counts["ambiguous"] += 1
                elif label:
                    counts["true_speech" if e["score"] >= 0.5 else "missed_speech"] += 1
                else:
                    counts["false_speech" if e["score"] >= 0.5 else "true_silence"] += 1
            result["unambiguous_windows"] = counts
        runtime = [e["processing_ms"] for e in events if "processing_ms" in e]
        result["inference_median_ms"] = float(np.median(runtime))
        result["inference_p95_ms"] = float(np.percentile(runtime, 95))
        results.append(result)
    report = dict(
        video_sha256=info["video_sha256"],
        duration_seconds=info["duration_seconds"],
        input_pipeline=info.get("input_pipeline", "original decoded resolution"),
        references_sha256=hashlib.sha256(args.references.read_bytes()).hexdigest(),
        reference_scope=scope,
        threshold=0.5,
        window_frames=38,
        stride_frames=3,
        boundary_exclusion_seconds=0.16,
        endpoint_policy="existing 3 positive samples, pre-roll 0.45s, silence 1.0s, tail 0.24s",
        crop_median_ms=float(np.median([r["crop_ms"] for r in info["frames"]])),
        limits=[
            "Offline deterministic frame replay, not phone camera or LAN timing",
            "Speech boundaries are estimates unless explicitly annotated in reference scope",
            "Classifier decisions have trailing 1.52s context; scores are not calibrated",
            "Gate timing excludes crop/inference/network/caption decoding time",
            "No recognition decoder invoked; these are not WER/CER improvements",
        ],
        production_changed=False,
        models=results,
    )
    output.write_text(json.dumps(report, indent=2), encoding="utf8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
