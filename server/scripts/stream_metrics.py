"""Replay timing summary, including late words; no latency claim for missed words."""
import json,statistics,argparse
from pathlib import Path
from benchmark_models import normalized_words

def percentile(values,q):
    if not values:return None
    values=sorted(values)
    return values[min(len(values)-1,round((len(values)-1)*q))]

def summarize(path):
    data=json.loads(path.read_text(encoding='utf8'))
    events=[e for e in data['events'] if e['type'] in {'partial','session_final'}]
    decode=[e['elapsed_ms']/1000 for e in events if e.get('elapsed_ms')]
    lag=[e['wall_seconds']-e['source_seconds'] for e in events if 'source_seconds' in e]
    # First update whose model window includes each segment's speech end.
    # This measures caption availability, not whether that caption is correct.
    ends=[s.get('speech_end',s.get('end')) for s in data['segments']]
    opportunities=[]
    for end in ends:
        candidates=[e for e in events if e.get('source_seconds',-1)>=end-.05 and e.get('transcript')]
        if candidates:opportunities.append(candidates[0]['wall_seconds']-end)
    return {k:data[k] for k in ('source_seconds','sent_frames','transport_dropped_frames','errors','reference_words','wer','finalization_seconds')} | {
        'file':path.name,'decode_median_seconds':statistics.median(decode) if decode else None,
        'decode_p95_seconds':percentile(decode,.95),'source_to_display_median_seconds':statistics.median(lag) if lag else None,
        'source_to_display_p95_seconds':percentile(lag,.95),
        'endpoint_update_median_seconds':statistics.median(opportunities) if opportunities else None,
        'endpoint_update_p95_seconds':percentile(opportunities,.95),
        'endpoint_update_within_3_seconds':sum(v<=3 for v in opportunities),
        'endpoints_measured':len(opportunities),
        'maximum_buffered_frames':max((e.get('buffered_frames',0) for e in events),default=0),
        'scope':'Caption availability after segment end; incorrect/missing words still count in WER. Not correct-word latency.',
    }

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('files',nargs='+');p.add_argument('--output')
    args=p.parse_args();rows=[summarize(Path(f)) for f in args.files]
    result=json.dumps(rows,indent=2)
    if args.output:Path(args.output).write_text(result,encoding='utf8')
    print(result)
