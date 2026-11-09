"""Frozen-config application audit, with references kept outside inference.

All unique media from the existing 144-row boundary review packet are included;
that packet is a curated stress cohort, not a representative independent test.
Reports every failed input as deletions and reports abstention separately.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
import cv2
import numpy as np
from benchmark_models import errors, normalized_words, settings
from app.services.native_engine import NativeAvsrEngine
from app.services.live_evidence import check_live_images
from app.services.video_preprocessor import VideoValidationError

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('E:/Project/Lip/Unified_PR_2026-11-02/Context_Content_Control_2026-11-02')


def score(reference, hypothesis):
    ref, hyp = normalized_words(reference), normalized_words(hypothesis)
    rc, hc = ''.join(ref), ''.join(hyp)
    return dict(word_errors=errors(ref,hyp), reference_words=len(ref),
                char_errors=errors(rc,hc), reference_chars=len(rc))


def summary(rows):
    we, rw = sum(r['word_errors'] for r in rows), sum(r['reference_words'] for r in rows)
    ce, rc = sum(r['char_errors'] for r in rows), sum(r['reference_chars'] for r in rows)
    return dict(clips=len(rows), word_errors=we, reference_words=rw, wer=we/max(1,rw),
        char_errors=ce, reference_chars=rc, cer=ce/max(1,rc),
        unavailable=sum(not r['hypothesis'].strip() for r in rows),
        unavailable_rate=sum(not r['hypothesis'].strip() for r in rows)/max(1,len(rows)),
        exact_clips=sum(r['word_errors']==0 for r in rows),
        clips_wer_at_least_one=sum(r['word_errors']>=r['reference_words'] for r in rows),
        duration_seconds=sum(r['duration'] for r in rows),
        median_processing_seconds=float(np.median([r['seconds'] for r in rows])),
        p95_processing_seconds=float(np.percentile([r['seconds'] for r in rows],95)),
        processing_rtf=sum(r['seconds'] for r in rows)/sum(r['duration'] for r in rows))


def prepare(out):
    packet = SOURCE/'Boundary_Rater_Packet'
    provenance = {r['audit_id']:r for r in json.loads((SOURCE/'boundary_audit/Media_Provenance.json').read_text(encoding='utf8'))['clips']}
    rows = list(csv.DictReader((packet/'rater_1/Clips.csv').open(encoding='utf-8-sig')))
    prior = {hashlib.sha256(p.read_bytes()).hexdigest() for folder in
        [ROOT/'artifacts/validation/samples',ROOT/'artifacts/optimization_v2/long_samples'] for p in folder.glob('*.mp4')}
    train = SOURCE.parent/'Exposure_Paired_Seeds_2026-11-02/Portable_Training_Preparation_Actual_v1/Training/raw'
    train_names = {p.stem for p in train.rglob('*.mp4')}
    chosen, seen = [], set()
    dest = out/'samples'; dest.mkdir(parents=True,exist_ok=True)
    for row in sorted(rows,key=lambda r:hashlib.sha256(r['audit_id'].encode()).hexdigest()):
        src = packet/row['media']; digest=hashlib.sha256(src.read_bytes()).hexdigest()
        if digest in seen or digest in prior:
            continue
        seen.add(digest)
        p=provenance[row['audit_id']]
        target=dest/src.name
        if not target.exists(): shutil.copy2(src,target)
        assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
        cap=cv2.VideoCapture(str(target)); duration=cap.get(cv2.CAP_PROP_FRAME_COUNT)/cap.get(cv2.CAP_PROP_FPS);cap.release()
        with target.with_suffix('.csv').open('w',encoding='utf8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['Word','Start','End']);writer.writeheader()
            writer.writerow(dict(Word=row['full_transcript'],Start=0,End=duration))
        chosen.append(dict(file=src.name,source=str(src),sha256=digest,
            population=p['population'],clip_id=p['clip_id'],source_id=p['source_id'],
            training_filename_match=Path(p['clip_id']).name in train_names,
            reference=row['full_transcript'],duration=duration))
    manifest=dict(scope='Application stress cohort; existing canonical references, no new human review. Not a representative or independently collected deployment test.',
        selection='All unique packet media, SHA256 ordering before new inference; excluding exact bytes used by prior app tests.',
        independence='Training filename match is a limited check; pretrained-data and speaker independence are unverified.',
        count=len(chosen),populations=dict(Counter(r['population'] for r in chosen)),
        training_filename_scan_available=train.exists() and bool(train_names),
        training_filename_matches=sum(r['training_filename_match'] for r in chosen),clips=chosen)
    (out/'SELECTION.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    return chosen


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--prepare-only',action='store_true')
    args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    chosen=prepare(out)
    print('Prepared',len(chosen),'clips',sum(r['duration'] for r in chosen),'seconds',flush=True)
    if args.prepare_only:return
    result_path=out/'CLIP_RESULTS.json'
    if result_path.exists():raise RuntimeError('Use a new output directory; previous run is preserved')
    engine=NativeAvsrEngine(settings(ROOT/'server/models/SO_seed17.pt',beam=3));engine.load()
    records=[]
    for r in chosen:
        cap=cv2.VideoCapture(str(out/'samples'/r['file']));frames=[]
        while True:
            ok,frame=cap.read()
            if not ok:break
            frames.append(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
        cap.release()
        tick=time.perf_counter();code=None;hyp=''
        try:
            check_live_images(frames,25)
            result=engine.transcribe_frames(frames,source_fps=25,input_kind='mouth_roi')
            hyp=result.transcript
        except VideoValidationError as exc:code=exc.code
        except Exception as exc:code=type(exc).__name__
        record=dict(r,hypothesis=hyp,seconds=time.perf_counter()-tick,unavailable_reason=code,**score(r['reference'],hyp))
        records.append(record)
        report=dict(config={'model':'SO17','beam':3,'ctc':.1,'input_kind':'mouth_roi','mode':'full utterance, live decoder'},
            scope='Offline paced-independent processing time; not end-to-end live latency. Audio is never read.',
            normalization='NFC, lowercase, punctuation removed. WER: whitespace units; CER: Unicode codepoints with spaces removed.',
            overall=summary(records),populations={k:summary([x for x in records if x['population']==k]) for k in sorted(set(x['population'] for x in records))},records=records)
        result_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(len(records),r['file'],record['word_errors'],record['reference_words'],round(record['seconds'],3),code,flush=True)
    print(json.dumps(report['overall']),flush=True)


if __name__=='__main__':main()
