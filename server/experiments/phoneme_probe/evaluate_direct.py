"""Select direct phone-to-text decoding on dev, then freeze and test identical windows."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import statistics
import time
import torch
from app.services.phoneme_direct import PronunciationDecoder
from app.services.caption_stability import AgreementTimeline
from .codec import words,edit_distance
from .model import PhonemeHead


def error_summary(rows):
    e=sum(r['errors'] for r in rows);n=sum(r['reference_words'] for r in rows)
    ce=sum(r['char_errors'] for r in rows);cn=sum(r['reference_chars'] for r in rows)
    return dict(windows=len(rows),errors=e,words=n,wer=e/max(1,n),char_errors=ce,chars=cn,
        cer=ce/max(1,cn),unavailable=sum(not r['candidates'] for r in rows),
        outside_so17_top3=sum(r['outside_so17_top3'] for r in rows),
        median_decode_ms=statistics.median(r['decode_ms'] for r in rows))


def predict(row,decoder,logp):
    tick=time.perf_counter();candidates=decoder.decode(logp)
    elapsed=(time.perf_counter()-tick)*1000
    best=candidates[0] if candidates else dict(text='',words=[])
    result=dict(id=row['id'],candidates=candidates,decode_ms=elapsed,
        outside_so17_top3=bool(candidates) and best['text'] not in [c['text'] for c in row['candidates']])
    if 'reference' in row:
        ref=words(row['reference'])
        hyp=words(' '.join(w['text'] for w in best['words']
            if row['loss_start']/25<=(w['start']+w['end'])/2<row['loss_stop']/25))
        result.update(split=row['split'],reference=row['reference'],core_text=' '.join(hyp),
            errors=edit_distance(ref,hyp),reference_words=len(ref),
            char_errors=edit_distance(''.join(ref),''.join(hyp)),reference_chars=len(''.join(ref)))
    else:
        result.update(clip=row['clip'],event=row['event'])
    return result


def captions(rows,manifest,*,baseline=False):
    output={}
    for clip in manifest['clips']:
        timeline=AgreementTimeline();unavailable=0;history=[]
        for row in rows:
            if row['clip']!=clip['id']:continue
            candidates=row['candidates'];event=row['event']
            if not candidates or not candidates[0]['words']:
                unavailable+=1;timeline.discard_pending();continue
            update=timeline.update(candidates[0]['words'],event['window_start'],event['window_end'],
                final=event['type']=='segment_final',right_context=1.)
            history.append(dict(id=row['id'],**update))
        ref,hyp=words(clip['reference']),words(timeline.text)
        output[clip['id']]=dict(errors=edit_distance(ref,hyp),words=len(ref),wer=edit_distance(ref,hyp)/len(ref),
            char_errors=edit_distance(''.join(ref),''.join(hyp)),chars=len(''.join(ref)),
            cer=edit_distance(''.join(ref),''.join(hyp))/len(''.join(ref)),
            hypothesis=timeline.text,unavailable_windows=unavailable,history=history)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('head','lexicon','corpus-cache','live-cache','output'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2)
    saved=torch.load(args.head,weights_only=True,map_location='cpu')
    head=PhonemeHead(**saved['config']).eval()
    head.load_state_dict(saved['state_dict'])
    resource=json.loads(args.lexicon.read_text(encoding='utf8'))
    corpus=json.loads((args.corpus_cache/'CACHE.json').read_text(encoding='utf8'))
    live=json.loads((args.live_cache/'CACHE.json').read_text(encoding='utf8'))
    posteriors={}
    with torch.inference_mode():
        for cache,folder in [(corpus,args.corpus_cache),(live,args.live_cache)]:
            assert cache['checkpoint_sha256']==saved['feature_identity']['checkpoint_sha256']
            for row in cache['records']:
                path=Path(row['feature_file'])
                if not path.is_absolute():path=folder/path
                encoded=torch.load(path,weights_only=True,map_location='cpu')['encoded']
                assert hashlib.sha256(encoded.numpy().tobytes()).hexdigest()==row['encoded_sha256']
                values=head(encoded[None])
                posteriors[row['id']]={name:values[i][0].log_softmax(-1).numpy()
                    for i,name in enumerate(('segmental','tonal'))}
    dev=[r for r in corpus['records'] if r['split']=='dev']
    sweep=[]
    for branch,lm,bonus in itertools.product(('segmental','tonal'),(.2,.5),(0.,2.,4.)):
        config=dict(branch=branch,lm_weight=lm,word_score=bonus,beam=48,token_beam=12)
        decoder=PronunciationDecoder(resource,saved[branch+'_tokens'],**config)
        rows=[predict(r,decoder,posteriors[r['id']][branch]) for r in dev]
        result=dict(config=config,**error_summary(rows));sweep.append(result)
        (args.output/'DEV_SWEEP.json').write_text(json.dumps(sweep,indent=2),encoding='utf8')
        print(json.dumps(result),flush=True)
    selected=min(sweep,key=lambda r:(r['errors'],r['char_errors'],r['median_decode_ms']))['config']
    (args.output/'CONFIG.json').write_text(json.dumps(selected,indent=2),encoding='utf8')
    decoder=PronunciationDecoder(resource,saved[selected['branch']+'_tokens'],**selected)
    results={}
    for name,cache in [('corpus',corpus),('live',live)]:
        rows=[predict(r,decoder,posteriors[r['id']][selected['branch']]) for r in cache['records']]
        results[name]=rows
        (args.output/(name.upper()+'_ROWS.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    manifest=json.loads(Path(live['manifest']).read_text(encoding='utf8'))
    comparison={}
    for name,rows in [('baseline',live['records']),('direct',results['live'])]:
        values=captions(rows,manifest)
        (args.output/(name.upper()+'_CAPTIONS.json')).write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding='utf8')
        comparison[name]={k:{a:b for a,b in v.items() if a!='history'} for k,v in values.items()}
    report=dict(selected_config=selected,selection='Lowest dev core WER, then CER; test/live never select config.',
        corpus={split:error_summary([r for r in results['corpus'] if r['split']==split])
            for split in ('dev','test','lexical_test')},live=comparison,
        head_sha256=hashlib.sha256(args.head.read_bytes()).hexdigest(),
        lexicon_sha256=hashlib.sha256(args.lexicon.read_bytes()).hexdigest(),
        manifest_sha256=live['manifest_sha256'],scope='Same cached visual states and window timestamps. Direct decoding receives no SO17 candidates or reference text. Post-hoc scoring uses references.')
    (args.output/'RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(selected=selected,corpus=report['corpus'],live={k:{c:(v['errors'],v['words']) for c,v in vs.items()} for k,vs in comparison.items()})),flush=True)


if __name__=='__main__':main()
