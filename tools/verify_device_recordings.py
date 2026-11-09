"""Pull explicitly named app recordings and verify playable, nonempty audio."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--ffmpeg-dir', type=Path, required=True)
    parser.add_argument('--recording', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for name in args.recording:
        if not re.fullmatch(r'lip_\d+\.mp4', name):
            raise ValueError('Expected an exact app recording basename')
        target = args.output / name
        remote = 'app_flutter/captures/' + name
        command = [args.adb, '-s', args.serial, 'exec-out', 'run-as',
                   'vn.lipread.lip_reader', 'cat', remote]
        with target.open('wb') as stream:
            subprocess.run(command, stdout=stream, check=True, timeout=60)
        info = json.loads(subprocess.check_output([
            str(args.ffmpeg_dir / 'ffprobe.exe'), '-v', 'error',
            '-show_streams', '-show_format', '-of', 'json', str(target)], timeout=20))
        (args.output / (name + '.probe.json')).write_text(
            json.dumps(info, indent=2), encoding='utf8')
        decoded = subprocess.check_output([
            str(args.ffmpeg_dir / 'ffmpeg.exe'), '-v', 'error', '-i', str(target),
            '-map', '0:a:0', '-ac', '1', '-ar', '16000', '-f', 'f32le', 'pipe:1'], timeout=30)
        pcm = np.frombuffer(decoded, dtype=np.float32)
        streams = [{k:s.get(k) for k in ['codec_type', 'codec_name', 'width', 'height',
            'sample_rate', 'channels', 'duration', 'avg_frame_rate']} for s in info['streams']]
        with target.open('rb') as source:
            sha = hashlib.file_digest(source, 'sha256').hexdigest()
        result = {'file':name, 'device_serial':args.serial, 'device_path':remote,
            'sha256':sha, 'streams':streams, 'audio_samples_16khz':len(pcm),
            'audio_peak':float(np.abs(pcm).max()),
            'audio_rms':float(np.sqrt(np.mean(pcm**2))),
            'audio_nonzero_samples':int(np.count_nonzero(pcm)),
            'scope':'Audio track and signal verified; not speech intelligibility or lip-reading accuracy.'}
        assert any(s['codec_type'] == 'audio' and s['codec_name'] == 'aac' for s in streams)
        assert len(pcm) > 16000 and result['audio_nonzero_samples'] > 0
        records.append(result)
    (args.output / 'RECORDING_VERIFICATION.json').write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
