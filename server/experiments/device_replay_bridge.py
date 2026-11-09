"""Loopback-only QA bridge: prerecorded visual input, actual Android caption UI.

The phone's camera frames are acknowledged but not forwarded. A fixed source video
is paced to the real VSR server; its captions are forwarded to the installed app.
This validates transport/rendering, NOT physical-camera recognition. Test history
entries are identified by a QA prerecorded model ID. No audio enters inference.
"""
import argparse
import asyncio
import json
from pathlib import Path
import struct
import time

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from experiments.phoneme_probe.fixed_windows import camera_jpegs


async def main(args):
    args.output.mkdir(parents=True,exist_ok=False)
    frames=camera_jpegs(args.video,360)
    done=asyncio.Event()
    report=dict(scope=__doc__,video=str(args.video.resolve()),events=[],receipts=[],
                phone_frames=0,source_frames=0,source_acknowledgements=0)

    def save():
        (args.output/'RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')

    async def handle(phone):
        started=time.perf_counter()
        first_camera=asyncio.Event()
        tasks=[]
        try:
            hello=json.loads(await phone.recv())
            assert hello['type']=='start' and hello['protocol']==2
            async with connect(args.backend,max_size=2**20,ping_timeout=60) as backend:
                await backend.send(json.dumps(dict(type='start',protocol=2,input_kind='raw_face',auto_endpoint=True)))
                ready=json.loads(await backend.recv())
                assert ready['type']=='ready'
                await phone.send(json.dumps(ready))
                report['ready_seconds']=time.perf_counter()-started

                async def from_phone():
                    async for payload in phone:
                        if isinstance(payload,bytes):
                            assert payload[:4]==b'LIP2'
                            sequence=struct.unpack('>I',payload[4:8])[0]
                            report['phone_frames']+=1
                            first_camera.set()
                            await phone.send(json.dumps(dict(type='ack',sequence=sequence)))
                        else:
                            message=json.loads(payload)
                            if message['type']=='caption_rendered':
                                report['receipts'].append(dict(message,wall_seconds=time.perf_counter()-started))
                                await backend.send(payload)
                            elif message['type']=='stop':
                                return

                async def source():
                    await asyncio.wait_for(first_camera.wait(),15)
                    origin=time.perf_counter()
                    report['source_origin_seconds']=origin-started
                    for i,jpeg in enumerate(frames):
                        await asyncio.sleep(max(0,origin+i/25-time.perf_counter()))
                        await backend.send(b'LIP2'+struct.pack('>Id',i,i*40.)+jpeg)
                        report['source_frames']+=1
                    await backend.send(json.dumps(dict(type='stop')))

                async def to_phone():
                    async for payload in backend:
                        message=json.loads(payload)
                        if message['type']=='ack':
                            report['source_acknowledgements']+=1
                            continue
                        if 'model_id' in message:
                            message['model_id']='QA-prerecorded-'+message['model_id']
                        report['events'].append(dict(message,bridge_seconds=time.perf_counter()-started))
                        await phone.send(json.dumps(message,ensure_ascii=False))
                        if message['type'] in ('segment_final','session_final'):
                            save()
                        if message['type']=='session_final':return

                tasks=[asyncio.create_task(from_phone()),asyncio.create_task(source()),asyncio.create_task(to_phone())]
                await asyncio.wait_for(tasks[2],len(frames)/25+45)
                await tasks[1]
                report['complete']=True
                save()
                print('QA replay complete',report['source_frames'],'frames',len(report['receipts']),'render receipts',flush=True)
                await asyncio.sleep(1)
        except Exception as exc:
            report['error']=repr(exc)
            save()
            raise
        finally:
            for task in tasks:
                if not task.done():task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            done.set()

    async with serve(handle,'127.0.0.1',args.port,max_size=2**20,ping_timeout=60):
        print('QA bridge ready',args.port,flush=True)
        await asyncio.wait_for(done.wait(),180)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--backend',default='ws://127.0.0.1:7100/v1/realtime')
    p.add_argument('--port',type=int,default=7102)
    p.add_argument('--output',type=Path,required=True)
    asyncio.run(main(p.parse_args()))
