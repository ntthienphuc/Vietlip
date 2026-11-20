"""Bounded start/stop verification on an explicitly selected Android device."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb', required=True)
    p.add_argument('--serial', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--rounds', type=int, default=4)
    p.add_argument('--server-log', type=Path,
                   help='Local VietLip server log for an isolated test with a single live client')
    args = p.parse_args()
    args.output.mkdir(exist_ok=False, parents=True)
    records = []
    def adb(*command):
        return subprocess.check_output([args.adb, '-s', args.serial, *command], timeout=20)
    def ui(name):
        for attempt in range(3):
            status = adb('shell', 'uiautomator', 'dump', '/sdcard/lip-connection-ui.xml')
            if b'dumped to:' in status:
                break
            time.sleep(.5)
        else:
            raise RuntimeError('Could not read current UI; refusing stale XML')
        data = adb('exec-out', 'cat', '/sdcard/lip-connection-ui.xml')
        (args.output / f'{name}.xml').write_bytes(data)
        return [n for n in ET.fromstring(data).iter('node')
                if n.get('package') == 'vn.lipread.lip_reader']
    def tap(nodes, text):
        node = next(n for n in nodes if n.get('content-desc') == text)
        x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
        adb('shell', 'input', 'tap', str((x1+x2)//2), str((y1+y2)//2))
    in_live = False
    try:
        for i in range(args.rounds):
            offset = args.server_log.stat().st_size if args.server_log else None
            adb('shell', 'input', 'swipe', '360', '350', '360', '1150', '350')
            nodes = ui(f'{i+1}-ready')
            started = time.monotonic()
            tap(nodes, 'Bắt đầu đọc môi')
            in_live = True
            time.sleep(2)
            live = ui(f'{i+1}-live')
            labels = [n.get('content-desc', '') for n in live]
            if 'Kết thúc phiên' not in labels:
                raise RuntimeError(f'Round {i+1}: did not enter live: {labels}')
            observed = time.monotonic() - started
            time.sleep(3)
            live = ui(f'{i+1}-flow')
            labels = [n.get('content-desc', '') for n in live]
            if any('Mất kết nối' in s or 'Luồng hình bị lỗi' in s for s in labels):
                raise RuntimeError(f'Round {i+1}: stream failed: {labels}')
            (args.output/f'{i+1}-live.png').write_bytes(adb('exec-out','screencap','-p'))
            fps = []
            if 'Thông tin phiên' in labels:
                tap(live, 'Thông tin phiên')
                details = ui(f'{i+1}-details')
                fps = [n.get('content-desc', '') for n in details
                       if 'khung hình/giây' in n.get('content-desc', '')]
                adb('shell', 'input', 'keyevent', '4')
                live = ui(f'{i+1}-resumed')
            tap(live, 'Kết thúc phiên')
            in_live = False
            stopped = ui(f'{i+1}-stopped')
            if not any(n.get('content-desc') == 'Bắt đầu đọc môi' for n in stopped):
                adb('shell', 'input', 'swipe', '360', '350', '360', '1150', '350')
                stopped = ui(f'{i+1}-settled')
            if not any(n.get('content-desc') == 'Bắt đầu đọc môi' for n in stopped):
                raise RuntimeError(f'Round {i+1}: stop did not settle')
            measured = [int(n) for label in fps for n in re.findall(r'Camera: (\d+) khung hình/giây', label)]
            if measured and min(measured) < 20:
                raise RuntimeError(f'Round {i+1}: low reported camera FPS: {measured}')
            frames = []
            if offset is not None:
                with args.server_log.open('rb') as log:
                    log.seek(offset)
                    frames = re.findall(rb'Auto live frames=(\d+)', log.read())
                if len(frames) != 1 or int(frames[0]) < 20:
                    raise RuntimeError('Expected one new server session with at least 20 received frames')
            if not measured and not frames:
                raise RuntimeError('This UI hides FPS. Supply --server-log to verify frame delivery.')
            records.append(dict(round=i+1, first_ui_observed_seconds=round(observed, 3),
                                camera_fps=measured, received_frames=int(frames[0]) if frames else None))
            (args.output/'RESULTS.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
            print(json.dumps(records[-1],ensure_ascii=False),flush=True)
    finally:
        if in_live:
            current = ui('cleanup')
            if any(n.get('content-desc') == 'Kết thúc phiên' for n in current):
                tap(current, 'Kết thúc phiên')
        (args.output/'device.log').write_bytes(adb('logcat','-d','-v','time',
            'flutter:I','LipNativeFrames:I','AndroidRuntime:E','*:S'))


if __name__ == '__main__':
    main()
