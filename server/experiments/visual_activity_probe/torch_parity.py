"""Compare the CPU port to every cached upstream score on identical face pixels."""

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.services.vvad_model import CnnSpeechModel


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(args.threads)
    model = CnnSpeechModel.from_npz(args.weights)
    model.score(np.zeros((38, 96, 96, 3), dtype=np.uint8))
    reports = []
    for directory in args.input:
        info = json.loads((directory / "INPUT.json").read_text(encoding="utf8"))
        scores = json.loads((directory / "SCORES.json").read_text(encoding="utf8"))
        if scores["input_sha256"] != digest(directory / "INPUT.json"):
            raise ValueError("Source input identity changed")
        expected = next(m for m in scores["models"] if m["model"] == "CNN2Plus1D_Light")
        crops = np.load(directory / "face_rgb.npy", mmap_mode="r")
        events = [e for e in expected["events"] if e["score"] is not None]
        if args.max_windows:
            # Cover the full range including silence rather than only startup.
            indices = np.linspace(0, len(events) - 1, min(args.max_windows, len(events))).astype(
                int
            )
            events = [events[i] for i in indices]
        rows = []
        for e in events:
            crop = crops[e["index"] - 37 : e["index"] + 1]
            tick = time.perf_counter()
            score = model.score(crop)
            elapsed = (time.perf_counter() - tick) * 1000
            row = dict(
                index=e["index"],
                time=e["time"],
                upstream_score=e["score"],
                score=score,
                absolute_error=abs(score - e["score"]),
                milliseconds=elapsed,
                same_decision=(score >= 0.5) == (e["score"] >= 0.5),
            )
            rows.append(row)
        report = dict(
            input=str(directory),
            video_sha256=info["video_sha256"],
            scores_sha256=digest(directory / "SCORES.json"),
            crops_sha256=digest(directory / "face_rgb.npy"),
            windows=len(rows),
            max_absolute_error=max(r["absolute_error"] for r in rows),
            decision_disagreements=sum(not r["same_decision"] for r in rows),
            median_ms=statistics.median(r["milliseconds"] for r in rows),
            p95_ms=float(np.percentile([r["milliseconds"] for r in rows], 95)),
            events=rows,
        )
        reports.append(report)
        print(json.dumps({k: v for k, v in report.items() if k != "events"}), flush=True)
        result = dict(
            weights_sha256=digest(args.weights),
            torch_version=torch.__version__,
            cpu_threads=args.threads,
            smoke_only=bool(args.max_windows),
            absolute_tolerance=0.0001,
            reports=reports,
        )
        (args.output / "RESULTS.json").write_text(json.dumps(result, indent=2), encoding="utf8")
        if report["max_absolute_error"] > 0.0001 or report["decision_disagreements"]:
            raise ValueError("CPU conversion parity failed; do not enable the model")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--weights", type=Path, required=True)
    p.add_argument("--input", type=Path, nargs="+", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--max-windows", type=int)
    main(p.parse_args())
