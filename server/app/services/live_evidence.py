"""Conservative input rejection and explicit failure accounting for live video.

This is not a speech-activity detector or a calibrated confidence estimator.
It only rejects blank/essentially identical image sequences; moving nonspeech
faces still require a trained visual speech detector and independent validation.
"""

from dataclasses import dataclass, field

from .video_preprocessor import VideoValidationError


def check_live_images(frames, fps):
    import cv2
    import numpy as np

    # Sample the whole window, never discard valid speech because the tail pauses.
    samples = frames[:: max(1, len(frames) // 24)]
    gray = np.stack(
        [cv2.resize(cv2.cvtColor(f, cv2.COLOR_RGB2GRAY), (48, 48)) for f in samples]
    ).astype(np.float32)
    brightness = float(gray.mean())
    contrast = float(gray.std())
    if contrast < 3 and (brightness < 8 or brightness > 247):
        raise VideoValidationError(
            "image_obscured", "Hình quá tối hoặc bị che. Hãy kiểm tra camera và ánh sáng."
        )
    motion = float(np.abs(np.diff(gray, axis=0)).mean()) if len(gray) > 1 else 0.0
    if len(frames) / fps >= 1.2 and motion < 0.02:
        raise VideoValidationError(
            "image_frozen", "Hình đang đứng yên. Chưa có chuyển động để tạo phụ đề mới."
        )
    return {
        "brightness": round(brightness, 2),
        "image_motion": round(motion, 4),
        "is_speech_detector": False,
    }


@dataclass
class LiveEvidence:
    attempted_windows: int = 0
    unavailable_windows: int = 0
    intervals: list = field(default_factory=list)

    def record(self, begin, end, code=None):
        self.attempted_windows += 1
        if code is None:
            return
        self.unavailable_windows += 1
        item = {"start": round(begin, 3), "end": round(end, 3), "code": code}
        if (
            self.intervals
            and self.intervals[-1]["code"] == code
            and begin <= self.intervals[-1]["end"]
        ):
            self.intervals[-1]["end"] = max(self.intervals[-1]["end"], item["end"])
        else:
            self.intervals.append(item)

    def payload(self):
        return {
            "attempted_windows": self.attempted_windows,
            "unavailable_windows": self.unavailable_windows,
            "unavailable_window_rate": self.unavailable_windows / max(1, self.attempted_windows),
            "unavailable_intervals": list(self.intervals),
            "rate_is_accuracy": False,
        }
