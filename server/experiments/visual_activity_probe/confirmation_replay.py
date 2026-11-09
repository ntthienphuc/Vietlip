"""Run the deployable confirmation path on the frozen MP4 window comparison.

Verifies the unchanged recognition tensors; reuses their saved VSR hypotheses.
Also exercises short speech suffixes with the bounded unknown-input fallback.
"""

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.services.caption_stability import AgreementTimeline
from app.services.native_engine import NativeAvsrEngine
from app.services.realtime import decode_jpeg_frames
from app.services.speech_confirmation import SpeechConfirmation
from experiments.visual_activity_probe.frozen_captions import digest, score, write
from experiments.visual_activity_probe.prepare import causal_frames
from scripts.benchmark_models import settings


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    checker = SpeechConfirmation(args.weights)
    checker.load()
    if checker.failure:
        raise RuntimeError(checker.failure)
    # Only its production preprocessor is used, not a second GPU model.
    engine = NativeAvsrEngine(settings(args.checkpoint, device="cuda", beam=3))
    manifest = json.loads((args.frozen / "MANIFEST.json").read_text(encoding="utf8"))
    result = dict(
        scope=__doc__,
        model_weights_sha256=digest(args.weights),
        source_manifest_sha256=digest(args.frozen / "MANIFEST.json"),
        production_enabled=False,
        clips=[],
        short_fragments=[],
    )
    try:
        for clip in manifest["clips"]:
            video = Path(clip["video"])
            if digest(video) != clip["sha256"]:
                raise ValueError("Changed source video")
            rgb = []
            for _, _, _, frame in causal_frames(video):
                ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if not ok:
                    raise ValueError("JPEG encode failure")
                rgb.append(decode_jpeg_frames([jpg.tobytes()], True, max_width=360)[0])
            rows = [
                json.loads(line)
                for line in (args.frozen / clip["id"] / "WINDOWS.jsonl")
                .read_text(encoding="utf8")
                .splitlines()
            ]
            timeline = AgreementTimeline()
            events = []
            for r in rows:
                e = r["event"]
                begin, end = round(e["window_start"] * 25), round(e["window_end"] * 25)
                frames = rgb[begin:end]
                prepared = engine._preprocessor.prepare_frames(
                    frames, source_fps=25, input_kind="raw_face"
                )
                if (
                    hashlib.sha256(prepared.tensor.numpy().tobytes()).hexdigest()
                    != r["tensor_sha256"]
                ):
                    raise ValueError("Recognition pixel tensor differs from frozen baseline")
                decision = checker.evaluate(
                    frames,
                    e["window_start"],
                    e["window_end"],
                    (clip["id"], e["turn_id"]),
                    e["turn_start"],
                )
                if decision["allow_decode"] and r["words"]:
                    update = timeline.update(
                        r["words"],
                        e["window_start"],
                        e["window_end"],
                        final=e["type"] == "segment_final",
                        right_context=1.0,
                    )
                else:
                    timeline.discard_pending()
                    update = dict(transcript=timeline.text)
                events.append(
                    dict(event=e, gate=decision, caption=update, tensor_sha256=r["tensor_sha256"])
                )
            ref_path = args.scenes / (
                "REFERENCE_CONFIRMED.json"
                if clip["id"] == "scene01"
                else clip["id"].upper() + "_REFERENCE_CONFIRMED.json"
            )
            refs = json.loads(ref_path.read_text(encoding="utf8"))["sentences"]
            summary = dict(
                clip=clip["id"],
                transcript=timeline.text,
                **score(" ".join(refs), timeline.text),
                windows=len(events),
                suppressed=sum(not e["gate"]["allow_decode"] for e in events),
                new_classifier_calls=sum(e["gate"]["classifier_calls"] for e in events),
                elapsed_median_ms=statistics.median(e["gate"]["elapsed_ms"] for e in events),
                elapsed_max_ms=max(e["gate"]["elapsed_ms"] for e in events),
                events=events,
            )
            result["clips"].append(summary)
            print(
                json.dumps({k: v for k, v in summary.items() if k not in ("events", "transcript")}),
                flush=True,
            )
            if clip["id"] != "scene03":
                boundaries = json.loads(
                    (args.probes / (clip["id"].upper() + "_AUDIO_ENDPOINTS.json")).read_text()
                )
                if boundaries["video_sha256"] != clip["sha256"]:
                    raise ValueError("Speech boundary identity mismatch")
                for i, ref in enumerate(boundaries["thresholds"]["0.5"]):
                    for duration in (0.4, 0.6, 0.8, 1.0, 1.4, 1.8, 2.4):
                        first = int(np.ceil((ref["end"] - duration) * 25))
                        stop = int(np.floor((ref["end"] + 0.24) * 25))
                        decision = checker.evaluate(
                            rgb[first:stop],
                            first / 25,
                            stop / 25,
                            (clip["id"], "suffix", i, duration),
                            first / 25,
                        )
                        result["short_fragments"].append(
                            dict(
                                clip=clip["id"],
                                reference_index=i,
                                speech_suffix_seconds=duration,
                                video_start=first / 25,
                                video_end=stop / 25,
                                gate=decision,
                            )
                        )
            write(args.output / "RESULTS.json", result)
    finally:
        checker.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ("weights", "frozen", "scenes", "probes", "checkpoint", "output"):
        p.add_argument("--" + flag, type=Path, required=True)
    main(p.parse_args())
