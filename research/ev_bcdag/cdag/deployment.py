from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np

from .budgeted import invocation_mask
from .features import AUTO_FEATURE_NAMES, JOINT_FEATURE_NAMES, agreement_features, auto_features, matrix
from .utility_router import utility_matrix


class EVBCDAGController:
    def __init__(self, frozen_dir: Path):
        frozen_dir = Path(frozen_dir)
        with (frozen_dir / "router.pkl").open("rb") as handle:
            self.router = pickle.load(handle)
        self.policy = json.loads((frozen_dir / "policy.json").read_text(encoding="utf-8"))
        if self.router["auto_feature_names"] != AUTO_FEATURE_NAMES:
            raise RuntimeError("Auto feature schema differs from frozen router")
        if self.router["joint_feature_names"] != JOINT_FEATURE_NAMES:
            raise RuntimeError("joint feature schema differs from frozen router")

    def route_window(self, rows: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if len(rows) > int(self.policy["accounting_window_requests"]):
            raise ValueError("window exceeds frozen accounting size")
        featured = [dict(row, auto_features=auto_features(row)) for row in rows]
        auto_x = matrix(featured, AUTO_FEATURE_NAMES, "auto_features")
        auto_risk = self.router["auto_model"].predict_risk(auto_x)
        expected_utility = self.router["utility_model"].predict(
            utility_matrix(featured, auto_risk, include_visual=False)
        )
        invoked = invocation_mask(
            expected_utility,
            [row["sample_id"] for row in rows],
            float(self.policy["invocation_fraction"]),
        )
        return invoked, auto_risk, expected_utility

    def finalize_window(self, rows: list[dict], verifier_outputs: dict[str, dict]) -> list[dict]:
        invoked, auto_risk, expected_utility = self.route_window(rows)
        outputs = []
        for index, row in enumerate(rows):
            call = bool(invoked[index])
            risk = float(auto_risk[index])
            if call:
                if row["sample_id"] not in verifier_outputs:
                    raise KeyError(f"missing verifier output for invoked clip: {row['sample_id']}")
                verifier = verifier_outputs[row["sample_id"]]
                joint_row = dict(
                    row,
                    av_top1=verifier["top1"],
                    av_nbest=verifier["nbest"],
                )
                joint_row["agreement_features"] = agreement_features(joint_row, risk)
                joint_row["joint_features"] = dict(joint_row["agreement_features"])
                joint_risk = float(
                    self.router["joint_model"].predict_risk(
                        matrix([joint_row], JOINT_FEATURE_NAMES, "joint_features")
                    )[0]
                )
                risk = joint_risk
                accepted = risk <= float(self.policy["joint_accept_risk_max"])
            else:
                accepted = risk <= float(self.policy["auto_accept_risk_max"])
            outputs.append(
                {
                    "sample_id": row["sample_id"],
                    "verifier_invoked": call,
                    "expected_verifier_utility": float(expected_utility[index]),
                    "predicted_risk": risk,
                    "accepted": bool(accepted),
                    "returned_transcript": row["auto_top1"] if accepted else None,
                    "alternatives": [candidate["text"] for candidate in row["auto_nbest"][1:3]] if not accepted else [],
                    "transcript_owner": "auto",
                }
            )
        return outputs
