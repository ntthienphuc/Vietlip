"""Extract each cropped window separately: no reuse of future-aware full-clip states."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time
import cv2
import numpy as np
import torch


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--raw-root',type=Path,required=True)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--vendor',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    data=json.loads(args.dataset.read_text(encoding='utf8'))
    checkpoint_sha=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
    if checkpoint_sha!='cddfb8c79f1db9d66695c0b1b7e2d98837187c600668a8aee3ccdd5b58981ecc':
        raise RuntimeError('Remote checkpoint is not the app SO17 checkpoint')
    identity=dict(dataset_sha256=hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        checkpoint_sha256=checkpoint_sha,dtype='float32',encoder='frozen_eval_cropped_windows',
        audio_used=False,torch=torch.__version__,opencv=cv2.__version__,gpu=torch.cuda.get_device_name(0))
    (args.output/'IDENTITY.json').write_text(json.dumps(identity,indent=2))
    sys.path.insert(0,str(args.vendor))
    from espnet.nets.pytorch_backend.e2e_asr_conformer import E2E
    model=E2E(2002,'video',ctc_weight=.1)
    payload=torch.load(args.checkpoint,map_location='cpu',weights_only=True,mmap=True)
    state=payload.get('model',payload.get('state_dict',payload))
    if all(k.startswith('model.') for k in state):state={k[6:]:v for k,v in state.items()}
    model.load_state_dict(state,strict=True);del payload,state
    model.to('cuda').eval().requires_grad_(False)
    grouped=defaultdict(list)
    for r in data['records']:grouped[r['parent_id']].append(r)
    done=0;start=time.perf_counter()
    with torch.inference_mode():
        for identifier,rows in grouped.items():
            path=args.raw_root/(identifier+'.mp4')
            assert hashlib.sha256(path.read_bytes()).hexdigest()==rows[0]['sha256'],identifier
            cap=cv2.VideoCapture(str(path))
            assert abs(cap.get(cv2.CAP_PROP_FPS)-25)<.001
            frames=[]
            while True:
                ok,frame=cap.read()
                if not ok:break
                assert frame.shape[:2]==(96,96)
                frames.append(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY))
            cap.release()
            tensor=(torch.from_numpy(np.stack(frames)).float()[:,None,4:92,4:92]/255-.421)/.165
            for row in rows:
                x=tensor[row['window_start']:row['window_stop']].to('cuda')
                encoded=model.encoder(model.proj_encoder(model.frontend(x[None])),None)[0][0]
                assert torch.isfinite(encoded).all()
                key=hashlib.sha256(row['id'].encode()).hexdigest()[:24]
                torch.save(dict(id=row['id'],encoded=encoded.cpu().clone(),frames=len(encoded)),
                           args.output/f'{key}.pt')
                done+=1
            if done%100<len(rows) or done==len(data['records']):
                status=dict(done=done,total=len(data['records']),seconds=time.perf_counter()-start)
                (args.output/'PROGRESS.json').write_text(json.dumps(status))
                print(json.dumps(status),flush=True)
    (args.output/'COMPLETE.json').write_text(json.dumps(dict(identity=identity,done=done,seconds=time.perf_counter()-start),indent=2))

if __name__=='__main__':main()
