from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from .features import AUTO_FEATURE_NAMES
from .visual import VISUAL_FEATURE_NAMES


UTILITY_FEATURE_NAMES = AUTO_FEATURE_NAMES + VISUAL_FEATURE_NAMES + ["auto_risk"]


def utility_matrix(
    rows: list[dict],
    auto_risks: np.ndarray,
    *,
    include_visual: bool = True,
    auto_feature_names: list[str] = AUTO_FEATURE_NAMES,
) -> np.ndarray:
    values = []
    for row, auto_risk in zip(rows, auto_risks):
        features = [float(row["auto_features"][name]) for name in auto_feature_names]
        if include_visual:
            features += [float(row["visual_features"][name]) for name in VISUAL_FEATURE_NAMES]
        values.append(features + [float(auto_risk)])
    return np.asarray(values, dtype=np.float64)


def decision_loss(
    row: dict,
    accepted: bool,
    reject_cost: float,
    target: str = "clipped_clip_wer",
) -> float:
    if target == "clipped_clip_wer":
        return min(float(row["errors"]["clip_wer"]), 1.0) if accepted else reject_cost
    if target == "word_error_mass":
        if accepted:
            return float(row["errors"]["word_errors"])
        return reject_cost * float(row["errors"]["reference_words"])
    raise ValueError(f"unknown utility target: {target}")


def verifier_utility(
    rows: list[dict],
    auto_accept: np.ndarray,
    joint_accept: np.ndarray,
    reject_cost: float,
    target: str = "clipped_clip_wer",
) -> np.ndarray:
    return np.asarray(
        [
            decision_loss(row, bool(auto), reject_cost, target)
            - decision_loss(row, bool(joint), reject_cost, target)
            for row, auto, joint in zip(rows, auto_accept, joint_accept)
        ],
        dtype=np.float64,
    )


def fit_utility_model(features: np.ndarray, targets: np.ndarray, seed: int):
    model = HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_iter=200,
        max_leaf_nodes=15,
        min_samples_leaf=30,
        l2_regularization=1.0,
        random_state=seed,
    )
    model.fit(features, targets)
    return model
