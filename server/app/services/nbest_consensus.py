from __future__ import annotations

import math
import re
from typing import Any


_SPACE = re.compile(r"\s+")


def _words(text: str) -> list[str]:
    return _SPACE.sub(" ", text.strip().lower()).split()


def _word_distance(left: str, right: str) -> float:
    """Normalized Levenshtein distance over words in [0, 1]."""
    a = _words(left)
    b = _words(right)
    if not a and not b:
        return 0.0
    previous = list(range(len(b) + 1))
    for row, token_a in enumerate(a, start=1):
        current = [row]
        for column, token_b in enumerate(b, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (token_a != token_b),
                )
            )
        previous = current
    return previous[-1] / max(len(a), len(b), 1)


def summarize_nbest(alternatives: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return a transcript-preserving N-best consensus diagnostic.

    The selected medoid minimizes expected pairwise word-edit distance under
    score-derived weights. It is evidence for review, not a calibrated
    confidence and never replaces the primary transcript.
    """
    candidates = [
        item for item in alternatives
        if str(item.get("text") or "").strip()
    ]
    if not candidates:
        return None

    scores = [float(item.get("raw_score") or 0.0) for item in candidates]
    maximum = max(scores)
    unnormalized = [math.exp(max(score - maximum, -80.0)) for score in scores]
    total = max(sum(unnormalized), 1e-12)
    weights = [value / total for value in unnormalized]

    risks: list[float] = []
    for left in candidates:
        risks.append(
            sum(
                weight * _word_distance(str(left["text"]), str(right["text"]))
                for weight, right in zip(weights, candidates)
            )
        )
    selected_index = min(
        range(len(candidates)),
        key=lambda index: (risks[index], index),
    )
    top1_support = 1.0 - sum(
        weight
        * _word_distance(
            str(candidates[0]["text"]),
            str(candidate["text"]),
        )
        for weight, candidate in zip(weights, candidates)
    )
    return {
        "method": "score_weighted_nbest_medoid_word_edit",
        "candidate_index": selected_index,
        "candidate_text": str(candidates[selected_index]["text"]),
        "agrees_with_top1": selected_index == 0,
        "expected_word_edit_risk": round(risks[selected_index], 6),
        "top1_support": round(top1_support, 6),
        "candidate_weight": round(weights[selected_index], 6),
        "is_calibrated_probability": False,
        "transcript_owner_changed": False,
    }
