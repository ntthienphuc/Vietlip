from types import SimpleNamespace

import numpy as np
import pytest

from app.services.video_preprocessor import (
    VideoPreprocessor,
    VideoValidationError,
)


def _landmark():
    return np.asarray(
        [[10, 10], [20, 10], [15, 15], [15, 20]],
        dtype=np.float32,
    )


def test_merge_landmarks_uses_short_range_per_missing_frame():
    primary = [_landmark(), None, _landmark(), None]
    fallback = [None, _landmark(), None, _landmark()]

    merged = VideoPreprocessor._merge_landmarks(primary, fallback)

    assert VideoPreprocessor._count_landmarks(merged) == 4


def test_track_face_retries_phone_rotation_when_upright_is_weak():
    class FakeDetector:
        def __init__(self):
            self.full_range_detector = "full"
            self.short_range_detector = "short"

        def detect(self, frames, detector):
            landscape = frames[0].shape[1] > frames[0].shape[0]
            if landscape and detector == "full":
                return [_landmark() for _ in frames]
            if detector == "full":
                return [_landmark(), None, *([None] * (len(frames) - 2))]
            return [None, _landmark(), *([None] * (len(frames) - 2))]

    preprocessor = VideoPreprocessor(
        auto_avsr_root=SimpleNamespace(),
        target_fps=25,
        min_frames=8,
        max_frames=1125,
    )
    frames = [np.zeros((12, 8, 3), dtype=np.uint8) for _ in range(10)]

    result = preprocessor._track_face(
        frames,
        detector_module=SimpleNamespace(LandmarksDetector=FakeDetector),
    )

    assert result.diagnostics["rotation_degrees"] == 90
    assert result.diagnostics["merged_detection_ratio"] == 1.0
    assert len(result.diagnostics["attempts"]) == 4


def test_track_face_rejects_when_too_few_frames_are_detected():
    class SparseDetector:
        def __init__(self):
            self.full_range_detector = "full"
            self.short_range_detector = "short"

        def detect(self, frames, detector):
            return [_landmark(), None, *([None] * (len(frames) - 2))]

    preprocessor = VideoPreprocessor(
        auto_avsr_root=SimpleNamespace(),
        target_fps=25,
        min_frames=8,
        max_frames=1125,
    )
    frames = [np.zeros((12, 8, 3), dtype=np.uint8) for _ in range(100)]

    with pytest.raises(VideoValidationError) as exc:
        preprocessor._track_face(
            frames,
            detector_module=SimpleNamespace(
                LandmarksDetector=SparseDetector
            ),
        )

    assert exc.value.code == "face_tracking_failed"
    assert "1/100" in str(exc.value)


def test_track_face_uses_facemesh_as_generic_close_face_rescue():
    points = [
        SimpleNamespace(x=0.5, y=0.5)
        for _ in range(468)
    ]
    points[33] = SimpleNamespace(x=0.35, y=0.40)
    points[133] = SimpleNamespace(x=0.42, y=0.40)
    points[362] = SimpleNamespace(x=0.58, y=0.40)
    points[263] = SimpleNamespace(x=0.65, y=0.40)
    points[1] = SimpleNamespace(x=0.50, y=0.52)
    points[13] = SimpleNamespace(x=0.50, y=0.62)
    points[14] = SimpleNamespace(x=0.50, y=0.66)
    points[78] = SimpleNamespace(x=0.43, y=0.64)
    points[308] = SimpleNamespace(x=0.57, y=0.64)

    class FakeFaceMesh:
        def __init__(self, **kwargs):
            pass

        def process(self, frame):
            return SimpleNamespace(
                multi_face_landmarks=[
                    SimpleNamespace(landmark=points),
                ]
            )

        def close(self):
            pass

    class MissingFaceDetector:
        def __init__(self):
            self.full_range_detector = "full"
            self.short_range_detector = "short"

        def detect(self, frames, detector):
            return [None for _ in frames]

    detector_module = SimpleNamespace(
        LandmarksDetector=MissingFaceDetector,
        mp=SimpleNamespace(
            solutions=SimpleNamespace(
                face_mesh=SimpleNamespace(FaceMesh=FakeFaceMesh),
            )
        ),
    )
    preprocessor = VideoPreprocessor(
        auto_avsr_root=SimpleNamespace(),
        target_fps=25,
        min_frames=8,
        max_frames=1125,
    )
    frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(10)]

    result = preprocessor._track_face(
        frames,
        detector_module=detector_module,
    )

    assert result.diagnostics["strategy"].endswith("facemesh_merge")
    assert result.diagnostics["facemesh_detection_ratio"] == 1.0
    assert result.diagnostics["merged_detection_ratio"] == 1.0


def test_track_face_retries_rotation_when_sideways_detector_has_high_coverage():
    sideways = np.asarray(
        [[10, 10], [10, 20], [15, 15], [20, 15]],
        dtype=np.float32,
    )

    class SidewaysDetector:
        def __init__(self):
            self.full_range_detector = "full"
            self.short_range_detector = "short"

        def detect(self, frames, detector):
            landscape = frames[0].shape[1] > frames[0].shape[0]
            landmark = _landmark() if landscape else sideways
            return [landmark.copy() for _ in frames]

    preprocessor = VideoPreprocessor(
        auto_avsr_root=SimpleNamespace(),
        target_fps=25,
        min_frames=8,
        max_frames=1125,
    )
    frames = [np.zeros((12, 8, 3), dtype=np.uint8) for _ in range(10)]

    result = preprocessor._track_face(
        frames,
        detector_module=SimpleNamespace(
            LandmarksDetector=SidewaysDetector,
        ),
    )

    assert result.diagnostics["rotation_degrees"] == 90
    assert result.diagnostics["upright_landmark_ratio"] == 1.0
