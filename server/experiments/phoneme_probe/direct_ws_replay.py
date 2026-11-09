"""Paired camera-paced direct-phoneme replay; the production model stays SO17."""
import argparse
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time
import cv2
import numpy as np
import torch
from app.services.native_engine import NativeAvsrEngine
from app.services.phoneme_direct import DirectPhonemeDecoder
from scripts.benchmark_models import settings
from .fixed_windows import decode_candidates
from .fixed_ws_replay import replay


class DirectPair:
    names=('baseline','direct')

    def __init__(self,args):
        self.engine=NativeAvsrEngine(replace(settings(args.checkpoint,device='cuda',beam=3),precision='float32',nbest=3))
        self.engine.load()
        self.direct=DirectPhonemeDecoder(args.head,args.lexicon,args.checkpoint,'cuda',
            json.loads(args.config.read_text(encoding='utf8')))
        self.expected={r['id']:r for r in json.loads(args.cache.read_text(encoding='utf8'))['records']}
        self.direct_expected={r['id']:r for r in json.loads(args.scores.read_text(encoding='utf8'))}

    def decode(self,clip,index,event,jpegs):
        tick=time.perf_counter()
        frames=[cv2.cvtColor(cv2.imdecode(np.frombuffer(j,np.uint8),cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB) for j in jpegs]
        prepared=self.engine._preprocessor.prepare_frames(frames,source_fps=25,input_kind=clip['input_kind'])
        identifier=f"{clip['id']}/{index}"
        expected=self.expected[identifier]
        tensor_hash=hashlib.sha256(prepared.tensor.numpy().tobytes()).hexdigest()
        assert tensor_hash==expected['tensor_sha256'],identifier
        with torch.inference_mode():
            model=self.engine._model;x=prepared.tensor.to('cuda')
            encoded=model.encoder(model.proj_encoder(model.frontend(x[None])),None)[0][0]
            candidates=decode_candidates(self.engine,encoded)
        assert [c['text'] for c in candidates]==[c['text'] for c in expected['candidates']],identifier
        baseline_ms=(time.perf_counter()-tick)*1000
        direct,detail=self.direct.decode(encoded)
        assert [c['text'] for c in direct]==[c['text'] for c in self.direct_expected[identifier]['direct_candidates']],identifier
        best=direct[0] if direct else dict(text='',words=[])
        selected=dict(baseline=dict(candidate=candidates[0],extra_ms=0.,changed=False),
            direct=dict(candidate=best,extra_ms=detail['elapsed_ms'],changed=best['text']!=candidates[0]['text']))
        return dict(index=index,event=event,tensor_sha256=tensor_hash,baseline_ms=baseline_ms,selected=selected)


async def main(args):
    args.output.mkdir(parents=True,exist_ok=False)
    decoder=await asyncio.to_thread(DirectPair,args)
    report=dict(scope='Camera-paced loopback with exact cached image tensors and original window boundaries. Frozen endpoint release offsets are estimates from transport telemetry; this is not an automatic endpoint or phone-visible latency test.',clips=[])
    for clip in json.loads(args.manifest.read_text(encoding='utf8'))['clips']:
        assert hashlib.sha256(Path(clip['video']).read_bytes()).hexdigest()==clip['sha256']
        result=await replay(clip,decoder)
        report['clips'].append(result)
        (args.output/'RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in result.items() if k not in ('events','client_events','outcomes')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('checkpoint','head','lexicon','config','manifest','cache','scores','output'):
        p.add_argument('--'+name,type=Path,required=True)
    asyncio.run(main(p.parse_args()))
