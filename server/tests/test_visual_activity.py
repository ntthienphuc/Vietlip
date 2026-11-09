import time
import struct
import json
from dataclasses import replace
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.services.visual_activity import EndpointPolicy, Observation, VisualMotionDetector
from test_streaming_v2 import TimedEngine


def test_pause_debounce_keeps_short_pause_and_finalizes_long_pause_once():
    gate = EndpointPolicy()
    states = []
    for i in range(60):
        moving = 10 <= i < 20 or 24 <= i < 35
        states.append(gate.observe(i*.12, Observation(2. if moving else 0.)))
    starts = [s for s in states if s.start is not None]
    ends = [s for s in states if s.end is not None]
    assert len(starts) == len(ends) == 1
    assert starts[0].start < 1.2
    assert ends[0].reason == 'visual_pause'
    assert abs(ends[0].end - (34*.12+.24)) < .001


def test_missing_face_and_capture_gap_are_not_silence_successes():
    for missing, reason in [(False,'capture_gap'),(True,'waiting_for_face')]:
        gate = EndpointPolicy()
        for i in range(6): gate.observe(i*.12,Observation(2.))
        assert gate.active
        if missing:
            updates=[gate.observe(.72+i*.12,Observation(quality='waiting_for_face')) for i in range(10)]
        else:
            updates=[gate.observe(2.,Observation(2.))]
        assert [u.reason for u in updates if u.end is not None] == [reason]
        assert not gate.active


def test_still_and_single_motion_pulse_never_create_utterance():
    gate = EndpointPolicy()
    for i in range(100):
        u=gate.observe(i*.12, Observation(8. if i==30 else 0.))
        assert u.start is None and u.end is None


def test_face_shape_rejects_rigid_motion_but_detects_mouth_deformation():
    p=np.zeros((468,2))
    p[[33,133]]=[100,100];p[[362,263]]=[200,100];p[1]=[150,150]
    for i,k in enumerate(VisualMotionDetector.LIPS):
        angle=2*np.pi*i/len(VisualMotionDetector.LIPS)
        p[k]=[150+35*np.cos(angle),190+8*np.sin(angle)]
    p[13]=[150,188];p[14]=[150,192]
    detector=VisualMotionDetector()
    detector.landmarks(p)
    for a in [0.02,.04,.06]:
        rotation=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
        shifted=p@rotation.T*1.01+[2,4]
        observation=detector.landmarks(shifted)
        assert observation.quality=='visible' and observation.score<.001
    detector.landmarks(p)
    moving=p.copy();moving[14,1]+=12
    assert detector.landmarks(moving).score>1


def test_auto_websocket_two_utterances_without_flush_or_camera_restart(monkeypatch, tmp_path):
    monkeypatch.setenv('LIP_REALTIME_TRACE_DIR', str(tmp_path))
    monkeypatch.setattr(VisualMotionDetector,'load',lambda self:None)
    monkeypatch.setattr(VisualMotionDetector,'analyze',lambda self,rgb:Observation(2. if rgb.mean()>110 else 0.))
    settings=replace(Settings.from_env(),realtime_window_seconds=3,
        realtime_min_seconds=1.,realtime_decode_interval_seconds=.6)
    with TestClient(create_app(settings=settings,engine=TimedEngine())) as client:
        with client.websocket_connect('/v1/realtime') as ws:
            ws.send_json(dict(type='start',protocol=2,input_kind='mouth_roi',auto_endpoint=True))
            assert ws.receive_json()['auto_endpoint']
            events=[]
            for i in range(75):
                speaking=8<=i<23 or 40<=i<55
                value=(150+i%30) if speaking else 80
                _,jpeg=cv2.imencode('.jpg',np.full((96,96,3),value,np.uint8))
                ws.send_bytes(b'LIP2'+struct.pack('>Id',i,i*120)+jpeg.tobytes())
                while True:
                    event=ws.receive_json();events.append(event)
                    if 'caption_event_id' in event:
                        ws.send_json(dict(type='caption_rendered',
                            caption_event_id=event['caption_event_id'], receive_to_frame_ms=0))
                    if event['type']=='ack':break
                time.sleep(.055)
            ws.send_json({'type':'stop'})
            while not events or events[-1]['type']!='session_final':
                events.append(ws.receive_json())
            finals=[e for e in events if e['type']=='segment_final']
            assert len(finals)==2
            assert all(e['endpoint_reason']=='visual_pause' for e in finals)
            assert events[-1]['transcript']=='xin chào xin chào'
            assert events[-1]['received_frames']==75
    receipts = [json.loads(line) for path in tmp_path.glob('*.jsonl')
                for line in path.read_text(encoding='utf8').splitlines()
                if json.loads(line)['type']=='caption_render_ack']
    assert receipts
    assert all(r['server_send_to_render_ack_ms'] >= 0 for r in receipts)


@pytest.mark.parametrize('has_activity',[False,True])
def test_idle_does_not_infer_and_decoder_failure_still_completes_session(monkeypatch,has_activity):
    class BrokenEngine(TimedEngine):
        calls=0
        def transcribe_frames(self,*args,**kwargs):
            self.calls+=1
            raise RuntimeError('deliberate inference failure')
    engine=BrokenEngine()
    monkeypatch.setattr(VisualMotionDetector,'load',lambda self:None)
    monkeypatch.setattr(VisualMotionDetector,'analyze',lambda self,rgb:
        Observation(2.) if has_activity else Observation(quality='waiting_for_face'))
    settings=replace(Settings.from_env(),realtime_min_seconds=1.,realtime_decode_interval_seconds=.6)
    with TestClient(create_app(settings=settings,engine=engine)) as client:
        with client.websocket_connect('/v1/realtime') as ws:
            ws.send_json(dict(type='start',protocol=2,input_kind='mouth_roi',auto_endpoint=True))
            assert ws.receive_json()['auto_endpoint']
            for i in range(25):
                _,jpeg=cv2.imencode('.jpg',np.full((96,96,3),80+i*2,np.uint8))
                ws.send_bytes(b'LIP2'+struct.pack('>Id',i,i*120)+jpeg.tobytes())
                while ws.receive_json()['type']!='ack': pass
                time.sleep(.055)
            ws.send_json(dict(type='stop'))
            while True:
                final=ws.receive_json()
                if final['type']=='session_final':break
            assert final['transcript']==''
            assert final['incomplete']==has_activity
            assert (engine.calls>0)==has_activity


def test_empty_partial_does_not_interrupt_speaker_but_empty_endpoint_is_reported(monkeypatch):
    from app.services.engine import EngineResult
    class BlankEngine(TimedEngine):
        def transcribe_frames(self,*args,**kwargs):
            return EngineResult(transcript='',num_frames=len(args[0]))
    monkeypatch.setattr(VisualMotionDetector,'load',lambda self:None)
    monkeypatch.setattr(VisualMotionDetector,'analyze',lambda self,rgb:Observation(2.))
    settings=replace(Settings.from_env(),realtime_min_seconds=1.,realtime_decode_interval_seconds=.6)
    with TestClient(create_app(settings=settings,engine=BlankEngine())) as client:
        with client.websocket_connect('/v1/realtime') as ws:
            ws.send_json(dict(type='start',protocol=2,input_kind='mouth_roi',auto_endpoint=True))
            assert ws.receive_json()['auto_endpoint']
            events=[]
            for i in range(25):
                _,jpeg=cv2.imencode('.jpg',np.full((96,96,3),80+i*2,np.uint8))
                ws.send_bytes(b'LIP2'+struct.pack('>Id',i,i*120)+jpeg.tobytes())
                while True:
                    e=ws.receive_json();events.append(e)
                    if e['type']=='ack':break
                time.sleep(.055)
            assert not any(e['type']=='notice' for e in events)
            ws.send_json(dict(type='stop'))
            while not events or events[-1]['type']!='session_final':events.append(ws.receive_json())
            assert any(e['type']=='telemetry' and e.get('code')=='empty_hypothesis' for e in events)
            assert any(e['type']=='notice' and e.get('code')=='empty_hypothesis' for e in events)
            assert events[-1]['incomplete'] and events[-1]['transcript']==''
