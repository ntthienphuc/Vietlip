"""Timestamp boundary ablation on saved outputs. No access to references until scoring."""
import json,argparse
from pathlib import Path
from benchmark_models import normalized_words,errors

def stitch(events, policy, delay, anchor):
    committed=[];frontier=-1;pending=[]
    for event in events:
        if not event.get('window_words'):continue
        start,end=event['window_start'],event['window_end']
        absolute=[dict(w,start=w['start']+start,end=w['end']+start) for w in event['window_words']]
        threshold=frontier+.02
        if committed:
            last=committed[-1]
            threshold=(last['end'] if policy.startswith('end') else frontier)+float(policy.split(':')[1])
        remaining=[w for w in absolute if (w['start']+w['end'])/2>threshold+1e-6]
        if committed and anchor:
            last=committed[-1]
            matches=[(abs((w['start']+w['end'])/2-frontier),i) for i,w in enumerate(absolute)
                     if w['text']==last['text'] and abs((w['start']+w['end'])/2-frontier)<.45]
            if matches:remaining=absolute[min(matches)[1]+1:]
        cutoff=end if event['type']=='session_final' else end-delay
        accepted=[]
        for w in remaining:
            if w['end']>cutoff+1e-6:break
            accepted.append(w)
        committed.extend(accepted)
        if accepted:frontier=(accepted[-1]['start']+accepted[-1]['end'])/2
        pending=remaining[len(accepted):]
    return ' '.join(w['text'] for w in committed+pending)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('files',nargs='+');p.add_argument('--output',required=True)
    args=p.parse_args();records=[]
    for filename in args.files:
        data=json.loads(Path(filename).read_text(encoding='utf8'));ref=normalized_words(data['reference'])
        for policy in ('mid:0.02','mid:0.08','mid:0.12','end:-0.04','end:0.0','end:0.04'):
            for delay in (1,1.5,2):
                for anchor in (True,False):
                    text=stitch(data['events'],policy,delay,anchor)
                    records.append(dict(file=Path(filename).name,policy=policy,delay=delay,anchor=anchor,
                        errors=errors(ref,normalized_words(text)),words=len(ref)))
    Path(args.output).write_text(json.dumps(records,indent=2))
    for filename in args.files:
        rows=sorted([r for r in records if r['file']==Path(filename).name],key=lambda r:r['errors'])
        print(json.dumps(rows[:5],indent=2))
