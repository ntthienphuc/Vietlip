"""Versioned adapter to James Kirby's vPhon; no letter-as-phoneme fallback.

vPhon stays an explicit external experiment dependency (GPL-3.0-or-later).
Each IPA onset/glide/nucleus/coda is one token; multi-codepoint IPA units
such as tʰ and iə must not be split into Unicode characters.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import importlib.util
from pathlib import Path
import sys
import unicodedata

VPHON_COMMIT = '076a5d3611d688325a71ad6dbbcd5868399bf5e7'
VPHON_FILES = {
    'vPhon.py': '6e0abb9de6a48a24bc8790b7a8a15e78a7128fb5ad48a0b17e27640b334ead40',
    'rules.py': '9f34e6ed1cb2d2a2a524f6113604a5d672f3990edf101b5ae64116f435776cf7',
}
TONES = {'ᴬ¹': 'A1', 'ᴬ²': 'A2', 'ᴮ¹': 'B1', 'ᴮ²': 'B2',
         'ᶜ¹': 'C1', 'ᶜ²': 'C2', 'ᴰ¹': 'B1', 'ᴰ²': 'B2'}


def words(text):
    text = unicodedata.normalize('NFC', text).lower()
    return ''.join(c if unicodedata.category(c)[0] in 'LNM' else ' '
                   for c in text).split()


class UnsupportedSyllable(ValueError):
    pass


class VietnamesePhones:
    def __init__(self, dependency: Path, dialect='n'):
        if dialect not in ('n', 'c', 's'):
            raise ValueError('Use an explicit Vietnamese dialect')
        self.dialect = dialect
        # The pinned external module imports rules by its historical module name.
        dependency = Path(dependency).resolve()
        for filename, expected in VPHON_FILES.items():
            if hashlib.sha256((dependency/filename).read_bytes()).hexdigest() != expected:
                raise ValueError(f'vPhon source differs from pinned version: {filename}')
        previous = sys.modules.pop('rules', None)
        sys.path.insert(0, str(dependency))
        try:
            spec = importlib.util.spec_from_file_location('_lip_probe_vphon', dependency/'vPhon.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
            sys.modules.pop('rules', None)
            if previous is not None:
                sys.modules['rules'] = previous
        self._trans = module.trans

    @lru_cache(maxsize=60000)
    def syllable(self, text):
        normalized = words(text)
        if len(normalized) != 1 or any(c.isdigit() for c in normalized[0]):
            raise UnsupportedSyllable(text)
        # Broad forms, no automatic glottal onset, preserve IPA superscripts.
        parts = self._trans(normalized[0], self.dialect, False, False,
                            False, True, True)
        if any(part is None for part in parts) or parts[4] not in TONES:
            raise UnsupportedSyllable(text)
        phones = tuple(part for part in parts[:4] if part)
        if not phones:
            raise UnsupportedSyllable(text)
        return phones, 'tone:' + TONES[parts[4]]

    def encode(self, text, *, tones=False):
        result = []
        for word in words(text):
            phones, tone = self.syllable(word)
            result.extend(phones)
            if tones:
                result.append(tone)
            result.append('|')
        return result


def edit_distance(reference, hypothesis):
    previous = list(range(len(hypothesis)+1))
    for i, a in enumerate(reference, 1):
        row = [i]
        for j, b in enumerate(hypothesis, 1):
            row.append(min(row[-1]+1, previous[j]+1, previous[j-1]+(a != b)))
        previous = row
    return previous[-1]


def ctc_min_frames(target):
    return len(target) + sum(a == b for a, b in zip(target, target[1:]))
