"""Freeze a visual-check gate on dev and compare exact cached windows/captions."""
import argparse
import json
from pathlib import Path
import statistics
from .codec import words,edit_distance
from .evaluate_direct import captions


def pick(row,scored,margin):
    original=row['candidates'][0]
    baseline=scored['candidates'][0]
    proposals=[c for c in scored['candidates'] if c['source']=='direct_phoneme_ctc' and c['words']]
    if proposals:
        best=max(proposals,key=lambda c:c['native_score'])
        if best['native_score']>baseline['native_score']+margin:
            return best
    return original


def corpus_summary(rows):
    errors=chars=ce=count=changed=0
    for row in rows:
        candidate=row['candidates'][0]
        reference=words(row['reference'])
        prediction=words(' '.join(w['text'] for w in candidate['words'] if
            row['loss_start']/25 <= (w['start']+w['end'])/2 < row['loss_stop']/25))
        errors+=edit_distance(reference,prediction);count+=len(reference)
        ce+=edit_distance(''.join(reference),''.join(prediction));chars+=len(''.join(reference))
        changed+=row.get('changed',False)
    return dict(windows=len(rows),errors=errors,words=count,wer=errors/count,
        char_errors=ce,chars=chars,cer=ce/chars,changed=changed)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scores',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    scores=json.loads(args.scores.read_text(encoding='utf8'))
    lookup={r['id']:r for r in scores}
    caches=[json.loads((Path(path)/'CACHE.json').read_text(encoding='utf8')) for path in dict.fromkeys(r['cache'] for r in scores)]
    corpus=next(c for c in caches if c['kind']=='corpus')
    def selected(row,margin):
        candidate=pick(row,lookup[row['id']],margin)
        return dict(row,candidates=[candidate],changed=candidate['text']!=row['candidates'][0]['text'])
    dev=[r for r in corpus['records'] if r['split']=='dev']
    sweep=[dict(margin=margin,**corpus_summary([selected(r,margin) for r in dev])) for margin in (0.,1.,2.,4.,8.,16.,1000000.)]
    best=min(sweep,key=lambda r:(r['errors'],r['char_errors'],r['changed']))
    margin=best['margin']
    report=dict(selection='Dev only; WER, CER, then fewer changes. Large margin includes unchanged baseline.',
        dev_sweep=sweep,selected_margin=margin,corpus={},live={},timing={
            'median_direct_ms':statistics.median(r['direct_ms'] for r in scores),
            'median_native_rescore_ms':statistics.median(r['rescore_ms'] for r in scores)})
    for name in ('baseline','direct','native_checked'):
        rows=[]
        for r in corpus['records']:
            if name=='native_checked':rows.append(selected(r,margin))
            elif name=='direct':rows.append(dict(r,candidates=lookup[r['id']]['direct_candidates']))
            else:rows.append(r)
        report['corpus'][name]={split:corpus_summary([r for r in rows if r['split']==split]) for split in ('dev','test','lexical_test')}
        outcomes={}
        for cache in caches:
            if cache['kind']!='live':continue
            manifest=json.loads(Path(cache['manifest']).read_text(encoding='utf8'))
            live=[]
            for r in cache['records']:
                if name=='native_checked':live.append(selected(r,margin))
                elif name=='direct':live.append(dict(r,candidates=lookup[r['id']]['direct_candidates']))
                else:live.append(r)
            outcomes.update(captions(live,manifest))
        report['live'][name]=outcomes
    report['promotion_eligible']=all(report['corpus']['native_checked'][s]['errors']<report['corpus']['baseline'][s]['errors'] for s in ('dev','test')) and sum(v['errors'] for v in report['live']['native_checked'].values())<sum(v['errors'] for v in report['live']['baseline'].values())
    (args.output/'RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='live'},ensure_ascii=True,indent=2))
    print(json.dumps({name:{clip:(r['errors'],r['words']) for clip,r in clips.items()} for name,clips in report['live'].items()}))


if __name__=='__main__':main()
