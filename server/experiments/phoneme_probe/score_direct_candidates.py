"""Check direct phoneme proposals against the frozen visual text decoder.

All candidates, including SO17, receive the same teacher-forced attention/CTC
score. References only enter the final evaluator, never candidate generation.
"""
from __future__ import annotations
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time
import torch
from app.services.native_engine import NativeAvsrEngine
from app.services.phoneme_direct import DirectPhonemeDecoder
from app.services.word_alignment import align_words
from scripts.benchmark_models import settings


def score_candidates(engine, encoded, candidates):
    model=engine._model
    ids=[[i+1 for i in engine._spm.encode(c['text'],out_type=int)] for c in candidates]
    assert all(engine._text(seq)==c['text'] for seq,c in zip(ids,candidates))
    lengths=torch.tensor([len(s)+1 for s in ids],device=encoded.device)
    size=int(lengths.max());batch=len(ids)
    inputs=torch.zeros((batch,size),dtype=torch.long,device=encoded.device)
    targets=torch.zeros_like(inputs)
    for i,seq in enumerate(ids):
        inputs[i,:len(seq)+1]=torch.tensor([model.sos]+seq,device=encoded.device)
        targets[i,:len(seq)+1]=torch.tensor(seq+[model.eos],device=encoded.device)
    valid=torch.arange(size,device=encoded.device)[None,:]<lengths[:,None]
    mask=valid[:,None,:]&torch.ones((size,size),dtype=torch.bool,device=encoded.device).tril()[None]
    with torch.inference_mode():
        logits=model.decoder(inputs,mask,encoded[None].expand(batch,-1,-1),None)[0]
        ar=(logits.log_softmax(-1).gather(-1,targets[...,None])[...,0]*valid).sum(-1).cpu()
        logp=model.ctc.log_softmax(encoded[None])[0].cpu()
        ctc=-torch.nn.functional.ctc_loss(logp[:,None].expand(-1,batch,-1),
            torch.tensor([v for seq in ids for v in seq]),torch.full((batch,),len(encoded)),
            torch.tensor([len(seq) for seq in ids]),reduction='none',zero_infinity=False)
    output=[]
    for i,candidate in enumerate(candidates):
        score=float(ar[i]*(1-engine.settings.ctc_weight)+ctc[i]*engine.settings.ctc_weight)
        output.append(dict(candidate,native_score=score,attention_score=float(ar[i]),
            text_ctc_score=float(ctc[i]),token_count=len(ids[i]),
            words=align_words(logp.numpy(),ids[i],engine.tokens,25,decode_pieces=engine._spm.decode)))
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('checkpoint','head','lexicon','config','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--cache',type=Path,action='append',required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    engine=NativeAvsrEngine(replace(settings(args.checkpoint,device='cuda',beam=3),precision='float32',nbest=3))
    engine.load()
    decoder=DirectPhonemeDecoder(args.head,args.lexicon,args.checkpoint,'cuda',
        json.loads(args.config.read_text(encoding='utf8')))
    results=[]
    for folder in args.cache:
        cache=json.loads((folder/'CACHE.json').read_text(encoding='utf8'))
        assert cache['checkpoint_sha256']==hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
        for row in cache['records']:
            feature=Path(row['feature_file'])
            if not feature.is_absolute():feature=folder/feature
            encoded=torch.load(feature,map_location='cpu',weights_only=True)['encoded']
            assert hashlib.sha256(encoded.numpy().tobytes()).hexdigest()==row['encoded_sha256']
            encoded=encoded.to('cuda')
            direct,detail=decoder.decode(encoded)
            candidates=[dict(c,source='so17') for c in row['candidates']]
            candidates.extend(c for c in direct if c['text'] not in {x['text'] for x in candidates})
            tick=time.perf_counter()
            scored=score_candidates(engine,encoded,candidates)
            torch.cuda.synchronize()
            results.append(dict(id=row['id'],cache=str(folder.resolve()),
                direct_candidates=direct,direct_ms=detail['elapsed_ms'],candidates=scored,
                rescore_ms=(time.perf_counter()-tick)*1000))
            if len(results)%40==0:print('Scored',len(results),flush=True)
        (args.output/'SCORES.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    print('Completed',len(results),'windows',flush=True)


if __name__=='__main__':main()
