from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class ConstantRiskModel:
    risk: float

    def predict_risk(self, features: np.ndarray) -> np.ndarray:
        return np.full(features.shape[0], self.risk, dtype=np.float64)


@dataclass
class LogisticRiskModel:
    pipeline: Pipeline

    def predict_risk(self, features: np.ndarray) -> np.ndarray:
        return self.pipeline.predict_proba(features)[:, 1]


def fit_risk_model(features: np.ndarray, targets: np.ndarray, seed: int):
    unique = np.unique(targets)
    if len(unique) == 1:
        return ConstantRiskModel(float(unique[0]))
    pipeline = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "logistic",
                LogisticRegression(
                    class_weight="balanced",
                    C=1.0,
                    max_iter=2000,
                    random_state=seed,
                ),
            ),
        ]
    )
    pipeline.fit(features, targets)
    return LogisticRiskModel(pipeline)


def threshold_for_coverage(risks: np.ndarray, coverage: float) -> float:
    return float(np.quantile(risks, min(max(coverage, 0.0), 1.0)))

