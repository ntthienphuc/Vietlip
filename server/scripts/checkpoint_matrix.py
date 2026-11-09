"""Fixed development comparison across all six available native checkpoints.

Preprocessing is cached identically across models; benchmark only decode RTF here.
Odd-ranked newly restored clips are reserved for the subsequent frozen audit.
"""
from __future__ import annotations
import argparse,csv,gc,json,statistics,time,sys
from pathlib import Path
import torch
from benchmark_models import settings,errors,normalized_words
from app.services.native_engine import NativeAvsrEngine

sys.stdout.reconfigure(encoding='utf8')
root=Path(__file__).resolve().parents[2]
out=root/'artifacts/optimization_v2'
out.mkdir(exist_ok=True)
models=Path(r'E:/Project/Lip/Unified_PR_2026-11-02/Public_Release_Preparation_20261103/Paired_Neural_Kit_v1/package/Neural_Inputs_v1/models')
parser=argparse.ArgumentParser()
parser.add_argument('--beam',type=int,default=3)
parser.add_argument('--runs',nargs='*',default=['SO_seed17','SO_seed29','SO_seed43','WW_seed17','WW_seed29','WW_seed43'])
args=parser.parse_args()
selection=json.loads((out/'DATA_SELECTION.json').read_text())
sources=[(out/'long_samples'/Path(r['path']).name,'new_development','mouth_roi') for r in selection['clips'][::2]]
sources += [(p,'previous_development','mouth_roi') for p in sorted((root/'artifacts/validation/samples').glob('*.mp4'))]
sources += [(p,'phone_development','raw_face') for p in sorted((root/'artifacts/validation/phone_samples').glob('*.mp4'))]
engine=NativeAvsrEngine(settings(models/args.runs[0]/'model.pt',beam=args.beam))
engine.load()
prepared=[]
for p,split,kind in sources:
    with p.with_suffix('.csv').open(encoding='utf-8-sig') as f:
        ref=' '.join(r['Word'].strip() for r in csv.DictReader(f))
    tick=time.perf_counter(); data=engine._preprocessor.prepare(p,kind)
    prepared.append((p,split,ref,data,time.perf_counter()-tick))
    print('prepared',p.name,data.num_frames,flush=True)
summaries=[]
for run in args.runs:
    checkpoint=models/run/'model.pt'
    payload=torch.load(checkpoint,map_location='cpu',mmap=True,weights_only=True)
    engine._model.load_state_dict(payload['model'],strict=True)
    del payload; gc.collect()
    records=[]
    for p,split,ref,data,prep_time in prepared:
        torch.cuda.synchronize(); tick=time.perf_counter()
        result=engine._decode_native(data,realtime=True)
        torch.cuda.synchronize(); elapsed=time.perf_counter()-tick
        r={'file':p.name,'split':split,'reference':ref,'hypothesis':result.transcript,
            'errors':errors(normalized_words(ref),normalized_words(result.transcript)),
            'words':len(normalized_words(ref)),'decode_seconds':elapsed,
            'preprocess_seconds':prep_time,'source_seconds':data.num_frames/25,
            'greedy_hypothesis':result.diagnostics['greedy_transcript'],
            'greedy_errors':errors(normalized_words(ref),normalized_words(result.diagnostics['greedy_transcript']))}
        records.append(r)
        print(run,p.name,f"{r['errors']}/{r['words']}",round(elapsed,2),flush=True)
        (out/f'{run}_beam{args.beam}.json').write_text(json.dumps({'run':run,'beam':args.beam,'records':records},ensure_ascii=False,indent=2),encoding='utf8')
    summary={'run':run,'beam':args.beam}
    for split in sorted(set(r['split'] for r in records)):
        rows=[r for r in records if r['split']==split]
        summary[split]={'errors':sum(r['errors'] for r in rows),'words':sum(r['words'] for r in rows),
            'wer':sum(r['errors'] for r in rows)/sum(r['words'] for r in rows),
            'median_decode_seconds':statistics.median(r['decode_seconds'] for r in rows),
            'decode_rtf':sum(r['decode_seconds'] for r in rows)/sum(r['source_seconds'] for r in rows)}
    summaries.append(summary)
    (out/f'MATRIX_beam{args.beam}.json').write_text(json.dumps(summaries,indent=2),encoding='utf8')
    print('SUMMARY',json.dumps(summary),flush=True)
