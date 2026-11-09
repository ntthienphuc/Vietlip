"""Build prefix and rolling windows without accessing evaluation outcomes."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
from .codec import VietnamesePhones,words,ctc_min_frames


def complete_word_core(timed_words,start,stop,fps=25):
    selected=[w for w in timed_words if w['start']>=start/fps-1e-6
              and w['end']<=stop/fps+1e-6 and w['end']>w['start']]
    if not selected:return None
    left=max(0,math.floor(selected[0]['start']*fps+1e-6)-start)
    right=min(stop-start,math.ceil(selected[-1]['end']*fps-1e-6)-start)
    return selected,left,right


def window_spans(frame_count):
    # Camera endpoints are on a 25 Hz grid, not snapped to word boundaries.
    ends=list(range(50,frame_count,38))+[frame_count]
    result=[]
    for end in ends:
        begin=max(0,end-150)
        if (begin,end) not in result:result.append((begin,end))
    # A deterministic shifted six-second window exposes both clipped edges.
    if frame_count>165:
        result.append((13,min(163,frame_count)))
    return list(dict.fromkeys(result))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    base=json.loads(args.base.read_text(encoding='utf8'))
    selected={r['id']:r for r in base['records']}
    timed={}
    with Path(base['source_manifest']).open(encoding='utf8') as f:
        for line in f:
            r=json.loads(line)
            if r['clip_id'] in selected:timed[r['clip_id']]=r['words']
    assert len(timed)==len(selected)
    codec=VietnamesePhones(Path(base['dependency']['path']))
    rows=[];excluded=Counter()
    for identifier,r in selected.items():
        assert words(' '.join(w['text'] for w in timed[identifier]))==r['words']
        for start,stop in window_spans(r['frames']):
            core=complete_word_core(timed[identifier],start,stop)
            if core is None:excluded['no_complete_words']+=1;continue
            chosen,left,right=core
            text=' '.join(w['text'] for w in chosen)
            phones=codec.encode(text);tonal=codec.encode(text,tones=True)
            if ctc_min_frames(tonal)>right-left:
                excluded['ctc_infeasible_core']+=1;continue
            rows.append(dict(r,id=f'{identifier}@{start}:{stop}',parent_id=identifier,
                text=text,words=words(text),phones=phones,tonal=tonal,
                window_start=start,window_stop=stop,loss_start=left,loss_stop=right,
                partial_left=any(w['start']<start/25<w['end'] for w in timed[identifier]),
                partial_right=any(w['start']<stop/25<w['end'] for w in timed[identifier])))
    assert not {w for r in rows if r['split']=='train' for w in r['words']} & set(base['lexical_holdout'])
    report={k:v for k,v in base.items() if k not in ('records','counts','excluded')}
    report.update(base_dataset_sha256=hashlib.sha256(args.base.read_bytes()).hexdigest(),
        window_policy='25 Hz, growing prefixes and maximum 150 frames, cuts not snapped to words',
        label_policy='CTC supervised only over fully contained timed words; partial edge phones are NOT fabricated as whole syllables. Encoder sees full cropped window with no frames beyond stop.',
        counts=dict(Counter(r['split'] for r in rows)),excluded=dict(excluded),records=rows)
    (args.output/'DATASET.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(counts=report['counts'],excluded=report['excluded'],
        partial_right=sum(r['partial_right'] for r in rows),partial_left=sum(r['partial_left'] for r in rows))),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');main()
