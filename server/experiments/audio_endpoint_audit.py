"""Audio-derived timing estimates for evaluation only; never used by live VSR."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import torch


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--ffmpeg',required=True)
    p.add_argument('--deps',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    sys.path.insert(0,str(args.deps.resolve()))
    from silero_vad import load_silero_vad,get_speech_timestamps
    model=load_silero_vad()
    raw=subprocess.check_output([args.ffmpeg,'-v','error','-i',str(args.video),
        '-map','0:a:0','-ar','16000','-ac','1','-f','f32le','pipe:1'])
    audio=torch.from_numpy(np.frombuffer(raw,dtype=np.float32).copy())
    results={}
    for threshold in (.4,.5,.6):
        results[str(threshold)]=get_speech_timestamps(audio,model,sampling_rate=16000,
            threshold=threshold,min_silence_duration_ms=600,speech_pad_ms=0,
            return_seconds=True,time_resolution=3)
    model_path=args.deps/'silero_vad/data/silero_vad.jit'
    report=dict(video=str(args.video.resolve()),video_sha256=hashlib.sha256(args.video.read_bytes()).hexdigest(),
        model='silero-vad 6.2.3',model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
        scope='Automatic audio VAD estimates, not human word-end annotations. Audio is used only for offline timing evaluation, never for visual predictions or endpoints.',
        thresholds=results,sample_rate=16000,samples=len(audio))
    args.output.write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
