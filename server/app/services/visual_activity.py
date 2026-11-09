"""Visual activity estimate and causal endpoint policy (no audio or text input).

This is a motion gate, not a trained speech/non-speech classifier. Chewing,
smiling, and silent articulation can still activate it. Scores are motion ratios,
never confidence probabilities. Capture timestamps drive every duration.
"""

from collections import deque
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class Observation:
    score: float = 0.0
    quality: str = "visible"


@dataclass(frozen=True)
class ActivityUpdate:
    state: str
    start: float | None = None
    end: float | None = None
    reason: str | None = None


class EndpointPolicy:
    def __init__(self, silence_seconds=1.0, pre_roll=0.45, tail=0.24):
        self.silence_seconds, self.pre_roll, self.tail = silence_seconds, pre_roll, tail
        self.history = deque()
        self.active = False
        self.last_active = self.last_valid = self.last_time = None
        self.state = "waiting_for_face"

    def observe(self, when, observation):
        start = end = reason = None
        gap = self.last_time is not None and when - self.last_time > 0.55
        self.last_time = when
        valid = observation.quality == "visible" and not gap
        if valid:
            self.last_valid = when
        while self.history and self.history[0][0] < when - 0.45:
            self.history.popleft()
        moving = valid and observation.score >= (0.65 if self.active else 1.0)
        self.history.append((when, moving))
        positives = [t for t, yes in self.history if yes]
        if not self.active and len(positives) >= 3 and positives[-1] - positives[0] >= 0.18:
            self.active = True
            start = max(0.0, positives[0] - self.pre_roll)
        if self.active and moving:
            self.last_active = when
        if self.active:
            missing = not valid and (self.last_valid is None or when - self.last_valid >= 0.7)
            quiet = self.last_active is not None and when - self.last_active >= self.silence_seconds
            if gap or missing or quiet:
                end = min(when, (self.last_active or when) + self.tail)
                reason = (
                    "capture_gap" if gap else observation.quality if missing else "visual_pause"
                )
                self.active = False
                self.history.clear()
            else:
                self.state = "speaking" if when - self.last_active < 0.35 else "pausing"
                return ActivityUpdate(self.state, start=start)
        self.state = (
            ("camera_stalled" if gap else observation.quality)
            if not valid
            else "waiting_for_speech"
        )
        return ActivityUpdate(self.state, start=start, end=end, reason=reason)


class VisualMotionDetector:
    """Normalize face translation/roll/scale, then measure lip deformation.

    A dedicated instance runs on one executor thread for each live session.
    Mouth ROI mode is for aligned dataset replays, not camera face detection.
    """

    LIPS = [61, 40, 37, 0, 267, 270, 291, 321, 314, 17, 84, 91, 78, 81, 13, 311, 308, 402, 14, 178]

    def __init__(self, input_kind="raw_face"):
        self.kind = input_kind
        self.mesh = None
        self.previous = None
        self.previous_pose = None

    def load(self):
        if self.kind == "raw_face" and self.mesh is None:
            import mediapipe as mp

            self.mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=2,
                refine_landmarks=False,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.6,
            )

    def close(self):
        if self.mesh is not None:
            self.mesh.close()
            self.mesh = None

    def analyze(self, rgb):

        if float(rgb.std()) < 5 or float(np.percentile(rgb, 90)) < 18:
            self.previous = self.previous_pose = None
            return Observation(quality="poor_light")
        if self.kind == "mouth_roi":
            return self._roi(rgb)
        self.load()
        faces = self.mesh.process(rgb).multi_face_landmarks
        if not faces or len(faces) != 1:
            self.previous = self.previous_pose = None
            return Observation(quality="multiple_faces" if faces else "waiting_for_face")
        h, w = rgb.shape[:2]
        points = np.array([(p.x * w, p.y * h) for p in faces[0].landmark])
        return self.landmarks(points)

    def landmarks(self, points):
        left, right = points[[33, 133]].mean(0), points[[362, 263]].mean(0)
        axis = right - left
        scale = float(np.linalg.norm(axis))
        if scale < 32:
            self.previous = self.previous_pose = None
            return Observation(quality="face_too_small")
        axis /= scale
        vertical = np.array([-axis[1], axis[0]])
        center = (left + right) / 2
        yaw = float(np.dot(points[1] - center, axis) / scale)
        if abs(yaw) > 0.42:
            self.previous = self.previous_pose = None
            return Observation(quality="look_straight")
        mouth = points[self.LIPS]
        shape = (mouth - mouth.mean(0)) @ np.stack([axis, vertical], axis=1) / scale
        aperture = float(
            np.linalg.norm(points[13] - points[14])
            / max(1, np.linalg.norm(points[61] - points[291]))
        )
        pose = (center, scale, math.atan2(axis[1], axis[0]), yaw)
        old, old_pose = self.previous, self.previous_pose
        self.previous, self.previous_pose = (shape, aperture), pose
        if old is None:
            return Observation()
        if (
            np.linalg.norm(center - old_pose[0]) / scale > 0.18
            or abs(math.log(scale / old_pose[1])) > 0.12
            or abs(pose[2] - old_pose[2]) > 0.14
            or abs(yaw - old_pose[3]) > 0.10
        ):
            return Observation(quality="head_motion")
        delta = float(np.sqrt(np.mean((shape - old[0]) ** 2)))
        return Observation(score=max(delta / 0.009, abs(aperture - old[1]) / 0.035))

    def _roi(self, rgb):
        import cv2

        gray = cv2.resize(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), (96, 96))
        old, self.previous = self.previous, gray
        if old is None:
            return Observation()
        flow = cv2.calcOpticalFlowFarneback(old, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        border = np.concatenate(
            [
                flow[:16].reshape(-1, 2),
                flow[-16:].reshape(-1, 2),
                flow[16:-16, :12].reshape(-1, 2),
                flow[16:-16, -12:].reshape(-1, 2),
            ]
        )
        translation = np.median(border, axis=0)
        residual = np.linalg.norm(flow[24:76, 16:80] - translation, axis=2)
        return Observation(score=float(np.percentile(residual, 75) / 0.7))
