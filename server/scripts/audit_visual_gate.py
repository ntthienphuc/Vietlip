"""Pixel-level nonspeech controls; synthetic controls are not natural validation."""
import json
import math
import time
from pathlib import Path
import cv2
import numpy as np
from app.services.visual_activity import VisualMotionDetector, EndpointPolicy

ROOT=Path(__file__).resolve().parents[2]


def main():
    cap=cv2.VideoCapture(str(ROOT/'artifacts/validation/phone_samples/phone_01.mp4'))
    ok,first=cap.read();cap.release()
    assert ok
    first=cv2.cvtColor(cv2.resize(first,(360,640)),cv2.COLOR_BGR2RGB)
    report=[]
    for name in ['frozen_face','rigid_pan_roll_zoom','blank_camera','face_disappears']:
        detector=VisualMotionDetector();detector.load();gate=EndpointPolicy()
        events=[];samples=[]
        for i in range(100):
            t=i*.12
            frame=first
            if name=='rigid_pan_roll_zoom':
                matrix=cv2.getRotationMatrix2D((180,320),3*math.sin(t*2),1+.02*math.sin(t))
                matrix[:,2]+=[4*math.sin(t*2),3*math.cos(t*2)]
                frame=cv2.warpAffine(first,matrix,(360,640),borderMode=cv2.BORDER_REFLECT)
            elif name=='blank_camera' or (name=='face_disappears' and 3<t<8):
                frame=np.zeros_like(first)
            tick=time.perf_counter();obs=detector.analyze(frame);elapsed=(time.perf_counter()-tick)*1000
            update=gate.observe(t,obs)
            if update.start is not None or update.end is not None:
                events.append(dict(time=t,start=update.start,end=update.end,reason=update.reason))
            samples.append(dict(time=t,score=obs.score,quality=obs.quality,state=update.state,ms=elapsed))
        detector.close()
        report.append(dict(scenario=name,seconds=12,starts=sum(e['start'] is not None for e in events),
            events=events,p95_ms=float(np.percentile([s['ms'] for s in samples],95)),samples=samples))
        print(name,report[-1]['starts'],report[-1]['p95_ms'],flush=True)
    (ROOT/'artifacts/live_v3/VISUAL_GATE_CONTROLS.json').write_text(json.dumps(dict(
        scope='One real face first-frame, synthetic stationary/rigid-image-motion/blank controls. Not natural chewing, smiling, 3D head turns, or VAD accuracy.',
        scenarios=report),indent=2),encoding='utf8')


if __name__=='__main__':main()
