from __future__ import annotations

import re
import unicodedata


_SENTENCEPIECE_BYTE_RUN = re.compile(r"(?:<0x[0-9A-Fa-f]{2}>)+")


def decode_sentencepiece_bytes(value: str) -> str:
    def decode(match: re.Match[str]) -> str:
        byte_values = re.findall(r"<0x([0-9A-Fa-f]{2})>", match.group(0))
        try:
            return bytes.fromhex("".join(byte_values)).decode("utf-8")
        except UnicodeDecodeError:
            return match.group(0)

    return _SENTENCEPIECE_BYTE_RUN.sub(decode, str(value))


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", str(value)).lower()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def edit_distance(left: list[str], right: list[str]) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, left_item in enumerate(left, 1):
        current = [i]
        for j, right_item in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (left_item != right_item),
                )
            )
        previous = current
    return previous[-1]


def similarity(left: str, right: str, *, characters: bool = False) -> float:
    left = normalize_text(left)
    right = normalize_text(right)
    left_items = list(left.replace(" ", "")) if characters else left.split()
    right_items = list(right.replace(" ", "")) if characters else right.split()
    denominator = max(len(left_items), len(right_items), 1)
    return max(0.0, 1.0 - edit_distance(left_items, right_items) / denominator)


def error_counts(reference: str, hypothesis: str) -> dict[str, int | float | bool]:
    reference = normalize_text(reference)
    hypothesis = normalize_text(hypothesis)
    ref_words, hyp_words = reference.split(), hypothesis.split()
    ref_chars = list(reference.replace(" ", ""))
    hyp_chars = list(hypothesis.replace(" ", ""))
    word_errors = edit_distance(ref_words, hyp_words)
    char_errors = edit_distance(ref_chars, hyp_chars)
    return {
        "word_errors": word_errors,
        "reference_words": len(ref_words),
        "character_errors": char_errors,
        "reference_characters": len(ref_chars),
        "clip_wer": word_errors / max(len(ref_words), 1),
        "clip_cer": char_errors / max(len(ref_chars), 1),
        "exact": reference == hypothesis,
    }
