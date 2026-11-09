"""Optional per-turn visual confirmation; short/unknown inputs preserve VSR.

Runs on one owning executor thread. A positive pair is retained for that turn.
No audio, transcript or reference list is accepted by this service.
"""

from collections import OrderedDict
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import time

import numpy as np


WEIGHTS_SHA256 = "b32f26769b92dd1043bce2f7836787dbdb8489b92727f741b36fec1fe4187bb3"


def face_crop(rgb, detector):
    import cv2

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


@dataclass
class ConfirmationState:
    confirmed: bool = False
    saw_positive: bool = False
    scores: dict = field(default_factory=dict)


def decide(events, duration, *, minimum_seconds=2.0, already_confirmed=False):
    """Only sufficient, uniformly negative evidence can suppress a decode.

    The 2s default is the existing live partial-decode minimum, not a fitted speech
    duration. Invalid/ambiguous evidence and isolated positive scores remain unknown.
    """
    if already_confirmed:
        return "confirmed"
    if duration < minimum_seconds - 1e-6:
        return "short_unknown"
    previous = None
    for e in events:
        positive = e.get("score") is not None and e["quality"] == "visible" and e["score"] >= 0.5
        if positive and previous is not None and 0 < e["time"] - previous <= 0.121:
            return "confirmed"
        previous = e["time"] if positive else None
    valid = [e for e in events if e.get("score") is not None and e["quality"] == "visible"]
    if len(valid) >= 2 and len(valid) == len(events) and all(e["score"] < 0.5 for e in valid):
        return "negative"
    return "unknown"


class SpeechConfirmation:
    def __init__(self, weights, minimum_seconds=2.0):
        self.weights = Path(weights)
        self.minimum_seconds = minimum_seconds
        self.model = self.detector = None
        self.failure = None
        self.crops = OrderedDict()
        self.turns = OrderedDict()

    def load(self):
        try:
            if hashlib.sha256(self.weights.read_bytes()).hexdigest() != WEIGHTS_SHA256:
                raise ValueError("Visual confirmation weights do not match the validated export")
            import mediapipe as mp
            from .vvad_model import CnnSpeechModel

            self.model = CnnSpeechModel.from_npz(self.weights)
            self.detector = mp.solutions.face_detection.FaceDetection(
                model_selection=0, min_detection_confidence=0.6
            )
            self.model.score(np.zeros((38, 96, 96, 3), dtype=np.uint8))
        except Exception as exc:
            self.failure = type(exc).__name__ + ": " + str(exc)

    def close(self):
        if self.detector is not None:
            self.detector.close()
            self.detector = None
        self.model = None
        self.crops.clear()
        self.turns.clear()

    def evaluate(self, frames, begin, end, turn_id, turn_start):
        tick = time.perf_counter()
        result = dict(
            enabled=True,
            model="cnn2plus1d_light",
            threshold=0.5,
            scores_are_calibrated_probabilities=False,
            window_start=begin,
            window_end=end,
            state="unknown",
            allow_decode=True,
            classifier_calls=0,
            crop_calls=0,
        )

        def finish(state, **extra):
            return dict(
                result,
                state=state,
                allow_decode=state != "negative",
                **extra,
                elapsed_ms=round((time.perf_counter() - tick) * 1000, 3),
            )

        if self.failure or self.model is None:
            return finish("unavailable", failure=self.failure or "not_loaded")
        if abs((end - begin) * 25 - len(frames)) > 0.001:
            return finish("unavailable", failure="requires_25_hz_window")
        state = self.turns.setdefault(turn_id, ConfirmationState())
        self.turns.move_to_end(turn_id)
        while len(self.turns) > 4:
            self.turns.popitem(last=False)
        if state.confirmed:
            return finish("confirmed", reused_turn_confirmation=True)
        if end - begin < self.minimum_seconds - 1e-6:
            return finish("short_unknown")
        try:
            crop_rows = []
            for frame in frames:
                identity = hashlib.sha256(frame.tobytes()).digest()
                cached = self.crops.get(identity)
                if cached is None:
                    cached = face_crop(frame, self.detector)
                    self.crops[identity] = cached
                    result["crop_calls"] += 1
                self.crops.move_to_end(identity)
                while len(self.crops) > 200:
                    self.crops.popitem(last=False)
                crop_rows.append((identity, *cached))
            events = []
            base = round(begin * 25)
            for index in range(37, len(crop_rows)):
                if (base + index) % 3:
                    continue
                left = index - 37
                start = begin + left / 25
                if start < turn_start - 1e-6:
                    continue
                window = crop_rows[left : index + 1]
                key = (round(start, 6), tuple(r[0] for r in window))
                cached = state.scores.get(key)
                if cached is None:
                    visible = all(r[2] == "visible" for r in window)
                    cached = dict(
                        time=begin + index / 25,
                        window_start=start,
                        quality="visible" if visible else "face_unavailable",
                        score=None,
                    )
                    if visible:
                        cached["score"] = self.model.score(np.stack([r[1] for r in window]))
                        result["classifier_calls"] += 1
                    state.scores[key] = cached
                events.append(cached)
                if (
                    cached["quality"] == "visible"
                    and cached["score"] is not None
                    and cached["score"] >= 0.5
                ):
                    state.saw_positive = True
                if decide(events, end - begin, minimum_seconds=self.minimum_seconds) == "confirmed":
                    state.confirmed = True
                    break
            # A positive earlier in this turn remains ambiguous evidence even if
            # its window has slid out of view. Do not call the whole turn silent.
            decision = decide(events, end - begin, minimum_seconds=self.minimum_seconds)
            if decision == "negative" and state.saw_positive:
                decision = "unknown"
            if len(state.scores) > 256:
                # Keep this memory bounded even for long moving-but-uncertain turns.
                state.scores = dict(list(state.scores.items())[-256:])
            return finish(decision, events=events)
        except Exception as exc:
            # A broken optional detector must never erase a potentially spoken turn.
            self.failure = type(exc).__name__ + ": " + str(exc)
            return finish("unavailable", failure=self.failure)
