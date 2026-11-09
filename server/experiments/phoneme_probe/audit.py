"""Audit lexical holdouts and quantify reliance on ordered visual evidence."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import torch
from .codec import VietnamesePhones
from .model import PhonemeHead, greedy, phone_error


def chunks(tokens):
    result, current = [], []
    for token in tokens:
        if token == '|':
            if current:
                result.append(tuple(current)); current=[]
        else:
            current.append(token)
    if current:
        result.append(tuple(current))
    return result


def exact_aligned(reference, hypothesis):
    # Return reference indices correctly aligned by minimum syllable edit cost.
    costs=[[0]*(len(hypothesis)+1) for _ in range(len(reference)+1)]
    for i in range(len(reference)+1): costs[i][0]=i
    for j in range(len(hypothesis)+1): costs[0][j]=j
    for i,a in enumerate(reference,1):
        for j,b in enumerate(hypothesis,1):
            costs[i][j]=min(costs[i-1][j]+1,costs[i][j-1]+1,costs[i-1][j-1]+(a!=b))
    i,j=len(reference),len(hypothesis);correct=set()
    while i or j:
        if i and j and costs[i][j]==costs[i-1][j-1]+(reference[i-1]!=hypothesis[j-1]):
            if reference[i-1]==hypothesis[j-1]:correct.add(i-1)
            i-=1;j-=1
        elif i and costs[i][j]==costs[i-1][j]+1:i-=1
        else:j-=1
    return correct


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--features',type=Path,required=True)
    p.add_argument('--head',type=Path,required=True)
    p.add_argument('--evaluation',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    d=json.loads(args.dataset.read_text(encoding='utf8'))
    rows=json.loads((args.evaluation/'ROWS.json').read_text(encoding='utf8'))
    codec=VietnamesePhones(Path(d['dependency']['path']))
    trainwords={w for r in d['records'] if r['split']=='train' for w in r['words']}
    train_segmental={codec.syllable(w)[0] for w in trainwords}
    train_tonal={codec.syllable(w) for w in trainwords}
    holdout={}
    for w in d['lexical_holdout']:
        phones,tone=codec.syllable(w)
        holdout[w]=dict(word_seen_in_head_train=w in trainwords,
            same_segmental_sequence_seen=phones in train_segmental,
            same_tonal_sequence_seen=(phones,tone) in train_tonal,
            phones=phones,tone=tone,occurrences=0,exact_aligned_phone_syllables=0)
    source={r['id']:r for r in d['records']}
    for r in rows:
        if r['split']!='lexical_test':continue
        words=source[r['id']]['words']
        refs=[codec.syllable(w)[0] for w in words]
        correct=exact_aligned(refs,chunks(r['head_prediction']))
        for i,w in enumerate(words):
            if w in holdout:
                holdout[w]['occurrences']+=1
                holdout[w]['exact_aligned_phone_syllables']+=i in correct
    payload=torch.load(args.head,map_location='cpu',weights_only=True)
    torch.set_num_threads(4);torch.manual_seed(1706)
    head=PhonemeHead(**payload['config']).eval()
    head.load_state_dict(payload['state_dict'])
    controls={k:dict(errors=0,phones=0) for k in ('ordered','shuffled','static_mean')}
    with torch.inference_mode():
        for r in d['records']:
            if r['split']!='test':continue
            key=hashlib.sha256(r['id'].encode()).hexdigest()[:24]
            x=torch.load(args.features/f'{key}.pt',weights_only=True,map_location='cpu')['encoded']
            inputs=dict(ordered=x,shuffled=x[torch.randperm(len(x))],
                        static_mean=x.mean(0,keepdim=True).repeat(len(x),1))
            for mode,value in inputs.items():
                logits,_=head(value[None])
                hyp=greedy(logits[0],len(x),payload['segmental_tokens'])
                e,n=phone_error(r['phones'],hyp)
                controls[mode]['errors']+=e;controls[mode]['phones']+=n
    for stats in controls.values():stats['per']=stats['errors']/stats['phones']
    report=dict(holdout=holdout,controls=controls,
        alignment='Minimum-edit alignment of whole predicted IPA syllables using predicted boundaries. Tone excluded; not spelling or semantic word accuracy.',
        controls_scope='Corrupt cached encoder states, not original images. Encoder itself already uses utterance context. This does not prove causal lip-motion learning.',
        limitations=d['scope'])
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8')
    main()
