"""Cache causal 25 Hz face crops and the current motion gate from a phone MP4.

This offline experiment never loads audio or changes the production server.
Decode timestamps, crop failures and source hashes are retained for audit.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import cv2
import mediapipe as mp
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.services.visual_activity import VisualMotionDetector
from app.services.realtime import decode_jpeg_frames


def causal_frames(video, fps=25):
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"Cannot open {video}")
    previous, previous_time, index = None, -1.0, 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            source_time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if source_time <= previous_time:
                raise ValueError("Video timestamps are not strictly increasing")
            while previous is not None and index / fps < source_time - 1e-7:
                if previous_time > index / fps + 1e-7:
                    raise ValueError("First video timestamp is later than the sample clock")
                yield index, index / fps, previous_time, previous
                index += 1
            previous, previous_time = frame, source_time
        if previous is not None and index / fps <= previous_time + 1e-7:
            yield index, index / fps, previous_time, previous
    finally:
        cap.release()


def face_crop(rgb, detector):
    found = detector.process(rgb).detections
    if not found or len(found) != 1:
        return None, "multiple_faces" if found else "waiting_for_face"
    box = found[0].location_data.relative_bounding_box
    h, w = rgb.shape[:2]
    cx, cy = (box.xmin + box.width / 2) * w, (box.ymin + box.height / 2) * h
    size = max(box.width * w, box.height * h)
    x0, x1 = max(0, round(cx - size / 2)), min(w, round(cx + size / 2))
    y0, y1 = max(0, round(cy - size / 2)), min(h, round(cy + size / 2))
    if x1 <= x0 or y1 <= y0:
        return None, "invalid_crop"
    return cv2.resize(rgb[y0:y1, x0:x1], (96, 96)), "visible"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--camera-transport",
        action="store_true",
        help="JPEG quality 80 then the live activity decoder's 360px resize",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    crops, rows = [], []
    motion = VisualMotionDetector()
    try:
        with mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.6
        ) as detector:
            for i, sample_time, source_time, bgr in causal_frames(args.video):
                tick = time.perf_counter()
                if args.camera_transport:
                    ok, jpeg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if not ok:
                        raise ValueError("JPEG encode failed")
                    rgb = decode_jpeg_frames([jpeg.tobytes()], True, max_width=360)[0]
                else:
                    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                crop, quality = face_crop(rgb, detector)
                crop_ms = (time.perf_counter() - tick) * 1000
                row = dict(
                    index=i,
                    time=sample_time,
                    source_time=source_time,
                    crop_quality=quality,
                    crop_ms=crop_ms,
                )
                crops.append(crop if crop is not None else np.zeros((96, 96, 3), np.uint8))
                if i % 3 == 0:
                    tick = time.perf_counter()
                    observation = motion.analyze(rgb)
                    row["motion"] = dict(
                        score=observation.score,
                        quality=observation.quality,
                        processing_ms=(time.perf_counter() - tick) * 1000,
                    )
                rows.append(row)
    finally:
        motion.close()
    if len(rows) < 38:
        raise ValueError("Fewer than 38 decoded samples")
    np.save(args.output / "face_rgb.npy", np.stack(crops))
    result = dict(
        video=str(args.video.resolve()),
        video_sha256=hashlib.sha256(args.video.read_bytes()).hexdigest(),
        sample_fps=25,
        motion_stride_frames=3,
        frame_count=len(rows),
        duration_seconds=rows[-1]["time"] + 0.04,
        crop="MediaPipe single face square box clipped to frame, RGB 96x96",
        input_pipeline=(
            "JPEG 80 then production decode_jpeg_frames max_width=360"
            if args.camera_transport
            else "original decoded resolution"
        ),
        transport_limit="MP4 re-encoding approximates camera JPEG; not the original wire payload",
        timestamp_rule="latest decoded source frame at or before each sample; no future frame",
        audio_used=False,
        production_changed=False,
        frames=rows,
    )
    (args.output / "INPUT.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps({k: v for k, v in result.items() if k != "frames"}), flush=True)


if __name__ == "__main__":
    main()
