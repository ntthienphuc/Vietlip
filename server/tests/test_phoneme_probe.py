from pathlib import Path
import unicodedata

import pytest
import torch

from experiments.phoneme_probe.codec import VietnamesePhones, UnsupportedSyllable, ctc_min_frames
from experiments.phoneme_probe.model import PhonemeHead, greedy, phone_error
from experiments.phoneme_probe.evaluate import rerank
from experiments.phoneme_probe.audit import chunks, exact_aligned

DEPENDENCY = Path(__file__).resolve().parents[2]/'artifacts/phoneme_probe_20261106/deps/vPhon'


@pytest.fixture
def codec():
    if not (DEPENDENCY/'vPhon.py').exists():
        pytest.skip('Optional offline vPhon dependency is not installed')
    return VietnamesePhones(DEPENDENCY)


def test_shared_motion_does_not_collapse_bilabial_phonemes(codec):
    b, _ = codec.syllable('ba')
    m, _ = codec.syllable('ma')
    assert b[0] == 'ɓ' and m[0] == 'm' and b[1:] == m[1:]


def test_multichar_ipa_units_remain_atomic(codec):
    phones, _ = codec.syllable('thuốc')
    assert phones == ('tʰ','uə','k')
    assert codec.encode('thuốc') == ['tʰ','uə','k','|']


def test_tone_head_is_separate_from_segmental(codec):
    assert codec.encode('ma má mà mả mã mạ') == ['m','a','|']*6
    assert len({codec.syllable(w)[1] for w in 'ma má mà mả mã mạ'.split()}) == 6
    assert codec.encode('mẹ', tones=True)[-2] == 'tone:B2'


@pytest.mark.parametrize('word', ['bluetooth','camera','laser','123','LipLens'])
def test_foreign_and_numeric_inputs_are_explicitly_unsupported(codec,word):
    with pytest.raises(UnsupportedSyllable):
        codec.syllable(word)


def test_unicode_equivalence(codec):
    assert codec.encode('nghiêng') == codec.encode(unicodedata.normalize('NFD','nghiêng'))


def test_ctc_requires_blanks_between_repeated_targets():
    assert ctc_min_frames(['a','a','b']) == 4
    assert ctc_min_frames(['a','b','a']) == 3


def test_greedy_removes_blank_after_collapsing_not_before():
    logits = torch.full((5,3), -10.)
    logits[range(5),[1,1,0,1,2]] = 10
    assert greedy(logits,5,['<blank>','m','a']) == ['m','m','a']


def test_padding_cannot_change_valid_features():
    torch.manual_seed(2)
    head = PhonemeHead(8,16,5,7).eval()
    clip = torch.randn(1,9,8)
    padded = torch.cat([clip,torch.randn(1,6,8)*100],dim=1)
    a=head(clip,torch.tensor([9]))[0]
    b=head(padded,torch.tensor([9]))[0][:,:9]
    torch.testing.assert_close(a,b)


def test_phone_error_excludes_boundaries_and_optionally_tones():
    assert phone_error(['m','a','tone:A1','|'],['m','a','tone:B1','|']) == (0,2)
    assert phone_error(['m','a','tone:A1','|'],['m','a','tone:B1','|'],tones=True) == (1,3)


def test_rerank_missing_pronunciation_preserves_baseline():
    candidates=[dict(raw_score=-10),dict(raw_score=-11)]
    assert rerank(candidates,[None,-1],1) == 0
    assert rerank(candidates,[-10,-1],0) == 0
    assert rerank(candidates,[-10,-1],1) == 1


def test_heldout_alignment_preserves_repeats_and_empty_boundaries():
    assert chunks(['|','m','a','|','|','k','a']) == [('m','a'),('k','a')]
    reference=[('m','a'),('m','a'),('k','a')]
    assert exact_aligned(reference,reference) == {0,1,2}
    matched=exact_aligned(reference,[('m','a'),('k','a')])
    assert len(matched)==2 and 2 in matched


def test_ctc_head_can_learn_tiny_distinguishable_sequence():
    # Exercises actual gradients/loss, not just shape agreement.
    torch.manual_seed(4)
    torch.set_num_threads(2)
    head = PhonemeHead(4,16,4,4)
    features = torch.eye(4).repeat_interleave(3,0)[None]
    target = torch.tensor([1,2,3])
    optimizer=torch.optim.Adam(head.parameters(),lr=.02)
    loss_fn=torch.nn.CTCLoss()
    for _ in range(100):
        optimizer.zero_grad()
        logits,_=head(features)
        loss=loss_fn(logits.log_softmax(-1).transpose(0,1),target,
                     torch.tensor([12]),torch.tensor([3]))
        loss.backward();optimizer.step()
    head.eval()
    assert greedy(head(features)[0][0],12,['<blank>','a','b','c']) == ['a','b','c']
