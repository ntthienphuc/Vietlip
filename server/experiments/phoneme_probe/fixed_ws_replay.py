"""Camera-paced loopback WebSocket replay with frozen, identical decode windows.

This benchmark endpoint is local to this process. It uses the app's preprocessing,
encoder, beam, phoneme rescoring and caption agreement. Endpoint times are replayed
from the manifest; this does not measure automatic endpoint detection or WAN delay.
"""
from __future__ import annotations
import argparse
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import time
import cv2
import numpy as np
import torch
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from app.services.caption_stability import AgreementTimeline
from app.services.native_engine import NativeAvsrEngine
from app.services.phoneme_rescorer import PhonemeRescorer
from scripts.benchmark_models import settings
from .codec import words,edit_distance
from .fixed_windows import camera_jpegs,decode_candidates


def distribution(values):
    return dict(median=float(np.median(values)),p95=float(np.percentile(values,95)),max=max(values))


class PairedDecoder:
    names=('baseline','v1','window')
    def __init__(self,args):
        self.engine=NativeAvsrEngine(replace(settings(args.checkpoint,device='cuda',beam=3),precision='float32',nbest=3))
        self.engine.load()
        assert self.engine._phoneme_rescorer is None
        self.rescorers={name:PhonemeRescorer(path,args.vphon,args.checkpoint,'cuda',weight)
            for name,path,weight in [('v1',args.old_head,args.old_weight),('window',args.new_head,args.new_weight)]}
        self.expected={r['id']:r for r in json.loads(args.cache.read_text(encoding='utf8'))['records']}

    def decode(self,clip,index,event,jpegs):
        tick=time.perf_counter()
        frames=[cv2.cvtColor(cv2.imdecode(np.frombuffer(j,np.uint8),cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB) for j in jpegs]
        prepared=self.engine._preprocessor.prepare_frames(frames,source_fps=25,input_kind=clip['input_kind'])
        expected=self.expected[f"{clip['id']}/{index}"]
        tensor_hash=hashlib.sha256(prepared.tensor.numpy().tobytes()).hexdigest()
        if tensor_hash!=expected['tensor_sha256']:
            raise RuntimeError(f"Replay tensor mismatch: {clip['id']}/{index}")
        with torch.inference_mode():
            x=prepared.tensor.to('cuda')
            model=self.engine._model
            encoded=model.encoder(model.proj_encoder(model.frontend(x[None])),None)[0][0]
            candidates=decode_candidates(self.engine,encoded)
        if [r['text'] for r in candidates]!=[r['text'] for r in expected['candidates']]:
            raise RuntimeError(f"Replay candidate mismatch: {clip['id']}/{index}")
        baseline_ms=(time.perf_counter()-tick)*1000
        selected={'baseline':dict(candidate=candidates[0],extra_ms=0.,changed=False,applied=False)}
        for name,scorer in self.rescorers.items():
            start=time.perf_counter()
            ranked,diagnostics=scorer.rank(encoded,candidates)
            torch.cuda.synchronize()
            selected[name]=dict(candidate=ranked[0],extra_ms=(time.perf_counter()-start)*1000,**diagnostics)
        return dict(index=index,event=event,tensor_sha256=tensor_hash,baseline_ms=baseline_ms,selected=selected)


async def replay(clip,decoder):
    frames=await asyncio.to_thread(camera_jpegs,Path(clip['video']),360 if clip['input_kind']=='raw_face' else 0)
    if clip.get('smoke_only'):
        frames=frames[:round(clip['windows'][-1]['window_end']*25)]
    windows=clip['windows'];results=[];received=0;peak_queue=0
    trace_path=Path(clip['source_trace'])
    assert hashlib.sha256(trace_path.read_bytes()).hexdigest()==clip['trace_sha256']
    trace_text=trace_path.read_text(encoding='utf8')
    source_events=([json.loads(line) for line in trace_text.splitlines()]
        if clip.get('trace_format')=='jsonl' else json.loads(trace_text)['events'])
    original=[e for e in source_events
              if e['type'] in ('partial','segment_final')]
    for i,event in enumerate(windows):
        assert (event['type'],event['window_start'],event['window_end'])==(
            original[i]['type'],original[i]['window_start'],original[i]['window_end'])
        event['release_seconds']=max(event['window_end'],
            original[i]['wall_seconds']-original[i]['elapsed_ms']/1000-clip.get('capture_clock_offset_seconds',0))
    queue=asyncio.Queue()
    timelines={name:AgreementTimeline() for name in decoder.names}
    clock_start=None

    async def handler(ws):
        nonlocal received,peak_queue,clock_start
        hello=json.loads(await ws.recv())
        assert hello==dict(type='start',clip=clip['id'])
        await ws.send(json.dumps(dict(type='ready')))
        images={};next_window=0

        async def consume():
            while True:
                item=await queue.get()
                if item is None:break
                index,event,snapshot,available=item
                release=clock_start+event['release_seconds']
                await asyncio.sleep(max(0,release-time.perf_counter()))
                started=time.perf_counter()
                try:
                    result=await asyncio.to_thread(decoder.decode,clip,index,event,snapshot)
                except Exception as exc:
                    await ws.send(json.dumps(dict(type='error',message=str(exc))))
                    raise
                result['queue_ms']=max(0,started-max(available,release))*1000
                result['wall_seconds']=time.perf_counter()-clock_start
                for name,selected in result['selected'].items():
                    candidate=selected['candidate']
                    if candidate['words']:
                        update=timelines[name].update(candidate['words'],event['window_start'],event['window_end'],
                            final=event['type']=='segment_final',right_context=1.)
                    else:
                        timelines[name].discard_pending();update=dict(transcript=timelines[name].text)
                    selected['caption']=update
                results.append(result)
                await ws.send(json.dumps(dict(type='window',index=index,wall_seconds=result['wall_seconds'])))
            await ws.send(json.dumps(dict(type='session_final',windows=len(results))))

        worker=asyncio.create_task(consume())
        try:
            async for message in ws:
                if isinstance(message,str):
                    assert json.loads(message)==dict(type='stop')
                    if next_window!=len(windows):raise RuntimeError('Missing scheduled windows')
                    await queue.put(None);await worker;break
                assert message[:4]==b'LIP2'
                seq,ms=struct.unpack('>Id',message[4:16])
                assert seq==received and abs(ms-seq*40)<.001
                images[seq]=message[16:];received+=1
                while next_window<len(windows) and round(windows[next_window]['window_end']*25)<=received:
                    event=windows[next_window]
                    left,right=round(event['window_start']*25),round(event['window_end']*25)
                    snapshot=tuple(images[j] for j in range(left,right))
                    queue.put_nowait((next_window,event,snapshot,time.perf_counter()))
                    peak_queue=max(peak_queue,queue.qsize());next_window+=1
                images.pop(seq-250,None)
                await ws.send(json.dumps(dict(type='ack',sequence=seq)))
        finally:
            if not worker.done():worker.cancel()
            await asyncio.gather(worker,return_exceptions=True)

    acknowledgements=0;client_events=[];max_lateness=0.
    async with serve(handler,'127.0.0.1',0,max_size=2**20) as server:
        port=server.sockets[0].getsockname()[1]
        async with connect(f'ws://127.0.0.1:{port}',max_size=2**20,ping_timeout=60) as ws:
            await ws.send(json.dumps(dict(type='start',clip=clip['id'])))
            assert json.loads(await ws.recv())['type']=='ready'
            clock_start=time.perf_counter()
            async def receive():
                nonlocal acknowledgements
                async for message in ws:
                    event=json.loads(message)
                    if event['type']=='ack':acknowledgements+=1;continue
                    if event['type']=='error':raise RuntimeError(event['message'])
                    client_events.append(event)
                    if event['type']=='session_final':return
            receiver=asyncio.create_task(receive())
            try:
                for index,jpeg in enumerate(frames):
                    target=clock_start+index/25
                    await asyncio.sleep(max(0,target-time.perf_counter()))
                    max_lateness=max(max_lateness,time.perf_counter()-target)
                    await ws.send(b'LIP2'+struct.pack('>Id',index,index*40.)+jpeg)
                    if receiver.done():await receiver
                await ws.send(json.dumps(dict(type='stop')))
                await asyncio.wait_for(receiver,120)
            finally:
                if not receiver.done():receiver.cancel()
    assert received==len(frames)==acknowledgements
    assert len(results)==len(windows)
    ref=words(clip['reference']);outcomes={}
    for name,timeline in timelines.items():
        hyp=words(timeline.text)
        outcomes[name]=dict(errors=edit_distance(ref,hyp),words=len(ref),wer=edit_distance(ref,hyp)/len(ref),
            char_errors=edit_distance(''.join(ref),''.join(hyp)),chars=len(''.join(ref)),hypothesis=timeline.text,
            changed_windows=sum(r['selected'][name].get('changed',False) for r in results),
            unavailable_windows=sum(not r['selected'][name]['candidate']['words'] for r in results),
            extra_ms=distribution([r['selected'][name]['extra_ms'] for r in results]))
    return dict(clip=clip['id'],source_seconds=len(frames)/25,frames=received,acknowledgements=acknowledgements,
        windows=len(results),peak_queue=peak_queue,max_sender_lateness_seconds=max_lateness,
        queue_ms=distribution([r['queue_ms'] for r in results]),
        baseline_decode_ms=distribution([r['baseline_ms'] for r in results]),
        frozen_endpoint_wait_seconds=distribution([r['event']['release_seconds']-r['event']['window_end']
            for r in results if r['event']['type']=='segment_final'] or [0.]),
        window_to_caption_seconds=distribution([r['wall_seconds']-r['event']['window_end'] for r in results]),
        outcomes=outcomes,events=results,client_events=client_events)


async def main(args):
    args.output.mkdir(parents=True,exist_ok=False)
    manifest=json.loads(args.manifest.read_text(encoding='utf8'))
    decoder=await asyncio.to_thread(PairedDecoder,args)
    report=dict(scope=__doc__,smoke_only=bool(args.max_windows),fps=25,weights=dict(v1=args.old_weight,window=args.new_weight),clips=[])
    for clip in manifest['clips']:
        if args.clip and clip['id']!=args.clip:continue
        if args.max_windows:
            clip=dict(clip,windows=clip['windows'][:args.max_windows],smoke_only=True)
        assert hashlib.sha256(Path(clip['video']).read_bytes()).hexdigest()==clip['sha256']
        result=await replay(clip,decoder)
        report['clips'].append(result)
        (args.output/'RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in result.items() if k not in ('events','client_events','outcomes')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','cache','checkpoint','old-head','new-head','vphon','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--old-weight',type=float,default=1.)
    p.add_argument('--new-weight',type=float,required=True)
    p.add_argument('--clip')
    p.add_argument('--max-windows',type=int,help='Short harness smoke check only, not an accuracy evaluation')
    asyncio.run(main(p.parse_args()))
