"""Real tokenizer regressions for open vocabulary rendering, no GPU required."""
from pathlib import Path

import numpy as np
import pytest
import sentencepiece as spm

from app.services.native_engine import NativeAvsrEngine
from app.services.word_alignment import align_words


@pytest.fixture
def engine():
    root = Path(__file__).resolve().parents[1]
    instance = NativeAvsrEngine.__new__(NativeAvsrEngine)
    instance._spm = spm.SentencePieceProcessor(
        model_file=str(root / 'assets/tokenizers/vi.model'))
    instance.tokens = ['<blank>'] + [line.rsplit(maxsplit=1)[0] for line in
        (root / 'assets/tokenizers/vi_units.txt').read_text(encoding='utf8').splitlines()] + ['<eos>']
    assert instance.tokens[1:-1] == [instance._spm.id_to_piece(i)
        for i in range(instance._spm.get_piece_size())]
    return instance


@pytest.mark.parametrize('text', [
    'nguyễn viết văn linh', 'pin perovskite', 'lip lens',
    'máy lọc không khí', 'tôi thử ký hiệu 🧬 mới',
])
def test_round_trip_including_utf8_bytes(engine, text):
    ids = [i + 1 for i in engine._spm.encode(text)]
    assert engine._text([0, *ids, len(engine.tokens) - 1]) == text


def test_aligned_bytes_and_standalone_word_boundary(engine):
    text = 'tôi thử 🧬 mới'
    ids = [i + 1 for i in engine._spm.encode(text)]
    assert any(engine.tokens[i].startswith('<0x') for i in ids)
    path = [0]
    for identifier in ids:
        path.extend([identifier, 0])
    logp = np.full((len(path), len(engine.tokens)), -40, dtype=np.float32)
    logp[np.arange(len(path)), path] = 0
    words = align_words(logp, ids, engine.tokens, 25,
                        decode_pieces=engine._spm.decode)
    assert [word['text'] for word in words] == text.split()
    assert all(a['end'] <= b['start'] for a, b in zip(words, words[1:]))
    assert all(word['end'] > word['start'] for word in words)


def test_boundary_only_piece_starts_next_word():
    # A bare whitespace piece must not join a new OOV word to the previous word.
    tokens = ['<blank>', '▁tôi', '▁', 'x', 'y', '<eos>']
    ids = [1, 2, 3, 4]
    logp = np.full((4, len(tokens)), -40, dtype=np.float32)
    logp[np.arange(4), ids] = 0
    words = align_words(logp, ids, tokens, 25)
    assert [word['text'] for word in words] == ['tôi', 'xy']
