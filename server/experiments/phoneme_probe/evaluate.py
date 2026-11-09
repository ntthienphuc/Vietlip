"""Blind held-out scoring and development-only phoneme reranker selection."""
from __future__ import annotations
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

import torch
from app.services.native_engine import NativeAvsrEngine
from scripts.benchmark_models import settings
from .codec import VietnamesePhones, UnsupportedSyllable, words, edit_distance, ctc_min_frames
from .model import PhonemeHead, greedy, phone_error


def rerank(candidates, ctc_scores, weight):
    # Unsupported loanwords must not silently disqualify otherwise good candidates.
    if weight == 0 or any(s is None for s in ctc_scores):
        return 0
    return max(range(len(candidates)),key=lambda i:candidates[i]['raw_score']+weight*ctc_scores[i])


def aggregate(rows, weight):
    result = dict(clips=len(rows),errors=0,words=0,char_errors=0,chars=0,unavailable=0,
                  head_phone_errors=0,head_phones=0,head_empty=0,rerank_changed=0,rerank_unsupported=0)
    for r in rows:
        index=rerank(r['candidates'],r['ctc_scores'],weight)
        candidate=r['candidates'][index]
        result['errors']+=candidate['errors'];result['words']+=len(words(r['reference']))
        result['char_errors']+=candidate['char_errors'];result['chars']+=len(''.join(words(r['reference'])))
        result['unavailable']+=not bool(candidate['text'].strip())
        result['rerank_changed']+=index!=0
        result['rerank_unsupported']+=any(s is None for s in r['ctc_scores'])
        if r['phone_reference_supported']:
            result['head_phone_errors']+=r['head_phone_errors']
            result['head_phones']+=r['head_phones']
            result['head_empty']+=not any(t!='|' for t in r['head_prediction'])
    result['wer']=result['errors']/max(1,result['words'])
    result['cer']=result['char_errors']/max(1,result['chars'])
    result['head_per']=result['head_phone_errors']/max(1,result['head_phones'])
    result['phone_reference_supported_clips']=sum(r['phone_reference_supported'] for r in rows)
    result['nbest_oracle_errors']=sum(min(c['errors'] for c in r['candidates']) for r in rows)
    result['median_head_ms']=statistics.median(r['head_ms'] for r in rows)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--features',type=Path,required=True)
    p.add_argument('--head',type=Path,required=True)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--phone-manifest',type=Path)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    dataset=json.loads(args.dataset.read_text(encoding='utf8'))
    cache_identity=json.loads((args.features/'IDENTITY.json').read_text())
    payload=torch.load(args.head,map_location='cpu',weights_only=True)
    assert cache_identity==payload['feature_identity']
    assert hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()==cache_identity['checkpoint_sha256']
    codec=VietnamesePhones(Path(dataset['dependency']['path']),dataset['dialect'])
    segmental,tonal=payload['segmental_tokens'],payload['tonal_tokens']
    ids={s:i for i,s in enumerate(segmental)}
    head=PhonemeHead(**payload['config']).to('cuda').eval()
    head.load_state_dict(payload['state_dict'],strict=True)
    engine=NativeAvsrEngine(replace(settings(args.checkpoint,device='cuda',beam=3),precision='float32',nbest=3))
    engine.load()
    items=[r for r in dataset['records'] if r['split']!='train']
    if args.phone_manifest:
        phone=json.loads(args.phone_manifest.read_text(encoding='utf8'))
        items.extend(dict(id=f"phone/{r['id']}",split='phone',text=r['reference']) for r in phone['segments'])
    rows=[];loss_fn=torch.nn.CTCLoss(reduction='sum',zero_infinity=False)
    start=time.perf_counter()
    for r in items:
        key=hashlib.sha256(r['id'].encode()).hexdigest()[:24]
        feature=torch.load(args.features/f'{key}.pt',map_location='cpu',weights_only=True)['encoded'].to('cuda')
        with torch.inference_mode():
            torch.cuda.synchronize();tick=time.perf_counter()
            logits,tlogits=head(feature[None])
            logp=logits[0].log_softmax(-1)
            torch.cuda.synchronize();head_ms=(time.perf_counter()-tick)*1000
            prediction=greedy(logits[0],len(feature),segmental)
            hypotheses=engine._beams[3](feature)
            candidates=[];scores=[]
            for hyp in hypotheses[:3]:
                text=engine._text([int(i) for i in hyp.yseq[1:] if 0<int(i)<engine._model.eos])
                candidate=dict(text=text,raw_score=float(hyp.score),
                    errors=edit_distance(words(r['text']),words(text)),
                    char_errors=edit_distance(''.join(words(r['text'])),''.join(words(text))))
                candidates.append(candidate)
                try:
                    seq=codec.encode(text)
                    target=torch.tensor([ids[s] for s in seq],device='cuda',dtype=torch.long)
                    if not seq or ctc_min_frames(seq)>len(feature):
                        scores.append(None)
                    else:
                        loss=loss_fn(logp[:,None,:],target,torch.tensor([len(feature)]),
                                     torch.tensor([len(seq)]))
                        scores.append(-float(loss) if torch.isfinite(loss) else None)
                except (UnsupportedSyllable,KeyError):
                    scores.append(None)
        assert candidates
        supported=True;pe=pn=0;unsupported=None
        try:
            reference=codec.encode(r['text'])
            pe,pn=phone_error(reference,prediction)
        except UnsupportedSyllable as exc:
            supported=False;unsupported=str(exc);reference=[]
        row=dict(id=r['id'],split=r['split'],reference=r['text'],head_prediction=prediction,
            reference_phones=reference,phone_reference_supported=supported,unsupported_reference=unsupported,
            head_phone_errors=pe,head_phones=pn,head_ms=head_ms,candidates=candidates,ctc_scores=scores)
        rows.append(row)
        if len(rows)%40==0 or len(rows)==len(items):
            (args.output/'ROWS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
            print(f'Evaluated {len(rows)}/{len(items)}; {time.perf_counter()-start:.1f}s',flush=True)
    weights=[0,.1,.3,.6,1.]
    dev=[r for r in rows if r['split']=='dev']
    sweep=[dict(weight=w,**aggregate(dev,w)) for w in weights]
    chosen=min(sweep,key=lambda s:(s['errors'],s['weight']))['weight']
    report=dict(head_checkpoint=str(args.head),head_sha256=hashlib.sha256(args.head.read_bytes()).hexdigest(),
        selected_epoch=payload['epoch'],selection='Head epoch: dev segmental PER. Reranking weight: dev WER only, ties prefer zero.',
        weights=sweep,selected_weight=chosen,
        scope=dataset['scope'],lexical_holdout=dataset['lexical_holdout'],audio_used_for_inference=False,
        phone_scope='Confirmed seven prompts, audio-assisted oracle slices; NOT continuous live or phone-paint latency.',
        reference_limitation='Vietnamese canonical Northern broad forms; foreign strings rejected, no invented pronunciations.',
        inference='Head receives visual states only. G2P receives candidate texts for rescoring; reference texts only score outcomes.',
        baseline={},selected={})
    for split in sorted({r['split'] for r in rows}):
        selected=[r for r in rows if r['split']==split]
        report['baseline'][split]=aggregate(selected,0)
        report['selected'][split]=aggregate(selected,chosen)
    (args.output/'EVALUATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(selected_weight=chosen,baseline=report['baseline'],selected=report['selected']),ensure_ascii=False),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8')
    main()
