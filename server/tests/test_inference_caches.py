import sys
from pathlib import Path
import numpy as np
import torch
from app.services.landmark_cache import LandmarkCache
from app.services.decoder_cache import cached_cross_attention


def test_landmark_cache_copies_outputs_and_bounds_storage():
    class Detector:
        calls=0
        def detect(self,frames,backend):
            self.calls+=len(frames)
            return [np.ones((4,2)) for _ in frames]
    detector=Detector();cache=LandmarkCache(2)
    a=np.zeros((5,5,3),dtype=np.uint8)
    first=cache.detect([a,a],detector,None,'full')
    first[0][:]=999
    again=cache.detect([a],detector,None,'full')
    assert np.all(again[0]==1) and detector.calls==1
    cache.detect([a+1,a+2],detector,None,'full')
    assert len(cache.entries)==2
    cache.detect([a],detector,None,'full')
    assert detector.calls==4


def test_cross_attention_cache_matches_original_for_changing_beam_width_and_resets():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vendor/auto_avsr'))
    from espnet.nets.pytorch_backend.transformer.attention import MultiHeadedAttention
    from types import SimpleNamespace
    torch.manual_seed(19)
    attention=MultiHeadedAttention(2,16,0).eval()
    decoder=SimpleNamespace(decoders=[SimpleNamespace(src_attn=attention)])
    original=attention.forward_qkv
    for _ in range(2):
        memory=torch.randn(1,11,16)
        queries=[torch.randn(n,1,16) for n in (1,3,2)]
        with torch.inference_mode():
            expected=[attention(q,memory.expand(len(q),-1,-1),memory.expand(len(q),-1,-1),None) for q in queries]
            with cached_cross_attention(decoder):
                actual=[attention(q,memory.expand(len(q),-1,-1),memory.expand(len(q),-1,-1),None) for q in queries]
            for a,b in zip(expected,actual):
                torch.testing.assert_close(a,b,rtol=1e-5,atol=1e-6)
        assert attention.forward_qkv==original


def test_incremental_decoder_matches_original_with_beam_reordering_and_new_utterance():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vendor/auto_avsr'))
    from espnet.nets.pytorch_backend.decoder.transformer_decoder import TransformerDecoder
    from app.services.incremental_decoder import IncrementalDecoderScorer
    torch.manual_seed(71)
    decoder=TransformerDecoder(31,attention_dim=16,attention_heads=2,
        linear_units=32,num_blocks=2,dropout_rate=0,positional_dropout_rate=0).eval()
    fast=IncrementalDecoderScorer(decoder)
    with torch.inference_mode():
        for _ in range(2):
            memory=torch.randn(11,16)
            fast.init_state(memory)
            slow_states=fast_states=[None]
            ys=torch.tensor([[30]])
            for step in range(6):
                expanded=memory.unsqueeze(0).expand(len(ys),-1,-1)
                expected,slow_states=decoder.batch_score(ys,slow_states,expanded)
                actual,fast_states=fast.batch_score(ys,fast_states,expanded)
                torch.testing.assert_close(actual,expected,atol=2e-6,rtol=1e-5)
                order=[0,0,0] if step==0 else [2,0,1]
                ys=torch.cat((ys[order],torch.randint(0,30,(3,1))),dim=1)
                slow_states=[slow_states[i] for i in order]
                fast_states=[fast_states[i] for i in order]


def test_cpu_ctc_prefix_matches_torch_with_repeats_and_eos_outside_prebeam():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vendor/auto_avsr'))
    from espnet.nets.scorers.ctc import CTCPrefixScorer
    from app.services.cpu_ctc_prefix import CpuCTCPrefixScorer
    class Head:
        def log_softmax(self,x): return torch.log_softmax(x,dim=-1)
    torch.manual_seed(28)
    memory=torch.randn(14,9)
    slow=CTCPrefixScorer(Head(),8)
    fast=CpuCTCPrefixScorer(Head(),8)
    slow_states=[slow.batch_init_state(memory)]
    fast_states=[fast.batch_init_state(memory)]
    y=torch.tensor([[8]])
    for token in (2,2,3,5):
        ids=torch.tensor([[2,3,5]])
        a,sa=slow.batch_score_partial(y,ids,slow_states,memory)
        b,sb=fast.batch_score_partial(y,ids,fast_states,memory)
        torch.testing.assert_close(a[:,[2,3,5,8]],b[:,[2,3,5,8]],atol=5e-5,rtol=1e-5)
        slow_states=[slow.select_state(sa,0,token)]
        fast_states=[fast.select_state(sb,0,token)]
        assert np.isfinite(fast_states[0][1]).all()
        y=torch.cat((y,torch.tensor([[token]])),dim=1)
