"""Transfer check of mirror-proposal expansion, scored only on original pixels.

The rule is exploratory: frozen after observing the new Wi-Fi scenes. Older
phone recordings and the long video are additional regression checks, not an
independent product test. Baseline is rerun on every identical archived tensor.
"""

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.services.native_engine import NativeAvsrEngine
from app.services.video_preprocessor import PreparedVideo
from experiments.phoneme_probe.evaluate_direct import captions
from experiments.phoneme_probe.score_direct_candidates import score_candidates
from experiments.visual_activity_probe.frozen_captions import digest, write
from scripts.benchmark_models import settings


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    source_path = args.archive / "SO_seed17_EVAL.json"
    rows = json.loads(source_path.read_text(encoding="utf8"))["live"]
    write(args.output / "INPUT.json", dict(
        scope=__doc__, archive_sha256=digest(source_path), source_sha256=digest(__file__),
        checkpoint_sha256=digest(args.checkpoint),
        rule="Union of identity/mirror beam3, exact original-image attention/CTC score, no weighting search",
        rejection="Any older phone-caption regression rejects production adoption",
        source_rows=len(rows), production_changed=False, audio_used=False,
    ))
    engine = NativeAvsrEngine(replace(settings(args.checkpoint, device="cuda", beam=3),
                                     precision="float32", nbest=3, ctc_weight=0.1))
    engine.load()
    if engine._phoneme_rescorer is not None:
        raise ValueError("Expected the standard decoder")
    model = engine._model
    completed = []
    for index, row in enumerate(rows):
        key = hashlib.sha256(row["id"].encode()).hexdigest()[:24]
        path = args.archive / "pixels" / (key + ".pt")
        tensor = torch.load(path, map_location="cpu", weights_only=True)
        if hashlib.sha256(tensor.numpy().tobytes()).hexdigest() != row["tensor_sha256"]:
            raise ValueError("Archived pixels changed")
        decoded, durations = {}, {}
        for name, pixels in (("baseline", tensor), ("mirror", tensor.flip(-1))):
            torch.cuda.synchronize()
            tick = time.perf_counter()
            decoded[name] = engine._decode_native(PreparedVideo(pixels, len(pixels), {}), realtime=True)
            torch.cuda.synchronize()
            durations[name] = (time.perf_counter() - tick) * 1000
        texts = list(dict.fromkeys(c["text"] for name in ("baseline", "mirror")
                                  for c in decoded[name].alternatives))
        excluded = [text for text in texts if engine._text(
            [i + 1 for i in engine._spm.encode(text, out_type=int)]) != text]
        candidates = [dict(text=text) for text in texts if text not in excluded]
        if not candidates:
            raise ValueError("No losslessly retokenizable candidate")
        torch.cuda.synchronize()
        tick = time.perf_counter()
        with torch.inference_mode():
            features = model.frontend(tensor.to(engine.device_label).unsqueeze(0))
            encoded = model.encoder(model.proj_encoder(features), None)[0][0].float()
            scored = score_candidates(engine, encoded, candidates)
            del encoded, features
        torch.cuda.synchronize()
        durations["rescore"] = (time.perf_counter() - tick) * 1000
        if not all(math.isfinite(c["native_score"]) for c in scored):
            raise ValueError("Nonfinite score")
        chosen = max(scored, key=lambda item: item["native_score"])
        item = dict(id=row["id"], clip=row["clip"], event=row["event"],
                    tensor_sha256=row["tensor_sha256"], excluded_nonroundtripping_texts=excluded,
                    candidates=scored, variants={
                        "baseline": dict(text=decoded["baseline"].transcript,
                                         words=decoded["baseline"].diagnostics["words"]),
                        "expanded": chosen,
                    }, durations_ms=durations,
                    baseline_matches_archive=decoded["baseline"].transcript == row["candidates"][0]["text"])
        completed.append(item)
        with (args.output / "WINDOWS.jsonl").open("a", encoding="utf8") as stream:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
        if (index + 1) % 10 == 0 or index + 1 == len(rows):
            print(f"{index + 1}/{len(rows)} saved", flush=True)
    # Caption references enter only now, after all model output is persisted.
    manifest = dict(clips=[])
    for path in args.manifest:
        manifest["clips"].extend(json.loads(path.read_text(encoding="utf8"))["clips"])
    evaluations = {}
    for variant in ("baseline", "expanded"):
        records = [dict(id=r["id"], clip=r["clip"], event=r["event"],
                        candidates=[r["variants"][variant]]) for r in completed]
        evaluations[variant] = captions(records, manifest)
    timings = {}
    for clip in evaluations["baseline"]:
        selected = [r for r in completed if r["clip"] == clip]
        timings[clip] = dict(baseline_median_ms=statistics.median(
            r["durations_ms"]["baseline"] for r in selected),
            expanded_serial_median_ms=statistics.median(sum(r["durations_ms"].values()) for r in selected))
    regressions = [clip for clip in evaluations["baseline"] if clip.startswith("phone_")
                   and evaluations["expanded"][clip]["errors"] > evaluations["baseline"][clip]["errors"]]
    write(args.output / "RESULTS.json", dict(scope=__doc__, variants=evaluations, timings=timings,
        baseline_archive_mismatches=sum(not r["baseline_matches_archive"] for r in completed),
        phone_regressions=regressions, production_changed=False,
        reference_manifest_hashes={str(path): digest(path) for path in args.manifest}))
    print(json.dumps(dict(phone_regressions=regressions, errors={key: {
        clip: value["errors"] for clip, value in values.items()} for key, values in evaluations.items()})), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("archive", "checkpoint", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    main(parser.parse_args())
