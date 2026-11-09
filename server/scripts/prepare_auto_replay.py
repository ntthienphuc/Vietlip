"""Separate replay artifacts; preserve originals and disclose synthetic pauses."""
import csv
import json
from pathlib import Path
import cv2

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts/live_v3'


def make(name, paths, size, repeats=1):
    target=OUT/f'{name}.mp4'
    if target.exists(): raise RuntimeError(f'Preserve previous replay: {target}')
    writer=cv2.VideoWriter(str(target),cv2.VideoWriter_fourcc(*'mp4v'),25,size)
    count=0;segments=[];words=[]
    for _ in range(repeats):
        for path in paths:
            cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS);raw=[]
            while True:
                ok,frame=cap.read()
                if not ok:break
                raw.append(cv2.resize(frame,size))
            cap.release()
            for _ in range(50):writer.write(raw[0]);count+=1
            begin=count/25
            for i in range(round(len(raw)/fps*25)):
                writer.write(raw[min(len(raw)-1,round(i/25*fps))]);count+=1
            end=count/25
            for _ in range(50):writer.write(raw[-1]);count+=1
            segments.append(dict(file=path.name,start=begin,speech_end=end,
                pause_end=count/25,boundary_kind='clip end, not human speech annotation'))
            with path.with_suffix('.csv').open(encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    words.append(dict(Word=row['Word'],Start=begin,End=end))
    writer.release()
    with target.with_suffix('.csv').open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['Word','Start','End']);w.writeheader();w.writerows(words)
    target.with_suffix('.manifest.json').write_text(json.dumps(dict(segments=segments,
        duration=count/25,note='Frozen first/last frames simulate pauses; not natural nonspeech. Word timing columns are clip bounds, not word annotations.'),indent=2),encoding='utf8')
    print(target,count/25)


if __name__=='__main__':
    make('phone_auto',sorted((ROOT/'artifacts/validation/phone_samples').glob('*.mp4')),(360,640),repeats=3)
    selection=json.loads((OUT/'SELECTION.json').read_text(encoding='utf8'))
    make('roi_auto24',[OUT/'samples'/r['file'] for r in selection['clips'][:24]],(96,96))
