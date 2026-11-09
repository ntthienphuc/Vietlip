"""Evaluate the two previously dev-selected averages on frozen Wi-Fi tensors.

No new mixture/weight is selected using these phone recordings. Original model
files stay read-only. This does not supersede prior phone regressions.
"""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.services.caption_stability import AgreementTimeline
from app.services.native_engine import NativeAvsrEngine
from app.services.video_preprocessor import PreparedVideo
from experiments.checkpoint_soup import load_average
from experiments.visual_activity_probe.frozen_captions import digest, score, write
from scripts.benchmark_models import settings


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    baseline = json.loads((args.frozen / "RESULTS.json").read_text(encoding="utf8"))
    engine = NativeAvsrEngine(replace(settings(args.models / "SO_seed17.pt", device="cuda", beam=3),
                                     precision="float32", nbest=3, ctc_weight=0.1))
    engine.load()
    assert engine._phoneme_rescorer is None
    paths = [args.models / f"{group}_seed{seed}.pt" for group in ("SO", "WW") for seed in (17, 29, 43)]
    results = []
    for name, sources in [("all_average", paths),
                          ("so17_all_average_50pct", [paths[0]]*6+paths)]:
        provenance = load_average(engine, sources)
        directory = args.output / name
        directory.mkdir()
        clips = []
        for clip in baseline["clips"]:
            scene = clip["clip"]
            original = [json.loads(line) for line in (args.frozen / scene / "WINDOWS.jsonl").read_text(encoding="utf8").splitlines()]
            timeline = AgreementTimeline()
            durations = []
            for r in original:
                path = Path(r["tensor_file"])
                if digest(path) != r["tensor_file_sha256"]:
                    raise ValueError("Tensor file mismatch")
                saved = torch.load(path, map_location="cpu", weights_only=True)
                tensor = saved["tensor"]
                if hashlib.sha256(tensor.numpy().tobytes()).hexdigest() != r["tensor_sha256"]:
                    raise ValueError("Tensor pixel mismatch")
                prepared = PreparedVideo(tensor, len(tensor), saved["diagnostics"])
                tick = time.perf_counter()
                result = engine._decode_native(prepared, realtime=True)
                torch.cuda.synchronize()
                elapsed = (time.perf_counter()-tick)*1000
                durations.append(elapsed)
                event = r["event"]
                aligned = result.diagnostics.get("words", [])
                if aligned:
                    caption = timeline.update(aligned, event["window_start"], event["window_end"],
                                              final=event["type"] == "segment_final", right_context=1.0)
                else:
                    timeline.discard_pending()
                    caption = dict(transcript=timeline.text)
                with (directory / (scene+".jsonl")).open("a", encoding="utf8") as stream:
                    stream.write(json.dumps(dict(index=r["index"], event=event,
                        tensor_sha256=r["tensor_sha256"], transcript=result.transcript,
                        words=aligned, caption=caption, decode_ms=elapsed), ensure_ascii=False)+"\n")
            # These references score saved predictions; never supplied to a model.
            ref_file = args.scenes / ("REFERENCE_CONFIRMED.json" if scene == "scene01"
                                     else scene.upper()+"_REFERENCE_CONFIRMED.json")
            refs = json.loads(ref_file.read_text(encoding="utf8"))["sentences"]
            row = dict(scene=scene, transcript=timeline.text,
                       **score(" ".join(refs), timeline.text), windows=len(original))
            clips.append(row)
            print(name, scene, row["word_errors"], "/", row["reference_units"], flush=True)
        results.append(dict(model=name, provenance=provenance, clips=clips))
        write(args.output / "RESULTS.json", dict(scope=__doc__,
              baseline_results_sha256=digest(args.frozen / "RESULTS.json"),
              production_changed=False, models=results))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ("frozen", "scenes", "models", "output"):
        p.add_argument("--"+flag, type=Path, required=True)
    main(p.parse_args())
