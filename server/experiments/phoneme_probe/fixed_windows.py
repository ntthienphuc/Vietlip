"""Cache identical visual states/candidates for paired window-by-window comparisons."""
from __future__ import annotations
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time
import cv2
import torch
from scripts.benchmark_models import settings
from app.services.native_engine import NativeAvsrEngine
from app.services.word_alignment import align_words
from .codec import words,edit_distance


def decode_candidates(engine,encoded):
    logp=engine._model.ctc.log_softmax(encoded[None])[0].cpu().numpy()
    result=[]
    for hyp in engine._beams[3](encoded)[:3]:
        ids=[int(i) for i in hyp.yseq[1:] if 0<int(i)<engine._model.eos]
        result.append(dict(text=engine._text(ids),raw_score=float(hyp.score),
            words=align_words(logp,ids,engine.tokens,25,decode_pieces=engine._spm.decode)))
    assert result
    return result


def camera_jpegs(video,width=0):
    cap=cv2.VideoCapture(str(video));fps=cap.get(cv2.CAP_PROP_FPS);raw=[]
    while True:
        ok,frame=cap.read()
        if not ok:break
        raw.append(frame)
    cap.release()
    assert raw
    output=[]
    for index in range(round(len(raw)/fps*25)):
        frame=raw[min(len(raw)-1,round(index/25*fps))]
        if width and frame.shape[1]>width:
            frame=cv2.resize(frame,(width,round(frame.shape[0]*width/frame.shape[1])),interpolation=cv2.INTER_AREA)
        ok,jpeg=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,80])
        assert ok
        output.append(jpeg.tobytes())
    return output


def camera_frames(video,width=0):
    import numpy as np
    return [cv2.cvtColor(cv2.imdecode(np.frombuffer(jpeg,np.uint8),cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)
            for jpeg in camera_jpegs(video,width)]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',choices=['live','corpus'],required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--features',type=Path)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    engine=NativeAvsrEngine(replace(settings(args.checkpoint,device='cuda',beam=3),precision='float32',nbest=3))
    engine.load();assert engine._phoneme_rescorer is None
    manifest=json.loads(args.manifest.read_text(encoding='utf8'))
    records=[];started=time.perf_counter()
    if args.kind=='live':
        for clip in manifest['clips']:
            video=Path(clip['video']);assert hashlib.sha256(video.read_bytes()).hexdigest()==clip['sha256']
            rgb=camera_frames(video,360 if clip['input_kind']=='raw_face' else 0)
            for i,event in enumerate(clip['windows']):
                begin,end=round(event['window_start']*25),round(event['window_end']*25)
                assert 0<=begin<end<=len(rgb),(clip['id'],begin,end,len(rgb))
                prepared=engine._preprocessor.prepare_frames(rgb[begin:end],source_fps=25,input_kind=clip['input_kind'])
                with torch.inference_mode():
                    x=prepared.tensor.to('cuda')
                    encoded=engine._model.encoder(engine._model.proj_encoder(engine._model.frontend(x[None])),None)[0][0]
                    candidates=decode_candidates(engine,encoded)
                identifier=f"{clip['id']}/{i}"
                key=hashlib.sha256(identifier.encode()).hexdigest()[:24]
                torch.save(dict(id=identifier,encoded=encoded.cpu().clone()),args.output/f'{key}.pt')
                records.append(dict(id=identifier,clip=clip['id'],event=event,feature_file=f'{key}.pt',
                    tensor_sha256=hashlib.sha256(prepared.tensor.numpy().tobytes()).hexdigest(),
                    encoded_sha256=hashlib.sha256(encoded.cpu().numpy().tobytes()).hexdigest(),candidates=candidates))
            print(f"{clip['id']}: {len(clip['windows'])} identical cached windows",flush=True)
    else:
        for row in manifest['records']:
            key=hashlib.sha256(row['id'].encode()).hexdigest()[:24]
            if args.features:
                feature=args.features/f'{key}.pt'
                x=torch.load(feature,weights_only=True,map_location='cpu')['encoded']
            else:
                video=Path(row['video'])
                assert hashlib.sha256(video.read_bytes()).hexdigest()==row['sha256']
                prepared=engine._preprocessor.prepare(video,input_kind='mouth_roi')
                tensor=prepared.tensor[row['window_start']:row['window_stop']].to('cuda')
                with torch.inference_mode():
                    x=engine._model.encoder(engine._model.proj_encoder(engine._model.frontend(tensor[None])),None)[0][0].cpu()
                feature=args.output/f'{key}.pt'
                torch.save(dict(id=row['id'],encoded=x.clone()),feature)
            with torch.inference_mode():candidates=decode_candidates(engine,x.to('cuda'))
            for candidate in candidates:
                # Evaluate complete-word core only; prediction never sees these bounds.
                selected=[w['text'] for w in candidate['words'] if
                    row['loss_start']/25 <= (w['start']+w['end'])/2 < row['loss_stop']/25]
                candidate['core_text']=' '.join(selected)
                candidate['core_errors']=edit_distance(row['words'],words(candidate['core_text']))
            records.append(dict(id=row['id'],split=row['split'],reference=row['text'],phones=row['phones'],
                loss_start=row['loss_start'],loss_stop=row['loss_stop'],feature_file=str(feature.resolve()),
                encoded_sha256=hashlib.sha256(x.numpy().tobytes()).hexdigest(),candidates=candidates))
            if len(records)%40==0:print(f'Corpus {len(records)}/{len(manifest["records"])}',flush=True)
    report=dict(kind=args.kind,manifest=str(args.manifest.resolve()),
        manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        seconds=time.perf_counter()-started,records=records)
    (args.output/'CACHE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');main()
