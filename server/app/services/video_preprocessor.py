from __future__ import annotations

import importlib.util
import math
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


class VideoValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class PreparedVideo:
    tensor: Any
    num_frames: int
    diagnostics: dict[str, Any]


@dataclass
class FaceTrackingResult:
    frames: list[Any]
    landmarks: list[Any]
    diagnostics: dict[str, Any]


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import preprocessing module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VideoPreprocessor:
    """Reuses the frozen Auto-AVSR alignment/cropping implementation."""

    def __init__(
        self,
        *,
        auto_avsr_root: Path,
        target_fps: float,
        min_frames: int,
        max_frames: int,
    ):
        self.auto_avsr_root = auto_avsr_root
        self.mean_face_path = (
            Path(__file__).resolve().parents[2]
            / "assets"
            / "20words_mean_face.npy"
        )
        self.target_fps = target_fps
        self.min_frames = min_frames
        self.max_frames = max_frames

    def prepare(self, video_path: Path, input_kind: str) -> PreparedVideo:
        frames_rgb, source_fps = self._read_at_target_fps(video_path)
        return self._prepare_frames(
            frames_rgb,
            source_fps=source_fps,
            input_kind=input_kind,
        )

    def prepare_frames(
        self,
        frames_rgb: list[Any],
        *,
        source_fps: float,
        input_kind: str,
    ) -> PreparedVideo:
        """Prepare in-memory RGB frames received by the live-preview API."""
        if not math.isfinite(source_fps) or source_fps <= 0:
            raise VideoValidationError(
                "invalid_realtime_fps",
                "Tốc độ khung hình trực tiếp không hợp lệ.",
            )
        frames_at_target = self._resample_frames(
            frames_rgb,
            source_fps=source_fps,
            target_fps=self.target_fps,
        )
        return self._prepare_frames(
            frames_at_target,
            source_fps=source_fps,
            input_kind=input_kind,
        )

    def _prepare_frames(
        self,
        frames_rgb: list[Any],
        *,
        source_fps: float,
        input_kind: str,
    ) -> PreparedVideo:
        try:
            import cv2
            import numpy as np
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "Video runtime is missing. Install requirements-cpu.txt "
                "or requirements-gpu.txt."
            ) from exc

        if len(frames_rgb) < self.min_frames:
            raise VideoValidationError(
                "video_too_short",
                f"Video cần ít nhất {self.min_frames} khung hình hợp lệ.",
            )
        if len(frames_rgb) > self.max_frames:
            max_seconds = self.max_frames / self.target_fps
            raise VideoValidationError(
                "video_too_long",
                f"Video vượt giới hạn {max_seconds:.1f} giây.",
            )

        resolved_kind = input_kind
        if resolved_kind == "auto":
            height, width = frames_rgb[0].shape[:2]
            resolved_kind = (
                "mouth_roi"
                if max(height, width) <= 160 and abs(height - width) <= 16
                else "raw_face"
            )

        face_detection_ratio: float | None = None
        face_tracking: dict[str, Any] | None = None
        if resolved_kind == "raw_face":
            if not self.mean_face_path.is_file():
                raise RuntimeError(
                    "Missing lip-alignment asset: 20words_mean_face.npy. "
                    "Run setup_server.ps1 again."
                )
            detector_path = (
                self.auto_avsr_root
                / "preparation"
                / "detectors"
                / "mediapipe"
                / "detector.py"
            )
            process_path = detector_path.with_name("video_process.py")
            detector_module = _load_module("_lip_mp_detector", detector_path)
            process_module = _load_module("_lip_mp_process", process_path)
            tracking = self._track_face(
                frames_rgb,
                detector_module=detector_module,
            )
            frames_rgb = tracking.frames
            landmarks = tracking.landmarks
            face_tracking = tracking.diagnostics
            face_detection_ratio = float(
                face_tracking["merged_detection_ratio"]
            )
            try:
                mouth_frames = process_module.VideoProcess(
                    mean_face_path=str(self.mean_face_path),
                    convert_gray=True,
                )(
                    frames_rgb,
                    landmarks,
                )
            except (
                AssertionError,
                IndexError,
                OverflowError,
                TypeError,
                ValueError,
                cv2.error,
            ) as exc:
                raise VideoValidationError(
                    "mouth_crop_failed",
                    (
                        "Đã tìm thấy mặt nhưng không căn chỉnh ổn định được "
                        "vùng môi. Hãy giữ trọn khuôn mặt, nhìn gần chính diện "
                        "và tránh rung máy."
                    ),
                ) from exc
            if mouth_frames is None or len(mouth_frames) == 0:
                raise VideoValidationError(
                    "mouth_crop_failed",
                    "Không tạo được vùng miệng từ video.",
                )
        elif resolved_kind == "mouth_roi":
            mouth_frames = np.stack(
                [
                    cv2.resize(
                        cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                        if frame.ndim == 3
                        else frame,
                        (96, 96),
                        interpolation=cv2.INTER_AREA,
                    )
                    for frame in frames_rgb
                ]
            )
        else:
            raise VideoValidationError(
                "invalid_input_kind",
                "input_kind phải là auto, raw_face hoặc mouth_roi.",
            )

        mouth_frames = np.asarray(mouth_frames, dtype=np.uint8)
        quality = self._quality(mouth_frames, face_detection_ratio)
        warnings = self._quality_warnings(quality)

        # Exact benchmark test transform: uint8 96x96 -> [0,1] -> center
        # crop 88x88 -> grayscale -> Normalize(mean=.421, std=.165).
        tensor = torch.from_numpy(mouth_frames).unsqueeze(1).float() / 255.0
        tensor = tensor[:, :, 4:92, 4:92]
        tensor = (tensor - 0.421) / 0.165

        return PreparedVideo(
            tensor=tensor,
            num_frames=int(tensor.shape[0]),
            diagnostics={
                "input_kind": resolved_kind,
                "source_fps": round(source_fps, 3),
                "target_fps": self.target_fps,
                "preprocessing": {
                    "pipeline": (
                        "auto_avsr_mediapipe_face_alignment_then_mouth_roi"
                    ),
                    "face_tracking": face_tracking,
                    "mouth_roi": "96x96_gray_center_crop_88x88",
                },
                "quality": quality,
                "warnings": warnings,
            },
        )

    @staticmethod
    def _resample_frames(
        frames_rgb: list[Any],
        *,
        source_fps: float,
        target_fps: float,
    ) -> list[Any]:
        if not frames_rgb:
            raise VideoValidationError(
                "no_frames",
                "Luồng trực tiếp chưa có khung hình hợp lệ.",
            )
        if len(frames_rgb) == 1:
            return list(frames_rgb)
        duration = (len(frames_rgb) - 1) / source_fps
        target_count = max(1, int(math.floor(duration * target_fps)) + 1)
        return [
            frames_rgb[
                min(
                    len(frames_rgb) - 1,
                    round((index / target_fps) * source_fps),
                )
            ]
            for index in range(target_count)
        ]

    def _track_face(
        self,
        frames_rgb: list[Any],
        *,
        detector_module: ModuleType,
    ) -> FaceTrackingResult:
        import cv2

        detector = detector_module.LandmarksDetector()

        def detect(
            candidate_frames: list[Any],
            rotation_degrees: int,
        ) -> FaceTrackingResult:
            full = detector.detect(
                candidate_frames,
                detector.full_range_detector,
            )
            full_detected = self._count_landmarks(full)
            full_ratio = full_detected / len(candidate_frames)

            short: list[Any] | None = None
            if full_ratio < 0.98:
                short = detector.detect(
                    candidate_frames,
                    detector.short_range_detector,
                )
            merged = (
                self._merge_landmarks(full, short)
                if short is not None
                else list(full)
            )
            short_detected = (
                self._count_landmarks(short) if short is not None else 0
            )
            face_mesh: list[Any] | None = None
            if self._count_landmarks(merged) / len(candidate_frames) < 0.98:
                face_mesh = self._detect_face_mesh(
                    candidate_frames,
                    detector_module=detector_module,
                )
                merged = self._merge_landmarks(merged, face_mesh)
            face_mesh_detected = self._count_landmarks(face_mesh)
            merged_detected = self._count_landmarks(merged)
            upright_landmarks = self._count_upright_landmarks(merged)
            return FaceTrackingResult(
                frames=candidate_frames,
                landmarks=merged,
                diagnostics={
                    "detector": "Auto-AVSR MediaPipe FaceDetection",
                    "strategy": (
                        "full_range"
                        if short is None and face_mesh is None
                        else (
                            "full_range_plus_short_range_plus_facemesh_merge"
                            if face_mesh is not None
                            else "full_range_plus_short_range_frame_merge"
                        )
                    ),
                    "rotation_degrees": rotation_degrees,
                    "total_frames": len(candidate_frames),
                    "full_range_detected_frames": full_detected,
                    "full_range_detection_ratio": round(full_ratio, 4),
                    "short_range_detected_frames": short_detected,
                    "short_range_detection_ratio": round(
                        short_detected / len(candidate_frames),
                        4,
                    ),
                    "facemesh_detected_frames": face_mesh_detected,
                    "facemesh_detection_ratio": round(
                        face_mesh_detected / len(candidate_frames),
                        4,
                    ),
                    "merged_detected_frames": merged_detected,
                    "merged_detection_ratio": round(
                        merged_detected / len(candidate_frames),
                        4,
                    ),
                    "upright_landmark_frames": upright_landmarks,
                    "upright_landmark_ratio": round(
                        upright_landmarks / max(merged_detected, 1),
                        4,
                    ),
                },
            )

        best = detect(frames_rgb, 0)
        attempts = [dict(best.diagnostics)]

        # OpenCV normally applies phone rotation metadata. Some MP4 encoders do
        # not expose it consistently, so only try rotated copies when the
        # upright dual-range pass is still weak.
        if (
            best.diagnostics["merged_detection_ratio"] < 0.5
            or best.diagnostics["upright_landmark_ratio"] < 0.8
        ):
            rotations = (
                (90, cv2.ROTATE_90_CLOCKWISE),
                (270, cv2.ROTATE_90_COUNTERCLOCKWISE),
                (180, cv2.ROTATE_180),
            )
            for degrees, rotate_code in rotations:
                rotated = [
                    cv2.rotate(frame, rotate_code) for frame in frames_rgb
                ]
                candidate = detect(rotated, degrees)
                attempts.append(dict(candidate.diagnostics))
                candidate_rank = (
                    candidate.diagnostics["upright_landmark_frames"],
                    candidate.diagnostics["full_range_detected_frames"],
                    candidate.diagnostics["merged_detected_frames"],
                )
                best_rank = (
                    best.diagnostics["upright_landmark_frames"],
                    best.diagnostics["full_range_detected_frames"],
                    best.diagnostics["merged_detected_frames"],
                )
                if candidate_rank > best_rank:
                    best = candidate

        best.diagnostics["attempts"] = attempts
        minimum_detected = max(3, math.ceil(len(frames_rgb) * 0.05))
        best.diagnostics["minimum_detected_frames"] = minimum_detected
        if best.diagnostics["merged_detected_frames"] < minimum_detected:
            raise VideoValidationError(
                "face_tracking_failed",
                (
                    "Chưa theo dõi đủ khuôn mặt để tạo vùng môi: "
                    f"{best.diagnostics['merged_detected_frames']}/"
                    f"{len(frames_rgb)} khung hình đạt yêu cầu. Hãy giữ trọn khuôn mặt "
                    "trong khung, nhìn gần chính diện và tăng ánh sáng phía trước."
                ),
            )
        if best.diagnostics["upright_landmark_frames"] < minimum_detected:
            raise VideoValidationError(
                "face_orientation_failed",
                (
                    "Đã tìm thấy mặt nhưng không xác định được hướng mặt thẳng "
                    "để căn chỉnh môi. Hãy quay dọc/đứng đúng chiều và nhìn gần "
                    "chính diện."
                ),
            )
        return best

    @staticmethod
    def _detect_face_mesh(
        frames_rgb: list[Any],
        *,
        detector_module: ModuleType,
    ) -> list[Any] | None:
        """Recover Auto-AVSR's four stable points with MediaPipe FaceMesh.

        FaceDetection remains the primary, benchmark-compatible detector.
        FaceMesh is only a rescue layer for close, clear faces that the two
        FaceDetection models occasionally miss. It returns the same ordered
        points expected by Auto-AVSR's VideoProcess: right eye, left eye,
        nose tip and mouth centre.
        """
        import numpy as np

        mp = getattr(detector_module, "mp", None)
        face_mesh_module = getattr(
            getattr(mp, "solutions", None),
            "face_mesh",
            None,
        )
        if face_mesh_module is None:
            return None

        recovered: list[Any] = []
        mesh = face_mesh_module.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        try:
            for frame in frames_rgb:
                results = mesh.process(frame)
                faces = getattr(results, "multi_face_landmarks", None)
                if not faces:
                    recovered.append(None)
                    continue
                points = faces[0].landmark
                height, width = frame.shape[:2]

                def average(indices: tuple[int, ...]) -> list[float]:
                    return [
                        float(
                            np.mean([points[index].x for index in indices])
                            * width
                        ),
                        float(
                            np.mean([points[index].y for index in indices])
                            * height
                        ),
                    ]

                recovered.append(
                    np.asarray(
                        [
                            average((33, 133)),
                            average((362, 263)),
                            average((1,)),
                            average((13, 14, 78, 308)),
                        ],
                        dtype=np.float32,
                    )
                )
        except (AttributeError, IndexError, RuntimeError, ValueError):
            return None
        finally:
            close = getattr(mesh, "close", None)
            if callable(close):
                close()
        return recovered

    @staticmethod
    def _count_landmarks(landmarks: list[Any] | None) -> int:
        if landmarks is None:
            return 0
        return sum(item is not None for item in landmarks)

    @staticmethod
    def _count_upright_landmarks(landmarks: list[Any] | None) -> int:
        """Count frames whose eye/nose/mouth geometry is plausibly upright."""
        if landmarks is None:
            return 0
        count = 0
        for landmark in landmarks:
            if landmark is None:
                continue
            try:
                right_eye, left_eye, nose, mouth = landmark
                eye_dx = abs(float(left_eye[0]) - float(right_eye[0]))
                eye_dy = abs(float(left_eye[1]) - float(right_eye[1]))
                eye_y = (float(left_eye[1]) + float(right_eye[1])) / 2.0
                nose_y = float(nose[1])
                mouth_y = float(mouth[1])
            except (IndexError, TypeError, ValueError):
                continue
            if (
                eye_dx >= max(eye_dy, 1.0)
                and nose_y > eye_y
                and mouth_y > nose_y
            ):
                count += 1
        return count

    @staticmethod
    def _merge_landmarks(
        primary: list[Any],
        fallback: list[Any] | None,
    ) -> list[Any]:
        if fallback is None:
            return list(primary)
        if len(primary) != len(fallback):
            raise RuntimeError("Face detector passes returned different lengths.")
        return [
            main if main is not None else rescue
            for main, rescue in zip(primary, fallback)
        ]

    def _read_at_target_fps(self, video_path: Path):
        import cv2

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise VideoValidationError(
                "invalid_video",
                "Không mở được video MP4.",
            )
        source_fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not math.isfinite(source_fps) or source_fps <= 0:
            source_fps = self.target_fps

        frames = []
        source_index = 0
        next_target_time = 0.0
        hard_decode_limit = max(
            int(self.max_frames * max(source_fps / self.target_fps, 1.0)) + 5,
            self.max_frames + 5,
        )
        try:
            while source_index < hard_decode_limit:
                ok, frame_bgr = capture.read()
                if not ok:
                    break
                current_time = source_index / source_fps
                if current_time + 1e-9 >= next_target_time:
                    frames.append(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
                    next_target_time += 1.0 / self.target_fps
                    if len(frames) > self.max_frames:
                        break
                source_index += 1
        finally:
            capture.release()
        if not frames:
            raise VideoValidationError(
                "no_frames",
                "Video không có khung hình đọc được.",
            )
        return frames, source_fps

    @staticmethod
    def _quality(mouth_frames, face_detection_ratio):
        import cv2
        import numpy as np

        brightness = float(mouth_frames.mean())
        contrast = float(mouth_frames.std())
        blur_values = [
            float(cv2.Laplacian(frame, cv2.CV_64F).var())
            for frame in mouth_frames[:: max(1, len(mouth_frames) // 30)]
        ]
        motion = 0.0
        if len(mouth_frames) > 1:
            motion = float(
                np.abs(
                    mouth_frames[1:].astype(np.float32)
                    - mouth_frames[:-1].astype(np.float32)
                ).mean()
            )
        return {
            "face_detection_ratio": (
                round(face_detection_ratio, 4)
                if face_detection_ratio is not None
                else None
            ),
            "brightness_mean": round(brightness, 2),
            "contrast_std": round(contrast, 2),
            "blur_score": round(float(np.median(blur_values)), 2),
            "temporal_motion": round(motion, 2),
            "quality_is_calibrated": False,
        }

    @staticmethod
    def _quality_warnings(quality: dict[str, Any]) -> list[str]:
        warnings = []
        ratio = quality.get("face_detection_ratio")
        if ratio is not None and ratio < 0.9:
            warnings.append(
                "Khuôn mặt bị mất dấu ở một số khung hình; nên quay lại chính diện."
            )
        if quality["brightness_mean"] < 45:
            warnings.append("Video khá tối; hãy tăng ánh sáng phía trước mặt.")
        if quality["brightness_mean"] > 220:
            warnings.append("Video bị dư sáng; chi tiết môi có thể bị mất.")
        if quality["contrast_std"] < 18:
            warnings.append("Độ tương phản vùng miệng thấp.")
        if quality["blur_score"] < 18:
            warnings.append("Vùng miệng có dấu hiệu mờ/rung.")
        if quality["temporal_motion"] < 0.8:
            warnings.append("Chuyển động môi rất ít; kiểm tra lại đầu/cuối câu.")
        return warnings
