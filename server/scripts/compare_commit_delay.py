"""Compare caption ownership on identical saved model outputs (no inference)."""
import argparse,json
from pathlib import Path
from benchmark_models import errors,normalized_words
from app.services.streaming_buffer import WordTimeline

p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--output',required=True)
args=p.parse_args()
data=json.loads(Path(args.input).read_text(encoding='utf8'))
rows=[]
for delay in (0.6,1.0,1.5,2.0,2.5):
    timeline=WordTimeline()
    last=None
    for event in data['events']:
        if not event.get('window_words'):continue
        last=timeline.update(event['window_words'],event['window_start'],event['window_end'],
            final=event['type']=='session_final',right_context=delay)
    hyp=last['transcript'] if last else ''
    ref=normalized_words(data['reference'])
    rows.append(dict(commit_delay=delay,errors=errors(ref,normalized_words(hyp)),
        words=len(ref),wer=errors(ref,normalized_words(hyp))/len(ref),hypothesis=hyp))
Path(args.output).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps([{k:v for k,v in row.items() if k!='hypothesis'} for row in rows],indent=2))
