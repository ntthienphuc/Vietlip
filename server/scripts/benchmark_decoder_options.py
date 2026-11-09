"""Paired, warm decoding tests on identical prepared inputs and checkpoints."""
import os,time,json,sys,csv,statistics,argparse
from pathlib import Path
from dataclasses import replace
import torch
from benchmark_models import settings,normalized_words,errors
from app.services.native_engine import NativeAvsrEngine
from app.services.decoder_cache import cached_cross_attention

root=Path(__file__).resolve().parents[2];out=root/'artifacts/optimization_v2'
p=argparse.ArgumentParser();p.add_argument('--run',default='WW_seed29');args=p.parse_args()
models=Path(r'E:/Project/Lip/Unified_PR_2026-11-02/Public_Release_Preparation_20261103/Paired_Neural_Kit_v1/package/Neural_Inputs_v1/models')
engine=NativeAvsrEngine(settings(models/args.run/'model.pt',beam=10));engine.load()
from espnet.nets.batch_beam_search import BatchBeamSearch
selection=json.loads((out/'DATA_SELECTION.json').read_text())
sources=[(out/'long_samples'/Path(r['path']).name,'mouth_roi') for r in selection['clips'][::2]]
sources += [(p,'raw_face') for p in sorted((root/'artifacts/validation/phone_samples').glob('*.mp4'))]
records=[]
for path,kind in sources:
    with path.with_suffix('.csv').open(encoding='utf-8-sig') as f:
        ref=' '.join(r['Word'].strip() for r in csv.DictReader(f))
    prepared=engine._preprocessor.prepare(path,kind)
    model=engine._model
    with torch.inference_mode():
        tensor=prepared.tensor.to(engine.device_label)
        torch.cuda.synchronize();tick=time.perf_counter()
        features=model.frontend(tensor.unsqueeze(0));torch.cuda.synchronize();front=time.perf_counter()-tick
        tick=time.perf_counter();encoded=model.encoder(model.proj_encoder(features),None)[0][0];torch.cuda.synchronize();enc=time.perf_counter()-tick
        for beam,ctc,cache in [(3,.1,False),(3,.1,True),(1,.1,True),(5,.1,True),(3,.3,True),(3,.5,True)]:
            search=BatchBeamSearch(beam_size=beam,vocab_size=model.odim,
                weights={'decoder':1-ctc,'ctc':ctc},scorers=model.scorers(),sos=model.sos,eos=model.eos,
                token_list=engine.tokens,pre_beam_ratio=1.5,pre_beam_score_key='decoder')
            torch.cuda.synchronize();tick=time.perf_counter()
            with cached_cross_attention(model.decoder,cache):hyps=search(encoded)
            torch.cuda.synchronize();elapsed=time.perf_counter()-tick
            hyp=engine._text(hyps[0].yseq[1:])
            r=dict(file=path.name,kind=kind,beam=beam,ctc=ctc,cache=cache,reference=ref,hypothesis=hyp,
                errors=errors(normalized_words(ref),normalized_words(hyp)),words=len(normalized_words(ref)),
                frontend_seconds=front,encoder_seconds=enc,search_seconds=elapsed)
            records.append(r)
            print(path.name,beam,ctc,cache,r['errors'],round(front+enc+elapsed,3),flush=True)
            (out/f'{args.run}_decoder_options.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
print('DONE',flush=True)
