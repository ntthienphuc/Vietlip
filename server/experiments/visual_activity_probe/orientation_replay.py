"""Paired horizontal-orientation audit on frozen phone recognition windows.

This is a finite input-sensitivity experiment, not a trained augmentation or an
ensemble. Baseline and mirror share checkpoint, timestamps and caption policy.
References are opened only after every prediction is persisted. Oracle n-best
selection is a labeled diagnostic, never a deployable decoder.
"""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.services.caption_stability import AgreementTimeline
from app.services.native_engine import NativeAvsrEngine
from app.services.video_preprocessor import PreparedVideo
from experiments.visual_activity_probe.frozen_captions import digest, score, write
from scripts.benchmark_models import settings


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    sources = {f"scene{i:02}": args.frozen / f"scene{i:02}" for i in (1, 2, 3)}
    sources["scene04"] = args.scene4 / "frozen_v1"
    checkpoint_hash = digest(args.checkpoint)
    manifests = {}
    for name, directory in sources.items():
        manifests[name] = dict(path=str(directory.resolve()),
                               windows_sha256=digest(directory / "WINDOWS.jsonl"))
    write(args.output / "INPUT.json", dict(
        scope=__doc__, checkpoint_sha256=checkpoint_hash, source_sha256=digest(__file__),
        clips=manifests, development_clips=["scene01", "scene02"],
        additional_checks=["scene03_silence", "scene04_short_phrases"],
        rule="Reject mirror if either development speech clip has more errors; no per-scene choice",
        transformations={"baseline": "identity", "mirror": "torch.flip(tensor, dims=(-1,))"},
        audio_used_for_prediction=False, reference_used_for_prediction=False,
        production_changed=False,
    ))
    engine = NativeAvsrEngine(replace(settings(args.checkpoint, device="cuda", beam=3),
                                     precision="float32", nbest=3, ctc_weight=0.1))
    engine.load()
    if engine._phoneme_rescorer is not None:
        raise ValueError("Expected the unmodified SO17 decoder")
    all_rows = {}
    for name, directory in sources.items():
        timelines = {variant: AgreementTimeline() for variant in ("baseline", "mirror")}
        output = args.output / name
        output.mkdir()
        original = read_rows(directory / "WINDOWS.jsonl")
        recorded = []
        for row in original:
            path = directory / f"{row['index']:03}.pt"
            if digest(path) != row["tensor_file_sha256"]:
                raise ValueError(f"Changed tensor file: {path}")
            saved = torch.load(path, map_location="cpu", weights_only=True)
            tensor = saved["tensor"]
            pixel_hash = hashlib.sha256(tensor.numpy().tobytes()).hexdigest()
            if pixel_hash != row["tensor_sha256"]:
                raise ValueError(f"Changed tensor pixels: {path}")
            if tensor.ndim != 4 or tuple(tensor.shape[-2:]) != (88, 88):
                raise ValueError(f"Unexpected tensor shape: {tuple(tensor.shape)}")
            variants = {}
            # Alternate execution order to avoid assigning every cold call to one arm.
            order = ("baseline", "mirror") if row["index"] % 2 == 0 else ("mirror", "baseline")
            for variant in order:
                transformed = tensor if variant == "baseline" else tensor.flip(-1)
                prepared = PreparedVideo(transformed, len(tensor), dict(saved["diagnostics"]))
                torch.cuda.synchronize()
                tick = time.perf_counter()
                decoded = engine._decode_native(prepared, realtime=True)
                torch.cuda.synchronize()
                elapsed = (time.perf_counter() - tick) * 1000
                event = row["event"]
                timeline = timelines[variant]
                aligned = decoded.diagnostics.get("words", [])
                previous = timeline.text
                if aligned:
                    caption = timeline.update(aligned, event["window_start"], event["window_end"],
                                              final=event["type"] == "segment_final", right_context=1.0)
                else:
                    timeline.discard_pending()
                    caption = dict(transcript=timeline.text)
                variants[variant] = dict(
                    transcript=decoded.transcript, alternatives=decoded.alternatives,
                    words=aligned, caption=caption, decode_ms=elapsed,
                    output_tensor_sha256=hashlib.sha256(transformed.numpy().tobytes()).hexdigest(),
                    prefix_revised=bool(previous and timeline.text != previous
                                        and not timeline.text.startswith(previous + " ")),
                )
            item = dict(index=row["index"], event=row["event"], tensor_sha256=pixel_hash,
                        archived_transcript=row["transcript"], variants=variants)
            recorded.append(item)
            with (output / "WINDOWS.jsonl").open("a", encoding="utf8") as stream:
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")
            print(f"{name} {row['index'] + 1}/{len(original)} saved", flush=True)
        all_rows[name] = recorded
    # All outputs exist before any textual reference is opened.
    results = []
    for name, rows in all_rows.items():
        reference_file = (args.scene4 / "REFERENCE_CONFIRMED.json" if name == "scene04" else
                          args.scenes / ("REFERENCE_CONFIRMED.json" if name == "scene01" else
                                         name.upper() + "_REFERENCE_CONFIRMED.json"))
        references = json.loads(reference_file.read_text(encoding="utf8"))["sentences"]
        variants = {}
        for variant in ("baseline", "mirror"):
            final_text = rows[-1]["variants"][variant]["caption"]["transcript"]
            durations = [row["variants"][variant]["decode_ms"] for row in rows]
            variants[variant] = dict(transcript=final_text, **score(" ".join(references), final_text),
                                     median_decode_ms=statistics.median(durations),
                                     max_decode_ms=max(durations),
                                     prefix_revisions=sum(row["variants"][variant]["prefix_revised"]
                                                          for row in rows))
        result = dict(scene=name, windows=len(rows), reference_sha256=digest(reference_file),
                      archived_transcript_mismatches=sum(
                          row["archived_transcript"] != row["variants"]["baseline"]["transcript"]
                          for row in rows), variants=variants)
        if name == "scene04":
            finals = [row for row in rows if row["event"]["type"] == "segment_final"]
            if len(finals) != len(references):
                raise ValueError("Final-window diagnostic needs one endpoint per confirmed phrase")
            result["final_window_diagnostic"] = []
            for row, reference in zip(finals, references, strict=True):
                arms = {}
                for variant in ("baseline", "mirror"):
                    decoded = row["variants"][variant]
                    candidates = [dict(text=item["text"], **score(reference, item["text"]))
                                  for item in decoded["alternatives"]]
                    arms[variant] = dict(top1=score(reference, decoded["transcript"]),
                                         oracle_top3_errors=min(item["word_errors"] for item in candidates),
                                         candidates=candidates)
                result["final_window_diagnostic"].append(dict(index=row["index"], variants=arms))
        results.append(result)
    speech = [row for row in results if row["scene"] in ("scene01", "scene02")]
    candidate_passes = all(row["variants"]["mirror"]["word_errors"] <=
                           row["variants"]["baseline"]["word_errors"] for row in speech)
    candidate_improves = sum(row["variants"]["mirror"]["word_errors"] for row in speech) < sum(
        row["variants"]["baseline"]["word_errors"] for row in speech)
    write(args.output / "RESULTS.json", dict(
        scope=__doc__, clips=results,
        mirror_passes_development_rule=candidate_passes and candidate_improves,
        production_changed=False,
        limitations=["Same saved tensors before the declared transform; no native JPEG reconstruction",
                     "Single speaker and reused development recordings; no generalization claim",
                     "Decode timing excludes face alignment, endpoint waiting, network and phone render",
                     "Oracle selection reads answers and is not a usable recognition algorithm"],
    ))
    print(json.dumps(dict(results=[dict(scene=row["scene"], variants={
        key: value["word_errors"] for key, value in row["variants"].items()}) for row in results],
        mirror_passes=candidate_passes and candidate_improves)), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("frozen", "scenes", "scene4", "checkpoint", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    main(parser.parse_args())
