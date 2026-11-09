"""CTC Viterbi alignment of model predictions, without reference text or audio."""

from __future__ import annotations
import numpy as np


def align_words(logp, token_ids, tokens, fps, *, decode_pieces=None):
    if not token_ids or len(logp) < len(token_ids):
        return []
    labels = np.zeros(2 * len(token_ids) + 1, dtype=np.int64)
    labels[1::2] = token_ids
    states = len(labels)
    previous = np.full(states, -np.inf, dtype=np.float32)
    previous[0] = logp[0, 0]
    previous[1] = logp[0, labels[1]]
    back = np.zeros((len(logp), states), dtype=np.int8)
    skip = (labels != 0) & (labels != np.roll(labels, 2))
    skip[:2] = False
    for t in range(1, len(logp)):
        choices = np.stack(
            [previous, np.r_[-np.inf, previous[:-1]], np.r_[-np.inf, -np.inf, previous[:-2]]]
        )
        choices[2, ~skip] = -np.inf
        back[t] = choices.argmax(0)
        previous = choices.max(0) + logp[t, labels]
    state = states - 1 if previous[-1] >= previous[-2] else states - 2
    if not np.isfinite(previous[state]):
        return []
    spans = [[] for _ in token_ids]
    for t in range(len(logp) - 1, -1, -1):
        if state % 2:
            spans[state // 2].append(t)
        if t:
            state -= int(back[t, state])
    groups = []
    for identifier, span in zip(token_ids, spans):
        if not span:
            return []
        piece = tokens[identifier]
        boundary = piece.startswith("▁") or piece == "<space>"
        if boundary or not groups:
            groups.append(
                {"pieces": [piece], "start": min(span) / fps, "end": (max(span) + 1) / fps}
            )
        else:
            groups[-1]["pieces"].append(piece)
            groups[-1]["end"] = (max(span) + 1) / fps
    words = []
    for group in groups:
        pieces = group.pop("pieces")
        text = (
            decode_pieces(pieces)
            if decode_pieces
            else "".join(pieces).replace("▁", " ").replace("<space>", " ")
        ).strip()
        if text:
            words.append({"text": text, **group})
    return words
