from __future__ import annotations

import math
from itertools import combinations

import numpy as np

from .text import similarity


AUTO_FEATURE_NAMES = [
    "top1_score_per_word",
    "top12_margin_per_word",
    "nbest_entropy",
    "nbest_concentration",
    "top1_mean_support",
    "nbest_diversity",
    "words_per_frame",
]

AUTO_FEATURE_NAMES_V2 = AUTO_FEATURE_NAMES + [
    "top1_score_per_frame",
    "top12_margin_per_frame",
    "top13_margin_per_word",
    "score_gap_mean_per_word",
    "score_gap_std_per_word",
    "score_slope_per_rank",
    "effective_nbest_size",
    "top3_probability_mass",
    "weighted_top1_support",
    "top1_word_count_log",
    "top1_character_count_log",
    "frames_per_word_log",
    "weighted_word_count_mean",
    "weighted_word_count_std",
    "word_count_range",
    "top1_word_count_deviation",
    "weighted_score_per_word_mean",
    "weighted_score_per_word_std",
    "unique_hypothesis_fraction",
    "repeated_word_fraction",
    "digit_token_fraction",
]

JOINT_FEATURE_NAMES = [
    "auto_risk",
    "top1_word_agreement",
    "top1_character_agreement",
    "auto_supported_by_av_nbest",
    "av_supported_by_auto_nbest",
]


def _softmax(values: list[float]) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    array -= np.max(array)
    weights = np.exp(array)
    return weights / max(float(weights.sum()), 1e-12)


def auto_features(row: dict) -> dict[str, float]:
    candidates = row["auto_nbest"]
    top1 = candidates[0]
    word_count = max(len(top1["text"].split()), 1)
    scores = [float(candidate.get("score", 0.0)) for candidate in candidates]
    probabilities = _softmax(scores)
    entropy = -float(np.sum(probabilities * np.log(np.maximum(probabilities, 1e-12))))
    entropy /= max(math.log(max(len(probabilities), 2)), 1e-12)
    top1_support = [similarity(top1["text"], candidate["text"]) for candidate in candidates[1:]]
    pairwise = [
        similarity(left["text"], right["text"])
        for left, right in combinations(candidates, 2)
    ]
    return {
        "top1_score_per_word": scores[0] / word_count,
        "top12_margin_per_word": (scores[0] - scores[1]) / word_count if len(scores) > 1 else 0.0,
        "nbest_entropy": entropy,
        "nbest_concentration": float(probabilities[0]),
        "top1_mean_support": float(np.mean(top1_support)) if top1_support else 1.0,
        "nbest_diversity": 1.0 - (float(np.mean(pairwise)) if pairwise else 1.0),
        "words_per_frame": len(top1["text"].split()) / max(int(row.get("frame_count", 1)), 1),
    }


def auto_features_v2(row: dict) -> dict[str, float]:
    features = auto_features(row)
    candidates = row["auto_nbest"]
    scores = np.asarray([float(candidate.get("score", 0.0)) for candidate in candidates], dtype=np.float64)
    probabilities = _softmax(scores.tolist())
    texts = [candidate["text"] for candidate in candidates]
    word_counts = np.asarray([max(len(text.split()), 1) for text in texts], dtype=np.float64)
    character_counts = np.asarray([max(len(text.replace(" ", "")), 1) for text in texts], dtype=np.float64)
    frame_count = max(int(row.get("frame_count", 1)), 1)
    top1_words = texts[0].split()
    score_gaps = scores[:-1] - scores[1:] if len(scores) > 1 else np.zeros(1, dtype=np.float64)
    score_per_word = scores / word_counts
    top1_support = np.asarray([similarity(texts[0], text) for text in texts[1:]], dtype=np.float64)
    support_weights = probabilities[1:]
    weighted_support = (
        float(np.sum(top1_support * support_weights) / max(float(support_weights.sum()), 1e-12))
        if len(top1_support)
        else 1.0
    )
    repeated_fraction = 1.0 - len(set(top1_words)) / max(len(top1_words), 1)
    digit_fraction = sum(any(character.isdigit() for character in word) for word in top1_words) / max(len(top1_words), 1)
    weighted_words = float(np.sum(probabilities * word_counts))
    features.update(
        {
            "top1_score_per_frame": float(scores[0] / frame_count),
            "top12_margin_per_frame": float((scores[0] - scores[1]) / frame_count) if len(scores) > 1 else 0.0,
            "top13_margin_per_word": float((scores[0] - scores[2]) / word_counts[0]) if len(scores) > 2 else 0.0,
            "score_gap_mean_per_word": float(score_gaps.mean() / word_counts[0]),
            "score_gap_std_per_word": float(score_gaps.std() / word_counts[0]),
            "score_slope_per_rank": float((scores[0] - scores[-1]) / max(len(scores) - 1, 1)),
            "effective_nbest_size": float(np.exp(-np.sum(probabilities * np.log(np.maximum(probabilities, 1e-12))))),
            "top3_probability_mass": float(probabilities[:3].sum()),
            "weighted_top1_support": weighted_support,
            "top1_word_count_log": float(np.log1p(word_counts[0])),
            "top1_character_count_log": float(np.log1p(character_counts[0])),
            "frames_per_word_log": float(np.log1p(frame_count / word_counts[0])),
            "weighted_word_count_mean": weighted_words,
            "weighted_word_count_std": float(np.sqrt(np.sum(probabilities * np.square(word_counts - weighted_words)))),
            "word_count_range": float(word_counts.max() - word_counts.min()),
            "top1_word_count_deviation": float(word_counts[0] - weighted_words),
            "weighted_score_per_word_mean": float(np.sum(probabilities * score_per_word)),
            "weighted_score_per_word_std": float(np.sqrt(np.sum(probabilities * np.square(score_per_word - np.sum(probabilities * score_per_word))))),
            "unique_hypothesis_fraction": len(set(texts)) / max(len(texts), 1),
            "repeated_word_fraction": float(repeated_fraction),
            "digit_token_fraction": float(digit_fraction),
        }
    )
    return features


def agreement_features(row: dict, auto_risk: float) -> dict[str, float]:
    auto_top1 = row["auto_top1"]
    av_top1 = row["av_top1"]
    auto_nbest = [candidate["text"] for candidate in row["auto_nbest"]]
    av_nbest = [candidate["text"] for candidate in row["av_nbest"]]
    return {
        "auto_risk": float(auto_risk),
        "top1_word_agreement": similarity(auto_top1, av_top1),
        "top1_character_agreement": similarity(auto_top1, av_top1, characters=True),
        "auto_supported_by_av_nbest": max(similarity(auto_top1, candidate) for candidate in av_nbest),
        "av_supported_by_auto_nbest": max(similarity(av_top1, candidate) for candidate in auto_nbest),
    }


def matrix(rows: list[dict], names: list[str], key: str) -> np.ndarray:
    return np.asarray([[float(row[key][name]) for name in names] for row in rows], dtype=np.float64)
