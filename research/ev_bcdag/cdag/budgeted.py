from __future__ import annotations

import math

import numpy as np


def invocation_mask(risks: np.ndarray, sample_ids: list[str], fraction: float) -> np.ndarray:
    if len(risks) != len(sample_ids):
        raise ValueError("risk and sample-id lengths differ")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("invocation fraction must be between zero and one")
    count = math.floor(fraction * len(sample_ids))
    ranked = sorted(range(len(sample_ids)), key=lambda index: (-float(risks[index]), sample_ids[index]))
    output = np.zeros(len(sample_ids), dtype=bool)
    output[ranked[:count]] = True
    return output


def windowed_rank_mask(
    scores: np.ndarray,
    sample_ids: list[str],
    fraction: float,
    window_size: int,
    *,
    highest: bool,
) -> np.ndarray:
    if len(scores) != len(sample_ids):
        raise ValueError("score and sample-id lengths differ")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between zero and one")
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    ordered = sorted(range(len(sample_ids)), key=lambda index: sample_ids[index])
    output = np.zeros(len(sample_ids), dtype=bool)
    for start in range(0, len(ordered), window_size):
        window = ordered[start : start + window_size]
        count = math.floor(fraction * len(window))
        ranked = sorted(
            window,
            key=lambda index: ((-1.0 if highest else 1.0) * float(scores[index]), sample_ids[index]),
        )
        output[ranked[:count]] = True
    return output


def compose_budgeted_arm(
    c0_rows: list[dict],
    c1_rows: list[dict],
    c2_rows: list[dict],
    invocation_fraction: float,
) -> list[dict]:
    if not 0.0 <= invocation_fraction <= 1.0:
        raise ValueError("invocation_fraction must be between zero and one")
    by_arm = [
        {row["sample_id"]: row for row in rows}
        for rows in (c0_rows, c1_rows, c2_rows)
    ]
    sample_ids = set(by_arm[0])
    if any(set(rows) != sample_ids for rows in by_arm[1:]):
        raise ValueError("C0/C1/C2 sample coverage differs")

    ordered_ids = sorted(sample_ids)
    mask = invocation_mask(
        np.asarray([float(by_arm[0][sample_id]["predicted_risk"]) for sample_id in ordered_ids]),
        ordered_ids,
        invocation_fraction,
    )
    invoked = {sample_id for sample_id, value in zip(ordered_ids, mask) if value}
    output = []
    for sample_id in sorted(sample_ids):
        auto_row = by_arm[0][sample_id]
        source = by_arm[2][sample_id] if sample_id in invoked else by_arm[1][sample_id]
        row = dict(auto_row)
        row["arm"] = "C4"
        row["predicted_risk"] = float(source["predicted_risk"])
        row["accepted"] = bool(source["accepted"])
        row["verifier_invoked"] = sample_id in invoked
        if sample_id in invoked:
            row["decision"] = "budgeted_verified_auto_top1" if row["accepted"] else "budgeted_verified_reject"
        else:
            row["decision"] = "budgeted_auto_top1" if row["accepted"] else "budgeted_auto_reject"
        row["returned_transcript"] = row["auto_top1"] if row["accepted"] else None
        output.append(row)
    return output
