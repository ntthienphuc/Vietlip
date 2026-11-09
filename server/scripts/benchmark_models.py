"""Measure actual model errors and warm throughput on a filename-selected set."""
from __future__ import annotations
import argparse
import csv
import gc
import json
import statistics
import sys
import time
import unicodedata
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.services.native_engine import NativeAvsrEngine


def errors(reference,hypothesis):
    previous=list(range(len(hypothesis)+1))
    for i,a in enumerate(reference,1):
        row=[i]
        for j,b in enumerate(hypothesis,1):
            row.append(min(row[-1]+1,previous[j]+1,previous[j-1]+(a!=b)))
        previous=row
    return previous[-1]


def normalized_words(text):
    value=unicodedata.normalize('NFC',text).lower()
    return ''.join(c if unicodedata.category(c)[0] in 'LNM' else ' ' for c in value).split()


def settings(checkpoint,device='auto',beam=3):
    root=Path(__file__).resolve().parents[1]
    return replace(Settings.from_env(), model_backend='native_avsr',
        model_id=Path(checkpoint).stem,checkpoint_path=Path(checkpoint),
        auto_avsr_root=root/'vendor/auto_avsr',
        spm_model_path=root/'assets/tokenizers/vi.model',
        spm_units_path=root/'assets/tokenizers/vi_units.txt',
        beam_size=beam,nbest=beam,realtime_beam_size=beam,
        device=device,precision='auto',cpu_threads=4)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--checkpoint',required=True)
    parser.add_argument('--device',default='auto')
    parser.add_argument('--beam',default=3,type=int)
    parser.add_argument('--limit',default=6,type=int)
    parser.add_argument('--output',required=True)
    parser.add_argument('--samples')
    parser.add_argument('--input-kind',default='mouth_roi',choices=['mouth_roi','raw_face'])
    parser.add_argument('--precision',default='auto')
    args=parser.parse_args()
    import torch
    import cv2
    root=Path(__file__).resolve().parents[2]
    engine=NativeAvsrEngine(replace(settings(args.checkpoint,args.device,args.beam),precision=args.precision))
    start=time.perf_counter();engine.load();load=time.perf_counter()-start
    print('Loaded',engine.device_label,engine.effective_precision,round(load,2),flush=True)
    records=[]
    samples=Path(args.samples) if args.samples else root/'artifacts/validation/samples'
    for video in sorted(samples.glob('*.mp4'))[:args.limit]:
        with video.with_suffix('.csv').open(encoding='utf-8-sig') as f:
            reference=' '.join(r['Word'].strip() for r in csv.DictReader(f))
        cap=cv2.VideoCapture(str(video));frames=cap.get(cv2.CAP_PROP_FRAME_COUNT);fps=cap.get(cv2.CAP_PROP_FPS);cap.release()
        tick=time.perf_counter()
        result=engine.transcribe(video,input_kind=args.input_kind,context_hint=None)
        seconds=time.perf_counter()-tick
        ref=normalized_words(reference);hyp=normalized_words(result.transcript)
        row={'file':video.name,'reference':reference,'hypothesis':result.transcript,
             'errors':errors(ref,hyp),'words':len(ref),'seconds':seconds,
             'duration':frames/fps,'rtf':seconds/(frames/fps),'diagnostics':result.diagnostics}
        records.append(row)
        print(video.name,'WER',round(row['errors']/len(ref),3),'RTF',round(row['rtf'],3),result.transcript,flush=True)
        summary={'checkpoint':str(args.checkpoint),'beam':args.beam,'device':engine.device_label,
            'precision':engine.effective_precision,'load_seconds':load,
            'wer':sum(r['errors'] for r in records)/sum(r['words'] for r in records),
            'mean_rtf':statistics.mean(r['rtf'] for r in records),
            'peak_vram_mb':torch.cuda.max_memory_allocated()/2**20 if torch.cuda.is_available() else None,
            'scope':f'Local sample check, input_kind={args.input_kind}; not an independent deployment evaluation',
            'normalization':'Unicode NFC, lowercase, punctuation removed, Vietnamese whitespace units',
            'records':records}
        Path(args.output).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
