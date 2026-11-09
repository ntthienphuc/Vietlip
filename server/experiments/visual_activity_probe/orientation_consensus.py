"""Fixed equal-weight two-view rescoring of unprompted visual hypotheses.

Candidates are the union of the prior identity/mirror top-three visual decodes.
Each receives full teacher-forced attention and CTC scores under both images.
No reference text, language-model rewrite, score fitting or per-clip choice is
allowed. References are read only after every candidate score has been saved.
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
from app.services.caption_stability import AgreementTimeline
from app.services.native_engine import NativeAvsrEngine
from experiments.phoneme_probe.score_direct_candidates import score_candidates
from experiments.visual_activity_probe.frozen_captions import digest, score, write
from experiments.visual_activity_probe.orientation_replay import read_rows
from scripts.benchmark_models import settings


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    source = json.loads((args.orientation / "INPUT.json").read_text(encoding="utf8"))
    if digest(args.checkpoint) != source["checkpoint_sha256"]:
        raise ValueError("Checkpoint differs from candidate generator")
    write(args.output / "INPUT.json", dict(
        scope=__doc__, source_input_sha256=digest(args.orientation / "INPUT.json"),
        source_sha256=digest(__file__), scorer_sha256=digest(
            Path(__file__).resolve().parents[1] / "phoneme_probe" / "score_direct_candidates.py"),
        joint_score="0.5 * original_visual_score + 0.5 * mirrored_visual_score",
        alignment="original image CTC alignment of the chosen text",
        rule="No speech development regression and lower total errors, then no scene04 regression",
        checkpoint_sha256=source["checkpoint_sha256"], audio_used=False, production_changed=False,
    ))
    engine = NativeAvsrEngine(replace(settings(args.checkpoint, device="cuda", beam=3),
                                     precision="float32", nbest=3, ctc_weight=0.1))
    engine.load()
    if engine._phoneme_rescorer is not None:
        raise ValueError("Expected no phoneme or language model rescorer")
    model = engine._model
    all_rows = {}
    for name, manifest in source["clips"].items():
        directory = Path(manifest["path"])
        if digest(directory / "WINDOWS.jsonl") != manifest["windows_sha256"]:
            raise ValueError("Frozen input manifest changed")
        originals = {r["index"]: r for r in read_rows(directory / "WINDOWS.jsonl")}
        rows = read_rows(args.orientation / name / "WINDOWS.jsonl")
        timelines = {key: AgreementTimeline() for key in ("union_original", "joint")}
        output = args.output / name
        output.mkdir()
        completed = []
        for row in rows:
            path = directory / f"{row['index']:03}.pt"
            if digest(path) != originals[row["index"]]["tensor_file_sha256"]:
                raise ValueError("Changed frozen tensor file")
            tensor = torch.load(path, map_location="cpu", weights_only=True)["tensor"]
            if hashlib.sha256(tensor.numpy().tobytes()).hexdigest() != row["tensor_sha256"]:
                raise ValueError("Changed frozen pixels")
            texts = list(dict.fromkeys(item["text"] for view in ("baseline", "mirror")
                                      for item in row["variants"][view]["alternatives"]))
            if not texts or len(texts) > 6:
                raise ValueError("Unexpected candidate union")
            # A partial decode can end in an incomplete UTF-8 byte-piece. Its
            # displayed replacement character cannot recover the original IDs.
            # Exclude it explicitly instead of scoring a silently changed text.
            excluded = [text for text in texts if engine._text(
                [i + 1 for i in engine._spm.encode(text, out_type=int)]) != text]
            candidates = [dict(text=text) for text in texts if text not in excluded]
            if not candidates:
                raise ValueError("No losslessly retokenizable proposal; keep baseline and reject experiment")
            scored = {}
            torch.cuda.synchronize()
            tick = time.perf_counter()
            with torch.inference_mode():
                for view in ("baseline", "mirror"):
                    pixels = tensor if view == "baseline" else tensor.flip(-1)
                    features = model.frontend(pixels.to(engine.device_label).unsqueeze(0))
                    encoded = model.encoder(model.proj_encoder(features), None)[0][0].float()
                    scored[view] = score_candidates(engine, encoded, candidates)
                    del encoded, features
            torch.cuda.synchronize()
            rescore_ms = (time.perf_counter() - tick) * 1000
            scores = []
            for a, b in zip(scored["baseline"], scored["mirror"], strict=True):
                if a["text"] != b["text"]:
                    raise ValueError("Mismatched candidate order")
                value = (a["native_score"] + b["native_score"]) / 2
                if not math.isfinite(value):
                    raise ValueError("Nonfinite visual score; reject experiment")
                scores.append(dict(text=a["text"], original_score=a["native_score"],
                                   mirror_score=b["native_score"], joint_score=value, words=a["words"]))
            arms = {}
            event = row["event"]
            for variant, field in (("union_original", "original_score"), ("joint", "joint_score")):
                chosen = max(scores, key=lambda item: item[field])
                timeline = timelines[variant]
                previous = timeline.text
                if chosen["words"]:
                    caption = timeline.update(chosen["words"], event["window_start"], event["window_end"],
                                              final=event["type"] == "segment_final", right_context=1.0)
                else:
                    timeline.discard_pending()
                    caption = dict(transcript=timeline.text)
                arms[variant] = dict(transcript=chosen["text"], caption=caption,
                                     prefix_revised=bool(previous and timeline.text != previous
                                                       and not timeline.text.startswith(previous + " ")))
            item = dict(index=row["index"], event=event, tensor_sha256=row["tensor_sha256"],
                        excluded_nonroundtripping_texts=excluded,
                        candidates=scores, variants=arms, rescore_with_reencoding_ms=rescore_ms,
                        offline_serial_total_estimate_ms=rescore_ms + sum(
                            row["variants"][v]["decode_ms"] for v in ("baseline", "mirror")))
            completed.append(item)
            with (output / "WINDOWS.jsonl").open("a", encoding="utf8") as stream:
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")
            print(f"{name} {row['index'] + 1}/{len(rows)} rescored", flush=True)
        all_rows[name] = completed
    baseline = json.loads((args.orientation / "RESULTS.json").read_text(encoding="utf8"))
    original_results = {row["scene"]: row for row in baseline["clips"]}
    results = []
    for name, rows in all_rows.items():
        path = (args.scene4 / "REFERENCE_CONFIRMED.json" if name == "scene04" else
                args.scenes / ("REFERENCE_CONFIRMED.json" if name == "scene01" else
                               name.upper() + "_REFERENCE_CONFIRMED.json"))
        if digest(path) != original_results[name]["reference_sha256"]:
            raise ValueError("Reference changed since paired baseline")
        reference = " ".join(json.loads(path.read_text(encoding="utf8"))["sentences"])
        variants = {"baseline": original_results[name]["variants"]["baseline"]}
        for key in ("union_original", "joint"):
            text = rows[-1]["variants"][key]["caption"]["transcript"]
            variants[key] = dict(transcript=text, **score(reference, text),
                                 prefix_revisions=sum(r["variants"][key]["prefix_revised"] for r in rows))
        results.append(dict(scene=name, windows=len(rows), variants=variants,
                            median_rescore_with_reencoding_ms=statistics.median(
                                r["rescore_with_reencoding_ms"] for r in rows),
                            median_offline_serial_total_estimate_ms=statistics.median(
                                r["offline_serial_total_estimate_ms"] for r in rows)))
    dev = [row for row in results if row["scene"] in ("scene01", "scene02")]
    passes = all(r["variants"]["joint"]["word_errors"] <= r["variants"]["baseline"]["word_errors"]
                 for r in dev) and sum(r["variants"]["joint"]["word_errors"] for r in dev) < sum(
                     r["variants"]["baseline"]["word_errors"] for r in dev)
    write(args.output / "RESULTS.json", dict(scope=__doc__, clips=results,
        joint_passes_development_rule=passes, production_changed=False,
        limitations=["Timing is a serial estimate with redundant encoding, not live end-to-display latency",
                     "Two-view candidates are visual outputs; no new words are invented by a language model",
                     "Single-speaker repeated recordings cannot establish unseen-speaker accuracy"]))
    print(json.dumps(dict(joint_passes=passes, results=[dict(scene=r["scene"], errors={
        k: v["word_errors"] for k, v in r["variants"].items()}) for r in results])), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("orientation", "checkpoint", "output", "scenes", "scene4"):
        parser.add_argument("--" + flag, type=Path, required=True)
    main(parser.parse_args())
