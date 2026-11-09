"""Send concatenated local clips at camera pace through the real WebSocket API."""
from __future__ import annotations
import argparse
import asyncio
import csv
import json
import struct
import time
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
import cv2
from websockets.asyncio.client import connect
from benchmark_models import errors, normalized_words


async def run(args):
    output=Path(args.output)
    if output.exists(): raise RuntimeError('Use a new output path; previous results are preserved')
    if args.video and str(output.resolve()).lower()==str(Path(args.video).with_suffix('.json').resolve()).lower():
        raise ValueError('Output would overwrite video metadata on Windows')
    samples=Path(args.samples)
    frames=[];reference=[];segments=[];reference_times=[]
    videos=[Path(args.video)] if args.video else sorted(samples.glob('*.mp4'))[:args.limit]
    for video in videos:
        cap=cv2.VideoCapture(str(video))
        fps=cap.get(cv2.CAP_PROP_FPS)
        raw=[]
        while True:
            ok,frame=cap.read()
            if not ok:break
            raw.append(frame)
        cap.release()
        if not raw:continue
        count=round(len(raw)/fps*args.fps)
        begin=len(frames)/args.fps
        for i in range(count):
            frame=raw[min(len(raw)-1,round(i/args.fps*fps))]
            if args.input_kind == 'raw_face' and frame.shape[1] > 360:
                frame=cv2.resize(frame,(360,round(frame.shape[0]*360/frame.shape[1])),interpolation=cv2.INTER_AREA)
            ok,jpeg=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,80])
            if not ok:raise RuntimeError('JPEG encoding failed')
            frames.append(jpeg.tobytes())
        with video.with_suffix('.csv').open(encoding='utf-8-sig') as f:
            rows=list(csv.DictReader(f))
            words=[r['Word'].strip() for r in rows]
            for r in rows:
                ending=r.get('End') or r.get('end')
                reference_times.extend([begin+float(ending) if ending else None]*len(normalized_words(r['Word'])))
        reference.extend(words)
        segments.append({'file':video.name,'start':begin,'end':len(frames)/args.fps})
    if args.video:
        manifest=Path(args.video).with_suffix('.manifest.json')
        if not manifest.exists(): manifest=Path(args.video).with_suffix('.json')
        if manifest.exists(): segments=json.loads(manifest.read_text(encoding='utf-8'))['segments']
    events=[]; ack=-1; sequence=0; dropped=0
    done=asyncio.Event()
    connection_started=time.perf_counter()
    async with connect(args.url,max_size=2**20,open_timeout=10,ping_timeout=60) as ws:
        start_message={'type':'start','protocol':2,'input_kind':args.input_kind}
        if args.endpoint != 'default': start_message['auto_endpoint']=args.endpoint=='auto'
        await ws.send(json.dumps(start_message))
        ready=json.loads(await ws.recv())
        if ready.get('type')!='ready':raise RuntimeError(str(ready))
        ready_seconds=time.perf_counter()-connection_started
        start=time.perf_counter()
        async def receive():
            nonlocal ack
            async for text in ws:
                event=json.loads(text)
                if event['type']=='ack':ack=event['sequence'];continue
                event['wall_seconds']=time.perf_counter()-start
                events.append(event)
                print(event['type'],round(event['wall_seconds'],2),event.get('transcript',event.get('message','')),flush=True)
                if event['type']=='session_final':done.set();return
        receiver=asyncio.create_task(receive())
        for index,jpeg in enumerate(frames):
            target=index/args.fps
            await asyncio.sleep(max(0,start+target-time.perf_counter()))
            if sequence-ack-1>=4:
                dropped+=1;continue
            packet=b'LIP2'+struct.pack('>Id',sequence,target*1000)+jpeg
            await ws.send(packet);sequence+=1
        await ws.send(json.dumps({'type':'stop'}))
        await asyncio.wait_for(done.wait(),timeout=120)
        await receiver
    final=next(e for e in reversed(events) if e['type']=='session_final')
    hyp=normalized_words(final.get('transcript',''))
    reference=normalized_words(' '.join(reference))
    result={'fps':args.fps,'input_kind':args.input_kind,'source_seconds':len(frames)/args.fps,
        'ready_seconds':ready_seconds,
        'sent_frames':sequence,'transport_dropped_frames':dropped,
        'reference':' '.join(reference),'hypothesis':' '.join(hyp),
        'errors':errors(reference,hyp),'reference_words':len(reference),
        'wer':errors(reference,hyp)/max(1,len(reference)),
        'finalization_seconds':final['wall_seconds']-len(frames)/args.fps,
        'segments':segments,'reference_word_ends':reference_times,'events':events,
        'scope':'Paced prerecorded replay; not a physical-camera accuracy measurement'}
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('WER',result['wer'],'tail_seconds',result['finalization_seconds'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--url',default='ws://127.0.0.1:7100/v1/realtime')
    p.add_argument('--samples',default=str(Path(__file__).resolve().parents[2]/'artifacts/validation/samples'))
    p.add_argument('--fps',default=25,type=int)
    p.add_argument('--limit',default=6,type=int)
    p.add_argument('--video',help='A pre-concatenated video with matching timestamp CSV')
    p.add_argument('--input-kind',choices=['raw_face','mouth_roi'],default='mouth_roi')
    p.add_argument('--endpoint',choices=['auto','off','default'],default='default')
    p.add_argument('--output',required=True)
    asyncio.run(run(p.parse_args()))
