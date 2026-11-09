"""Local transport-only receiver. No recognition/accuracy claims from this probe."""
import asyncio, json, struct, time
from pathlib import Path
from websockets.asyncio.server import serve

async def session(ws):
    await ws.recv()
    await ws.send(json.dumps(dict(type='ready', protocol=2, sample_fps=25,
                                 max_inflight_frames=4, max_seconds=300)))
    samples=[]
    started=time.perf_counter()
    async for packet in ws:
        if isinstance(packet,bytes):
            sequence, milliseconds=struct.unpack('>Id',packet[4:16])
            samples.append(dict(sequence=sequence, capture_ms=milliseconds,
                                arrival=time.perf_counter()-started, bytes=len(packet)))
            await ws.send(json.dumps(dict(type='ack',sequence=sequence)))
        elif json.loads(packet).get('type')=='stop':
            await ws.send(json.dumps(dict(type='session_final',transcript='',
                stable_transcript='',received_frames=len(samples), model_id='transport-probe')))
            break
    if len(samples)>1:
        span=(samples[-1]['capture_ms']-samples[0]['capture_ms'])/1000
        result=dict(scope='emulator camera transport only', frames=len(samples),
            source_seconds=span, fps=(len(samples)-1)/span,samples=samples)
        path=Path('artifacts/optimization_v2')/f'camera_{time.time_ns()}.json'
        path.write_text(json.dumps(result,indent=2))
        print(path,result['frames'],result['fps'],flush=True)

async def main():
    async with serve(session,'0.0.0.0',7100,max_size=2**20):
        print('transport probe ready 7100',flush=True)
        await asyncio.Future()

if __name__=='__main__': asyncio.run(main())
