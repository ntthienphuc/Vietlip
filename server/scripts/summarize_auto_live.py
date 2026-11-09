"""Report endpoint timing against synthetic clip boundaries, not speech truth."""
import json
from pathlib import Path
import numpy as np
from benchmark_models import errors,normalized_words

ROOT=Path(__file__).resolve().parents[2]/'artifacts/live_v3'


def summarize(name):
    d=json.loads((ROOT/f'{name}.json').read_text(encoding='utf8'))
    events=d['events'];segments=d['segments']
    starts=[e for e in events if e['type']=='activity' and 'speech_start' in e]
    ends=[e for e in events if e['type']=='segment_final']
    matched=[]
    for segment in segments:
        candidates=[e for e in ends if segment['start']<=e['window_end']<=segment['pause_end']]
        matched.append(dict(file=segment['file'],clip_end=segment['speech_end'],
            endpoints=len(candidates),latency=None if not candidates else candidates[-1]['wall_seconds']-segment['speech_end']))
    latencies=[r['latency'] for r in matched if r['latency'] is not None]
    numbers=lambda values:dict(median=float(np.median(values)),p95=float(np.percentile(values,95)),maximum=max(values)) if values else None
    ref=''.join(normalized_words(d['reference']));hyp=''.join(normalized_words(d['hypothesis']))
    return dict(source_seconds=d['source_seconds'],clips=len(segments),sent_frames=d['sent_frames'],
        transport_dropped=d['transport_dropped_frames'],wer=d['wer'],word_errors=d['errors'],reference_words=d['reference_words'],
        cer=errors(ref,hyp)/max(1,len(ref)),char_errors=errors(ref,hyp),reference_chars=len(ref),
        detected_starts=len(starts),automatic_finals=len(ends),matched_clip_ends=sum(r['endpoints']>0 for r in matched),
        unavailable_windows=events[-1]['evidence']['unavailable_windows'],
        endpoint_after_clip_end_seconds=numbers(latencies),
        processing_ms=numbers([e['elapsed_ms'] for e in events if e.get('elapsed_ms')]),
        activity_processing_ms=numbers([e['activity_processing_ms'] for e in events if e.get('activity_processing_ms')]),
        finalization_after_stop_seconds=d['finalization_seconds'],
        scope='Paced replay, 2s frozen padding at both sides. Clip boundaries are NOT human speech boundaries. Matching endpoints is not VAD precision/recall; transcript presence is not accuracy.',
        boundaries=matched)


if __name__=='__main__':
    report={name:summarize(name) for name in ['PHONE_AUTO_IDLE','ROI_AUTO24_IDLE'] if (ROOT/f'{name}.json').exists()}
    (ROOT/'AUTO_LIVE_METRICS.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({k:{key:v for key,v in row.items() if key!='boundaries'} for k,row in report.items()},indent=2))
