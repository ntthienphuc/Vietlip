"""Frozen SO17 baseline vs development-selected WW29/CTC=.5; save N-best for LLM audit."""
import csv,json,time,gc,sys
from pathlib import Path
from dataclasses import replace
import torch
from benchmark_models import settings,errors,normalized_words
from app.services.native_engine import NativeAvsrEngine

root=Path(__file__).resolve().parents[2]
out=root/'artifacts/optimization_v2'
models=Path(r'E:/Project/Lip/Unified_PR_2026-11-02/Public_Release_Preparation_20261103/Paired_Neural_Kit_v1/package/Neural_Inputs_v1/models')
selection=json.loads((out/'DATA_SELECTION.json').read_text())
for run,ctc in [('SO_seed17',.1),('WW_seed29',.5)]:
    engine=NativeAvsrEngine(replace(settings(models/run/'model.pt',beam=3),ctc_weight=ctc))
    engine.load()
    records=[]
    for i,r in enumerate(selection['clips']):
        # Baseline is needed on the untouched audit half only.
        if run=='SO_seed17' and i%2==0: continue
        path=out/'long_samples'/Path(r['path']).name
        with path.with_suffix('.csv').open(encoding='utf-8-sig') as f:
            reference=' '.join(w['Word'].strip() for w in csv.DictReader(f))
        prepared=engine._preprocessor.prepare(path,'mouth_roi')
        tick=time.perf_counter();result=engine._decode_native(prepared,realtime=True)
        row=dict(file=path.name,split='development' if i%2==0 else 'reserved_audit',
            reference=reference,hypothesis=result.transcript,alternatives=result.alternatives,
            errors=errors(normalized_words(reference),normalized_words(result.transcript)),
            words=len(normalized_words(reference)),seconds=time.perf_counter()-tick)
        records.append(row)
        print(run,path.name,row['errors'],round(row['seconds'],2),flush=True)
        (out/f'{run}_frozen_ctc{ctc}.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
    del engine;gc.collect();torch.cuda.empty_cache()
