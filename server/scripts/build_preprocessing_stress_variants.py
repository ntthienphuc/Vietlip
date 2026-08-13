from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def _writer(path: Path, fps: float, size: tuple[int, int]):
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        size,
    )
    if not writer.isOpened():
        raise RuntimeError(f"Không tạo được video: {path}")
    return writer


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tạo các biến thể hình học/ánh sáng để stress-test crop mặt.",
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    capture = cv2.VideoCapture(str(args.source))
    if not capture.isOpened():
        raise RuntimeError(f"Không mở được video: {args.source}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError("Metadata video không hợp lệ.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    writers = {
        "rotated_90": _writer(
            args.output_dir / "stress_rotated_90.mp4",
            fps,
            (height, width),
        ),
        "low_light": _writer(
            args.output_dir / "stress_low_light.mp4",
            fps,
            (width, height),
        ),
        "close_crop": _writer(
            args.output_dir / "stress_close_crop.mp4",
            fps,
            (width, height),
        ),
        "small_face": _writer(
            args.output_dir / "stress_small_face.mp4",
            fps,
            (width, height),
        ),
    }
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            writers["rotated_90"].write(
                cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            )
            writers["low_light"].write(
                cv2.convertScaleAbs(frame, alpha=0.42, beta=0)
            )

            crop_width = int(width * 0.72)
            crop_height = int(height * 0.72)
            x0 = (width - crop_width) // 2
            y0 = (height - crop_height) // 2
            close_crop = frame[
                y0 : y0 + crop_height,
                x0 : x0 + crop_width,
            ]
            writers["close_crop"].write(
                cv2.resize(
                    close_crop,
                    (width, height),
                    interpolation=cv2.INTER_LINEAR,
                )
            )

            scaled = cv2.resize(
                frame,
                (int(width * 0.55), int(height * 0.55)),
                interpolation=cv2.INTER_AREA,
            )
            canvas = np.zeros_like(frame)
            sy, sx = scaled.shape[:2]
            offset_x = (width - sx) // 2
            offset_y = (height - sy) // 2
            canvas[
                offset_y : offset_y + sy,
                offset_x : offset_x + sx,
            ] = scaled
            writers["small_face"].write(canvas)
    finally:
        capture.release()
        for writer in writers.values():
            writer.release()

    for output in sorted(args.output_dir.glob("*.mp4")):
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
