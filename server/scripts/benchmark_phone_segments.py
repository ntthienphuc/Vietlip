"""Fixed-input diagnostic checkpoint comparison on explicitly supplied phone slices.

Reference text is used only after visual decoding, never passed to the engine.
Audio-assisted slice boundaries are an oracle diagnostic, not streaming results.
"""
import argparse
from dataclasses import replace
import gc
import json
from pathlib import Path
import statistics
import time

import cv2
import torch

from benchmark_models import errors, normalized_words, settings
from app.services.native_engine import NativeAvsrEngine


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--models', nargs='+', default=['SO_seed17','SO_seed29','SO_seed43',
        'WW_seed17','WW_seed29','WW_seed43','VLR_pretrained'])
    p.add_argument('--beam', type=int, default=3)
    p.add_argument('--ctc', type=float, default=.1)
    p.add_argument('--mirror', action='store_true')
    p.add_argument('--width', type=int, default=360)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(args.manifest.read_text(encoding='utf8'))
    root = Path(__file__).resolve().parents[2]
    config = replace(settings(root/'server/models'/f'{args.models[0]}.pt',
        device='cuda',beam=args.beam),ctc_weight=args.ctc,nbest=args.beam)
    engine = NativeAvsrEngine(config)
    engine.load()
    cap = cv2.VideoCapture(str(args.manifest.parent/manifest['video']))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok: break
        if args.mirror: frame = cv2.flip(frame, 1)
        if args.width and frame.shape[1] > args.width:
            frame = cv2.resize(frame,(args.width,round(frame.shape[0]*args.width/frame.shape[1])),
                               interpolation=cv2.INTER_AREA)
        frames.append(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
    cap.release()
    prepared = []
    for item in manifest['segments']:
        selected = [frames[min(len(frames)-1,round((item['start']+i/25)*fps))]
                    for i in range(round((item['end']-item['start'])*25))]
        tick=time.perf_counter()
        data = engine._preprocessor.prepare_frames(selected,source_fps=25,input_kind='raw_face')
        prepared.append((item,data,time.perf_counter()-tick))
        torch.save(data.tensor,args.output/f"prepared-{item['id']}.pt")
        roi=((data.tensor[len(data.tensor)//2,0]*.165+.421)*255).clip(0,255).byte().numpy()
        cv2.imwrite(str(args.output/f"mouth-{item['id']}.png"),roi)
    records = []
    for run in args.models:
        payload=torch.load(root/'server/models'/f'{run}.pt',map_location='cpu',weights_only=True,mmap=True)
        state=payload.get('model',payload.get('state_dict',payload))
        if all(k.startswith('model.') for k in state):
            state={k[6:]:v for k,v in state.items()}
        engine._model.load_state_dict(state,strict=True)
        del payload,state
        gc.collect()
        for item,data,prep in prepared:
            torch.cuda.synchronize();tick=time.perf_counter()
            result=engine._decode_native(data,realtime=True)
            torch.cuda.synchronize();elapsed=time.perf_counter()-tick
            ref=normalized_words(item['reference']);hyp=normalized_words(result.transcript)
            row=dict(model=run,id=item['id'],reference=item['reference'],hypothesis=result.transcript,
                errors=errors(ref,hyp),words=len(ref),decode_seconds=elapsed,preprocess_seconds=prep,
                source_seconds=data.num_frames/25,alternatives=result.alternatives,
                greedy=result.diagnostics['greedy_transcript'],aligned_words=result.diagnostics['words'])
            records.append(row)
            (args.output/'RESULTS.json').write_text(json.dumps(dict(
                manifest=str(args.manifest.resolve()),scope=manifest['boundary_scope'],
                reference_status=manifest['reference_status'],beam=args.beam,ctc=args.ctc,
                mirror=args.mirror,width=args.width,
                face_detector_policy=getattr(engine._preprocessor, 'face_detector_policy', 'full_first'),
                records=records),ensure_ascii=False,indent=2),encoding='utf8')
            print(run,item['id'],f"{row['errors']}/{row['words']}",round(elapsed,2),result.transcript,flush=True)
        selected=[r for r in records if r['model']==run]
        print('SUMMARY',run,sum(r['errors'] for r in selected),sum(r['words'] for r in selected),
              'median_decode',round(statistics.median(r['decode_seconds'] for r in selected),3),flush=True)


if __name__=='__main__':
    main()
