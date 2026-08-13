from __future__ import annotations

import cv2
import numpy as np


VISUAL_FEATURE_NAMES = [
    "log_frame_count",
    "brightness_mean",
    "brightness_std",
    "contrast_mean",
    "contrast_std",
    "blur_log_mean",
    "blur_log_std",
    "gradient_mean",
    "gradient_std",
    "motion_mean",
    "motion_std",
    "dark_fraction",
    "bright_fraction",
    "center_border_difference",
]


def visual_features(frames: np.ndarray, max_samples: int = 32) -> dict[str, float]:
    if frames.ndim != 3 or frames.shape[0] == 0:
        raise ValueError("expected non-empty grayscale frames shaped [T,H,W]")
    indices = np.unique(np.linspace(0, frames.shape[0] - 1, min(max_samples, frames.shape[0]), dtype=int))
    sampled = frames[indices].astype(np.float32) / 255.0
    frame_means = sampled.mean(axis=(1, 2))
    frame_stds = sampled.std(axis=(1, 2))
    blur = []
    gradient = []
    for frame in sampled:
        laplacian = cv2.Laplacian(frame, cv2.CV_32F)
        blur.append(float(laplacian.var()))
        gx = cv2.Sobel(frame, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(frame, cv2.CV_32F, 0, 1, ksize=3)
        gradient.append(float(np.sqrt(gx * gx + gy * gy).mean()))
    motion = np.abs(np.diff(sampled, axis=0)).mean(axis=(1, 2)) if len(sampled) > 1 else np.zeros(1)
    height, width = sampled.shape[1:]
    center = sampled[:, height // 4 : 3 * height // 4, width // 4 : 3 * width // 4]
    center_mean = float(center.mean())
    border_mean = float((sampled.sum() - center.sum()) / max(sampled.size - center.size, 1))
    blur_log = np.log1p(np.asarray(blur))
    gradients = np.asarray(gradient)
    return {
        "log_frame_count": float(np.log1p(frames.shape[0])),
        "brightness_mean": float(frame_means.mean()),
        "brightness_std": float(frame_means.std()),
        "contrast_mean": float(frame_stds.mean()),
        "contrast_std": float(frame_stds.std()),
        "blur_log_mean": float(blur_log.mean()),
        "blur_log_std": float(blur_log.std()),
        "gradient_mean": float(gradients.mean()),
        "gradient_std": float(gradients.std()),
        "motion_mean": float(motion.mean()),
        "motion_std": float(motion.std()),
        "dark_fraction": float((sampled < 0.08).mean()),
        "bright_fraction": float((sampled > 0.92).mean()),
        "center_border_difference": center_mean - border_mean,
    }
