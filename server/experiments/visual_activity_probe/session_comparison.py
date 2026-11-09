"""Compare confirmation on a recorded phone session's frozen window schedule.

The MP4 clock is a new replay clock. Original camera JPEGs and recording/capture
clock alignment were not saved. Thus replay WER is separate from original live
WER. References are read after predictions; no audio enters either visual path.
"""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time

import cv2
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
    trace = [json.loads(line) for line in args.trace.read_text(encoding="utf8").splitlines()]
    starts = {e["turn_id"]: e["speech_start"] for e in trace if "speech_start" in e}
    events = [e for e in trace if e["type"] in ("partial", "segment_final")]
    if not events or not any(e["type"] == "session_final" for e in trace):
        raise ValueError("Expected a completed phone session with recognition windows")
    provenance = dict(
        scope=__doc__,
        video_sha256=digest(args.video),
        trace_sha256=digest(args.trace),
        checkpoint_sha256=digest(args.checkpoint),
        weights_sha256=digest(args.weights),
        source_hashes={
            name: digest(Path(__file__).resolve().parents[2] / name)
            for name in (
                "app/services/speech_confirmation.py",
                "app/services/vvad_model.py",
                "app/services/auto_stream.py",
            )
        },
    )
    write(args.output / "INPUT.json", provenance)
    pixels = []
    timestamps = []
    for _, when, source, frame in causal_frames(args.video):
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            raise ValueError("JPEG encoding failed")
        pixels.append(decode_jpeg_frames([jpeg.tobytes()], True, max_width=360)[0])
        timestamps.append(dict(sample=when, source=source))
    write(args.output / "TIMESTAMPS.json", timestamps)
    engine = NativeAvsrEngine(
        replace(
            settings(args.checkpoint, device="cuda", beam=3),
            precision="float32",
            nbest=3,
            ctc_weight=0.1,
        )
    )
    engine.load()
    checker = SpeechConfirmation(args.weights)
    checker.load()
    if checker.failure:
        raise RuntimeError(checker.failure)
    timelines = {name: AgreementTimeline() for name in ("baseline", "confirmation")}
    rows = []
    previous = {name: "" for name in timelines}
    revisions = {name: [] for name in timelines}
    try:
        for index, event in enumerate(events):
            begin, end = event["window_start"], event["window_end"]
            first, stop = round(begin * 25), round(end * 25)
            if not 0 <= first < stop <= len(pixels):
                raise ValueError("Window outside saved video")
            frames = pixels[first:stop]
            prepared = engine._preprocessor.prepare_frames(
                frames, source_fps=25, input_kind="raw_face"
            )
            tensor_hash = hashlib.sha256(prepared.tensor.numpy().tobytes()).hexdigest()
            tensor_file = args.output / f"{index:03}.pt"
            torch.save(dict(tensor=prepared.tensor, diagnostics=prepared.diagnostics), tensor_file)
            tick = time.perf_counter()
            decoded = engine._decode_native(prepared, realtime=True)
            torch.cuda.synchronize()
            decode_ms = (time.perf_counter() - tick) * 1000
            decision = checker.evaluate(
                frames, begin, end, event["turn_id"], starts[event["turn_id"]]
            )
            aligned = decoded.diagnostics.get("words", [])
            captions = {}
            for name, timeline in timelines.items():
                accepted = name == "baseline" or decision["allow_decode"]
                if accepted and aligned:
                    caption = timeline.update(
                        aligned,
                        begin,
                        end,
                        final=event["type"] == "segment_final",
                        right_context=1.0,
                    )
                else:
                    timeline.discard_pending()
                    caption = dict(transcript=timeline.text)
                captions[name] = caption
                current = caption["transcript"]
                if (
                    previous[name]
                    and current != previous[name]
                    and not current.startswith(previous[name] + " ")
                ):
                    revisions[name].append(index)
                previous[name] = current
            row = dict(
                index=index,
                event={k: event[k] for k in ("type", "turn_id", "window_start", "window_end")},
                tensor_sha256=tensor_hash,
                tensor_file_sha256=digest(tensor_file),
                words=aligned,
                transcript=decoded.transcript,
                alternatives=decoded.alternatives,
                gate=decision,
                captions=captions,
                decode_ms=decode_ms,
            )
            rows.append(row)
            with (args.output / "WINDOWS.jsonl").open("a", encoding="utf8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(
                json.dumps(
                    dict(index=index, gate=decision["state"], transcript=decoded.transcript),
                    ensure_ascii=False,
                ),
                flush=True,
            )
    finally:
        checker.close()
    # The recognizer and gate have now finished. Only scoring reads references.
    refs = json.loads(args.references.read_text(encoding="utf8"))["sentences"]
    reference = " ".join(refs)
    final = next(e for e in trace if e["type"] == "session_final")
    receipts = [e for e in trace if e["type"] == "caption_render_ack"]
    result = dict(
        **provenance,
        reference_sha256=digest(args.references),
        replay=[
            dict(
                policy=name,
                transcript=timeline.text,
                **score(reference, timeline.text),
                visible_prefix_revisions=revisions[name],
            )
            for name, timeline in timelines.items()
        ],
        suppressed_windows=sum(not r["gate"]["allow_decode"] for r in rows),
        original_phone=dict(
            **score(reference, final["transcript"]),
            transcript=final["transcript"],
            received_frames=final["received_frames"],
            capture_fps=final["capture_fps"],
            capture_gaps=final["capture_gaps"],
            caption_events=len(events),
            render_receipts=len(receipts),
            missing_receipt_ids=sorted(
                {e["caption_event_id"] for e in events} - {e["caption_event_id"] for e in receipts}
            ),
            evidence=final["evidence"],
            visual_window_end_to_final_render_ack_ms=[
                e["window_end_to_render_ack_ms"]
                for e in receipts
                if e["caption_type"] == "segment_final"
            ],
            final_transcripts=[
                e["window_transcript"] for e in events if e["type"] == "segment_final"
            ],
        ),
        limits=[
            "Replay uses same tensors and windows for both gate policies, with reused decoder output",
            "Live and MP4 clock origins are not synchronized; receipt timing is from padded visual window end",
            "No claim of acoustic end-to-display delay or reconstructed native camera JPEGs",
            "One new speaker session, not a population accuracy evaluation",
        ],
    )
    write(args.output / "RESULTS.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("video", "trace", "references", "checkpoint", "weights", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    main(parser.parse_args())
