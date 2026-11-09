"""Stress confirmation with speech suffixes and their natural trailing pause.

These are existing utterance fragments, NOT new complete short spoken phrases.
No frames are stitched, padded, repeated or inferred from the transcript.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.visual_activity_probe.frozen_captions import confirmation, digest, write


def main(args):
    if args.output.exists():
        raise FileExistsError(args.output)
    rows = []
    hashes = []
    for scene in (1, 2):
        probe = args.probes / f"wifi_scene{scene:02}_transport_v2"
        info = json.loads((probe / "INPUT.json").read_text(encoding="utf8"))
        data = json.loads((probe / "SCORES.json").read_text(encoding="utf8"))
        if data["input_sha256"] != digest(probe / "INPUT.json"):
            raise ValueError("Cached classifier input mismatch")
        ref_path = args.probes / f"SCENE{scene:02}_AUDIO_ENDPOINTS.json"
        ref = json.loads(ref_path.read_text(encoding="utf8"))
        if ref["video_sha256"] != info["video_sha256"]:
            raise ValueError("Boundary/video hash mismatch")
        scores = next(m["events"] for m in data["models"] if m["model"] == "CNN2Plus1D_Light")
        for e in scores:
            e["crop_ms"] = info["frames"][e["index"]]["crop_ms"]
        hashes.append(dict(scene=scene, video_sha256=info["video_sha256"],
                           scores_sha256=digest(probe / "SCORES.json"),
                           boundary_sha256=digest(ref_path)))
        for index, ref in enumerate(ref["thresholds"]["0.5"]):
            for duration in (0.4, 0.6, 0.8, 1.0, 1.4, 1.8, 2.4):
                start = ref["end"] - duration
                if start < ref["start"]:
                    continue
                release = ref["end"] + 1.0
                decision = confirmation(scores, start, release)
                rows.append(dict(scene=scene, reference_index=index,
                                 speech_suffix_seconds=duration, assumed_turn_start=start,
                                 audio_end_estimate=ref["end"], release=release, **decision))
    summary = []
    for duration in sorted({r["speech_suffix_seconds"] for r in rows}):
        group = [r for r in rows if r["speech_suffix_seconds"] == duration]
        summary.append(dict(speech_suffix_seconds=duration, cases=len(group),
                            confirmed=sum(r["confirmed"] for r in group),
                            unconfirmed=sum(not r["confirmed"] for r in group),
                            no_complete_window=sum(r["valid_windows"] == 0 for r in group)))
    write(args.output, dict(scope=__doc__, protocol={
        "threshold": 0.5, "positive_pairs": 2, "silence_wait_seconds": 1.0,
        "turn_start": "estimated utterance end minus suffix duration, with no extra pre-roll",
        "scores": "existing causal full windows wholly after assumed turn start",
        "normalization": "unchanged continuous face crops; no cold face-detector restart",
    }, production_changed=False, hashes=hashes, summary=summary, cases=rows,
        limits=["Assumed motion onset/endpoint, not rerun endpoint detector",
                "Suffixes can begin inside a word; this diagnoses confirmation latency, not short-word WER",
                "All cases reuse two videos; not independent trials",
                "Missing full classifier context means unknown, not evidence of silence"]))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--probes", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    main(p.parse_args())
