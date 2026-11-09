import numpy as np
import pytest
from app.services.phoneme_direct import PronunciationDecoder


def decoder():
    entries=[dict(word=w,segmental=p) for w,p in [
        ('ba',['b','a','|']),('ma',['m','a','|']),('bba',['b','b','a','|'])]]
    resource=dict(entries=entries,unigram={'ba':10,'ma':10,'bba':1},
        bigram={},trigram={},contexts={})
    return PronunciationDecoder(resource,['<blank>','b','a','|','m'],lm_weight=0,beam=64,token_beam=5)


def posterior(ids):
    logp=np.full((len(ids),5),-25.,dtype=np.float32)
    logp[np.arange(len(ids)),ids]=0
    return logp


def test_direct_words_need_no_text_candidates_and_have_ordered_spans():
    result=decoder().decode(posterior([1,1,2,2,3,0,4,4,2,2,3,0]))
    assert result[0]['text']=='ba ma'
    a,b=result[0]['words']
    assert a['text']=='ba' and b['text']=='ma'
    assert a['start']==0 and a['end']<=b['start']<b['end']<=12/25


def test_repeated_phone_requires_blank_and_right_edge_needs_no_boundary():
    repeated=decoder().decode(posterior([1,0,1,2,3]))
    assert repeated[0]['text']=='bba'
    collapsed=decoder().decode(posterior([1,1,2,3]))
    assert collapsed[0]['text']=='ba'
    no_boundary=decoder().decode(posterior([1,2]))
    assert no_boundary[0]['text']=='ba'
    assert no_boundary[0]['words'][0]['end']==pytest.approx(2/25)


def test_incomplete_final_syllable_is_not_invented():
    result=decoder().decode(posterior([1,2,3,0,4]))
    assert result[0]['text']=='ba'
    assert result[0]['words'][-1]['end']<=3/25
