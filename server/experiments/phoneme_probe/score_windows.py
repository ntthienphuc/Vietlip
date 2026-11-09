"""Paired old/new-head scoring on exactly the same cached candidate windows."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import torch
from app.services.caption_stability import AgreementTimeline
from .codec import VietnamesePhones,UnsupportedSyllable,ctc_min_frames,words,edit_distance
from .model import PhonemeHead,greedy,phone_error
from .evaluate import rerank


def score_one(head,payload,x,candidates,codec):
    token_ids={s:i for i,s in enumerate(payload['segmental_tokens'])}
    loss_fn=torch.nn.CTCLoss(reduction='sum',zero_infinity=False)
    with torch.inference_mode():
        logits,_=head(x[None])
        logp=logits[0].log_softmax(-1)
        scores=[]
        for candidate in candidates:
            try:
                target=codec.encode(candidate['text'])
                ids=[token_ids[p] for p in target]
                if not ids or ctc_min_frames(ids)>len(x):
                    scores.append(None);continue
            except (UnsupportedSyllable,KeyError):
                scores.append(None);continue
            loss=loss_fn(logp[:,None],torch.tensor(ids,device=x.device),
                torch.tensor([len(x)]),torch.tensor([len(ids)]))
            scores.append(-float(loss) if torch.isfinite(loss) else None)
    return scores,logits[0]


def core_summary(rows,head,weight,include_phone=True):
    error=count=pe=pn=changed=char_errors=chars=oracle=0
    for r in rows:
        index=rerank(r['candidates'],r['scores'][head],weight)
        error+=r['candidates'][index]['core_errors'];count+=len(words(r['reference']))
        reference=''.join(words(r['reference']))
        prediction=''.join(words(r['candidates'][index]['core_text']))
        char_errors+=edit_distance(reference,prediction);chars+=len(reference)
        oracle+=min(c['core_errors'] for c in r['candidates'])
        pe+=r['per'][head][0];pn+=r['per'][head][1];changed+=index!=0
    return dict(windows=len(rows),errors=error,words=count,wer=error/max(1,count),
        char_errors=char_errors,chars=chars,cer=char_errors/max(1,chars),
        phone_errors=pe if include_phone else None,phones=pn if include_phone else None,
        per=pe/max(1,pn) if include_phone else None,changed=changed,top3_oracle_errors=oracle,
        unsupported_windows=sum(any(s is None for s in r['scores'][head]) for r in rows))


def caption_summary(rows,manifest,head,weight):
    outcomes={}
    for clip in manifest['clips']:
        timeline=AgreementTimeline();history=[];changes=unavailable=0
        for r in rows:
            if r['clip']!=clip['id']:continue
            index=0 if head is None else rerank(r['candidates'],r['scores'][head],weight)
            changes+=index!=0
            candidate=r['candidates'][index];e=r['event']
            if not candidate['words']:
                unavailable+=1;timeline.discard_pending();continue
            update=timeline.update(candidate['words'],e['window_start'],e['window_end'],
                final=e['type']=='segment_final',right_context=1.)
            history.append(dict(window=r['id'],type=e['type'],start=e['window_start'],end=e['window_end'],
                selected=index,window_transcript=candidate['text'],**update))
        ref,hyp=words(clip['reference']),words(timeline.text)
        outcomes[clip['id']]=dict(errors=edit_distance(ref,hyp),words=len(ref),
            wer=edit_distance(ref,hyp)/len(ref),char_errors=edit_distance(''.join(ref),''.join(hyp)),
            chars=len(''.join(ref)),hypothesis=timeline.text,changed_windows=changes,
            cer=edit_distance(''.join(ref),''.join(hyp))/len(''.join(ref)),
            unavailable_windows=unavailable,history=history)
    return outcomes


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('old-head','new-head','corpus-cache','live-cache','vphon','output'):
        p.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(4)
    codec=VietnamesePhones(args.vphon)
    models={}
    for name,path in [('v1',args.old_head),('window',args.new_head)]:
        saved=torch.load(path,weights_only=True,map_location='cpu')
        model=PhonemeHead(**saved['config']).to('cuda').eval()
        model.load_state_dict(saved['state_dict'])
        models[name]=(model,saved)
    caches={}
    for kind,folder in [('corpus',args.corpus_cache),('live',args.live_cache)]:
        cache=json.loads((folder/'CACHE.json').read_text(encoding='utf8'))
        for _,saved in models.values():
            assert saved['feature_identity']['checkpoint_sha256']==cache['checkpoint_sha256']
        for row in cache['records']:
            feature=Path(row['feature_file'])
            if not feature.is_absolute():feature=folder/feature
            x=torch.load(feature,weights_only=True,map_location='cpu')['encoded']
            assert hashlib.sha256(x.numpy().tobytes()).hexdigest()==row['encoded_sha256']
            x=x.to('cuda');row['scores']={};row['per']={}
            for name,(model,saved) in models.items():
                scores,logits=score_one(model,saved,x,row['candidates'],codec)
                row['scores'][name]=scores
                if kind=='corpus':
                    left,right=row['loss_start'],row['loss_stop']
                    hyp=greedy(logits[left:right],right-left,saved['segmental_tokens'])
                    row['per'][name]=phone_error(row['phones'],hyp)
        caches[kind]=cache
        (args.output/f'{kind.upper()}_SCORES.json').write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding='utf8')
    corpus=caches['corpus']['records'];dev=[r for r in corpus if r['split']=='dev']
    weights=[0,.1,.3,.6,1.]
    selected={};sweeps={}
    for name in models:
        sweeps[name]=[dict(weight=w,**core_summary(dev,name,w)) for w in weights]
        selected[name]=min(sweeps[name],key=lambda s:(s['errors'],s['weight']))['weight']
    report=dict(selected_weights=selected,dev_sweep=sweeps,corpus={},live={},
        scope='Paired identical-window replay using original application caption agreement. Historical camera schedules, not fresh physical-camera latency.',
        selection='Each head weight selected on dev window core WER only. Phone and long replay do not select weights.')
    for split in ('dev','test','lexical_test'):
        rows=[r for r in corpus if r['split']==split]
        report['corpus'][split]=dict(baseline=core_summary(rows,'v1',0,include_phone=False),
            v1=core_summary(rows,'v1',selected['v1']),window=core_summary(rows,'window',selected['window']))
    manifest=json.loads(Path(caches['live']['manifest']).read_text(encoding='utf8'))
    for name,head,weight in [('baseline',None,0),('v1_fixed', 'v1',1.),
                             ('v1_dev','v1',selected['v1']),('window','window',selected['window']),
                             ('window_fixed','window',1.)]:
        full=caption_summary(caches['live']['records'],manifest,head,weight)
        (args.output/f'{name}_CAPTIONS.json').write_text(json.dumps(full,ensure_ascii=False,indent=2),encoding='utf8')
        report['live'][name]={k:{a:b for a,b in v.items() if a!='history'} for k,v in full.items()}
    report['head_hashes']={name:hashlib.sha256(path.read_bytes()).hexdigest()
        for name,path in [('v1',args.old_head),('window',args.new_head)]}
    (args.output/'RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(selected_weights=selected,corpus=report['corpus'],
        live={k:{c:(s['errors'],s['words']) for c,s in v.items()} for k,v in report['live'].items()})),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');main()
