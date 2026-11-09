"""Same encoded features, beam size and model; paired original vs full KV cache."""
import csv,json,time,statistics,argparse
from pathlib import Path
import torch
from benchmark_models import settings
from app.services.native_engine import NativeAvsrEngine
from app.services.decoder_cache import cached_cross_attention

root=Path(__file__).resolve().parents[2]
out=root/'artifacts/optimization_v2'
engine=NativeAvsrEngine(settings(root/'server/models/SO_seed17.pt',beam=3))
engine.load()
parser=argparse.ArgumentParser()
parser.add_argument('--cpu-ctc',action='store_true')
args=parser.parse_args()
from espnet.nets.batch_beam_search import BatchBeamSearch
from app.services.incremental_decoder import IncrementalDecoderScorer
from app.services.cpu_ctc_prefix import CpuCTCPrefixScorer
model=engine._model
fast=IncrementalDecoderScorer(model.decoder)
searches={}
for mode in ('original','incremental'):
    scorers=model.scorers()
    if mode=='incremental':scorers['decoder']=fast
    if mode=='incremental' and args.cpu_ctc:scorers['ctc']=CpuCTCPrefixScorer(model.ctc,model.eos)
    searches[mode]=BatchBeamSearch(beam_size=3,vocab_size=model.odim,
        weights={'decoder':.9,'ctc':.1},scorers=scorers,sos=model.sos,eos=model.eos,
        token_list=engine.tokens,pre_beam_ratio=1.5,pre_beam_score_key='decoder')
selection=json.loads((out/'DATA_SELECTION.json').read_text())
sources=[(out/'long_samples'/Path(r['path']).name,'mouth_roi') for r in selection['clips']]
sources += [(p,'raw_face') for p in sorted((root/'artifacts/validation/phone_samples').glob('*.mp4'))]
records=[]
with torch.inference_mode():
    for path,kind in sources:
        prepared=engine._preprocessor.prepare(path,kind)
        tensor=prepared.tensor.to(engine.device_label)
        torch.cuda.synchronize();tick=time.perf_counter()
        encoded=model.encoder(model.proj_encoder(model.frontend(tensor[None])),None)[0][0]
        torch.cuda.synchronize()
        row={'file':path.name,'encode_seconds':time.perf_counter()-tick}
        for mode,search in searches.items():
            torch.cuda.synchronize();tick=time.perf_counter()
            with cached_cross_attention(model.decoder,mode=='original'): hyps=search(encoded)
            torch.cuda.synchronize()
            row[mode]={'seconds':time.perf_counter()-tick,
                'texts':[engine._text(h.yseq[1:]) for h in hyps[:3]]}
        row['top1_equal']=row['original']['texts'][0]==row['incremental']['texts'][0]
        row['nbest_equal']=row['original']['texts']==row['incremental']['texts']
        records.append(row)
        print(path.name,row['nbest_equal'],round(row['original']['seconds'],2),
            round(row['incremental']['seconds'],2),flush=True)
        target='CPU_CTC_PARITY.json' if args.cpu_ctc else 'INCREMENTAL_PARITY.json'
        (out/target).write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
