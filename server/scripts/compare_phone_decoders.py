"""Reuse fixed prepared inputs to compare search settings, excluding crop latency."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import time
import torch
from benchmark_models import settings, normalized_words, errors
from app.services.native_engine import NativeAvsrEngine
from app.services.video_preprocessor import PreparedVideo


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--prepared',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model',default='SO_seed17')
    args=p.parse_args()
    if args.output.exists():raise ValueError('Preserve previous results; use a new output')
    root=Path(__file__).resolve().parents[2]
    engine=NativeAvsrEngine(settings(root/'server/models'/f'{args.model}.pt',device='cuda',beam=10))
    engine.load()
    from espnet.nets.batch_beam_search import BatchBeamSearch
    from app.services.incremental_decoder import IncrementalDecoderScorer
    from app.services.cpu_ctc_prefix import CpuCTCPrefixScorer
    manifest=json.loads(args.manifest.read_text(encoding='utf8'));rows=[]
    for beam,weight in [(3,.1),(3,.3),(3,.5),(5,.3),(5,.5),(10,.3)]:
        engine.settings=replace(engine.settings,realtime_beam_size=beam,ctc_weight=weight,nbest=beam)
        model=engine._model
        scorers=model.scorers()
        scorers['decoder']=IncrementalDecoderScorer(model.decoder)
        scorers['ctc']=CpuCTCPrefixScorer(model.ctc,model.eos)
        engine._beams[beam]=BatchBeamSearch(beam_size=beam,vocab_size=model.odim,
            weights={'decoder':1-weight,'ctc':weight},scorers=scorers,sos=model.sos,eos=model.eos,
            token_list=engine.tokens,pre_beam_ratio=1.5,pre_beam_score_key='decoder')
        for item in manifest['segments']:
            tensor=torch.load(args.prepared/f"prepared-{item['id']}.pt",weights_only=True)
            data=PreparedVideo(tensor,len(tensor),{})
            tick=time.perf_counter();res=engine._decode_native(data,realtime=True)
            row=dict(id=item['id'],beam=beam,ctc=weight,reference=item['reference'],
                hypothesis=res.transcript,errors=errors(normalized_words(item['reference']),
                    normalized_words(res.transcript)),seconds=time.perf_counter()-tick,
                alternatives=res.alternatives)
            rows.append(row)
            print(beam,weight,item['id'],row['errors'],round(row['seconds'],3),res.transcript,flush=True)
            args.output.write_text(json.dumps(dict(model=args.model,prepared=str(args.prepared.resolve()),
                reference_status=manifest['reference_status'],scope=manifest['boundary_scope'],records=rows),
                ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':main()
