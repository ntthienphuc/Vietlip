"""Compare complete captions on frozen archived window times, mapped onto MP4.

The mapping is a declared new replay clock, NOT a reconstruction of live JPEGs.
References are read only after inference. Candidate scores never enter VSR.
"""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

import cv2
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.services.caption_stability import AgreementTimeline
from app.services.live_evidence import check_live_images
from app.services.native_engine import NativeAvsrEngine
from app.services.realtime import decode_jpeg_frames
from experiments.phoneme_probe.codec import edit_distance, words
from experiments.visual_activity_probe.prepare import causal_frames
from scripts.benchmark_models import settings


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def confirmation(events, start, release, offset=0.0):
    """Only a pair computed before release can authorize that decode window.

Offset expresses MP4 time minus archived capture time. Completion includes the
measured classifier and crop calls, but excludes concurrent execution/queuing.
"""
    previous = None
    valid_count = 0
    for e in events:
        available = e["time"] + (e.get("processing_ms", 0) + e.get("crop_ms", 0)) / 1000
        if available > release + offset + 1e-7:
            continue
        valid = (e.get("score") is not None and e["quality"] == "visible"
                 and e.get("window_start", -1) >= start + offset - 1e-7)
        if valid:
            valid_count += 1
        positive = valid and e["score"] >= 0.5
        if positive and previous is not None and e["time"] - previous <= 0.121:
            return dict(confirmed=True, available_at=available-offset,
                        valid_windows=valid_count)
        previous = e["time"] if positive else None
    return dict(confirmed=False, available_at=None, valid_windows=valid_count)


def score(reference, hypothesis):
    a, b = words(reference), words(hypothesis)
    ac, bc = "".join(a), "".join(b)
    return dict(word_errors=edit_distance(a, b), reference_units=len(a),
                wer=edit_distance(a, b)/len(a) if a else None,
                character_errors=edit_distance(ac, bc), reference_characters=len(ac),
                cer=edit_distance(ac, bc)/len(ac) if ac else None,
                inserted_units_without_speech=len(b) if not a else None)


def evaluate(records, clip, scores, references):
    results = []
    for policy, offset in [("baseline", 0), ("cnn_confirmation", 0),
                           ("cnn_confirmation", -0.5), ("cnn_confirmation", 0.5)]:
        timeline = AgreementTimeline()
        rows, previous, revisions = [], "", []
        for r in records:
            e = r["event"]
            decision = confirmation(scores, e["turn_start"], e["release_seconds"], offset)
            accepted = policy == "baseline" or decision["confirmed"]
            if accepted and r.get("words"):
                update = timeline.update(r["words"], e["window_start"], e["window_end"],
                                         final=e["type"] == "segment_final", right_context=1.0)
            else:
                timeline.discard_pending()
                update = dict(transcript=timeline.text)
            text = update["transcript"]
            if previous and text != previous and not text.startswith(previous + " "):
                revisions.append(dict(before=previous, after=text, index=r["index"]))
            previous = text
            rows.append(dict(index=r["index"], event=e, gate=decision, accepted=accepted,
                             caption=update))
        results.append(dict(policy=policy, assumed_score_clock_offset_seconds=offset,
                            transcript=timeline.text, **score(" ".join(references), timeline.text),
                            accepted_windows=sum(r["accepted"] for r in rows),
                            rejected_windows=sum(not r["accepted"] for r in rows),
                            visible_prefix_revisions=revisions, events=rows))
    return dict(clip=clip, results=results)


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    config = replace(settings(args.checkpoint, device="cuda", beam=3), precision="float32",
                     nbest=3, realtime_beam_size=3, ctc_weight=0.1)
    engine = NativeAvsrEngine(config)
    engine.load()
    assert engine._phoneme_rescorer is None
    checkpoint_hash = digest(args.checkpoint)
    manifest, decoded = [], []
    for scene in (1, 2, 3):
        name = f"scene{scene:02}"
        probe = args.probes / f"wifi_{name}_transport_v2"
        info = json.loads((probe / "INPUT.json").read_text(encoding="utf8"))
        video = Path(info["video"])
        if digest(video) != info["video_sha256"]:
            raise ValueError("Video hash mismatch")
        trace = args.scenes / f"SCENE{scene:02}_ORIGINAL_TRACE.jsonl"
        original = [json.loads(line) for line in trace.read_text(encoding="utf8").splitlines()]
        starts = {e["turn_id"]: e["speech_start"] for e in original if "speech_start" in e}
        events = []
        for e in original:
            if e["type"] not in ("partial", "segment_final"):
                continue
            events.append(dict(type=e["type"], turn_id=e["turn_id"],
                               turn_start=starts[e["turn_id"]],
                               window_start=e["window_start"], window_end=e["window_end"],
                               release_seconds=max(e["window_end"],
                                   e["capture_clock_seconds"]-e["elapsed_ms"]/1000)))
        pixels, timestamps = [], []
        for _, when, source, bgr in causal_frames(video):
            ok, jpg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                raise ValueError("JPEG encoding failed")
            pixels.append(decode_jpeg_frames([jpg.tobytes()], True, max_width=360)[0])
            timestamps.append(dict(sample=when, source=source))
        item = dict(id=name, video=str(video), sha256=info["video_sha256"],
                    trace=str(trace), trace_sha256=digest(trace), windows=events,
                    timestamps=timestamps, scores_sha256=digest(probe / "SCORES.json"))
        manifest.append(item)
        write(args.output / "MANIFEST.json", dict(
            scope="Archived window times copied onto MP4 time zero; no exact live-clock or JPEG equivalence claim",
            checkpoint_sha256=checkpoint_hash, audio_used_for_prediction=False,
            score_clock_sensitivity_seconds=[-0.5, 0.0, 0.5], clips=manifest))
        out = args.output / name
        out.mkdir()
        records = []
        for index, event in enumerate(events):
            begin, end = round(event["window_start"]*25), round(event["window_end"]*25)
            if not 0 <= begin < end <= len(pixels):
                raise ValueError("Window outside saved video")
            tick = time.perf_counter()
            frames = pixels[begin:end]
            check_live_images(frames, 25)
            prepared = engine._preprocessor.prepare_frames(frames, source_fps=25, input_kind="raw_face")
            preprocess_ms = (time.perf_counter()-tick)*1000
            tensor_hash = hashlib.sha256(prepared.tensor.numpy().tobytes()).hexdigest()
            tensor_file = out / f"{index:03}.pt"
            torch.save(dict(tensor=prepared.tensor, diagnostics=prepared.diagnostics), tensor_file)
            tick = time.perf_counter()
            result = engine._decode_native(prepared, realtime=True)
            torch.cuda.synchronize()
            elapsed_ms = (time.perf_counter()-tick)*1000
            r = dict(index=index, event=event, tensor_sha256=tensor_hash,
                     tensor_file_sha256=digest(tensor_file), tensor_file=str(tensor_file.resolve()),
                     transcript=result.transcript, words=result.diagnostics.get("words", []),
                     alternatives=result.alternatives, runtime=dict(preprocess_ms=preprocess_ms,
                         decode_ms=elapsed_ms), diagnostics=result.diagnostics)
            records.append(r)
            with (out / "WINDOWS.jsonl").open("a", encoding="utf8") as stream:
                stream.write(json.dumps(r, ensure_ascii=False)+"\n")
            print(f"{name} window {index+1}/{len(events)} {event['type']}: {result.transcript}", flush=True)
        decoded.append((name, probe, records))
        del pixels
    # Read textual references only once all predictions have been persisted.
    results = []
    for name, probe, records in decoded:
        reference_file = args.scenes / ("REFERENCE_CONFIRMED.json" if name == "scene01"
                                       else f"{name.upper()}_REFERENCE_CONFIRMED.json")
        ref = json.loads(reference_file.read_text(encoding="utf8"))
        refs = ref.get("sentences", [])
        if name != "scene03" and not refs:
            raise ValueError("Missing confirmed sentences")
        data = json.loads((probe / "SCORES.json").read_text(encoding="utf8"))
        scores = next(m["events"] for m in data["models"] if m["model"] == "CNN2Plus1D_Light")
        info = json.loads((probe / "INPUT.json").read_text(encoding="utf8"))
        if data["input_sha256"] != digest(probe / "INPUT.json") or data["video_sha256"] != info["video_sha256"]:
            raise ValueError("Classifier source/hash mismatch")
        for e in scores:
            e["crop_ms"] = info["frames"][e["index"]]["crop_ms"]
        result = evaluate(records, name, scores, refs)
        result.update(reference_sha256=digest(reference_file),
                      recognition_windows=len(records),
                      unavailable_word_alignment_windows=sum(not r["words"] for r in records),
                      decode_median_ms=statistics.median(r["runtime"]["decode_ms"] for r in records))
        results.append(result)
    write(args.output / "RESULTS.json", dict(
        scope="Controlled MP4 replay at archived window numbers; paired same tensors/hypotheses. Not the original phone session.",
        production_changed=False, checkpoint_sha256=checkpoint_hash,
        normalization="NFC lowercase whitespace units, punctuation removed; CER excludes spaces",
        limits=["Clock offsets are sensitivity checks, not measured alignment bounds",
                "Classifier runtime is cached isolated execution; no end-to-end latency claim",
                "Strict confirmation may reject short utterances; not validated for release",
                "MP4 decoder/re-encoding differs from native camera JPEG payloads"], clips=results))
    print("Complete:", args.output / "RESULTS.json", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("scenes", "probes", "checkpoint", "output"):
        parser.add_argument("--"+flag, type=Path, required=True)
    main(parser.parse_args())
