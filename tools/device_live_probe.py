"""Observe the installed Android app through ADB; retain local test evidence.

This reads UI state without tapping controls. It never reads microphone audio.
Run while a participant uses the app, then compare the saved captions to the
participant's actual utterances. UI sampling is not precise endpoint timing.
"""

import argparse
import json
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--seconds", type=float, default=90)
    parser.add_argument("--interval", type=float, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)

    def adb(*command):
        return subprocess.run(
            [args.adb, "-s", args.serial, *command],
            capture_output=True, timeout=20, check=True,
        ).stdout

    records = []
    started = time.monotonic()
    try:
        while time.monotonic() - started < args.seconds:
            tick = time.monotonic()
            stamp = datetime.now(timezone.utc).isoformat()
            adb("shell", "uiautomator", "dump", "/sdcard/lip-probe-ui.xml")
            xml = adb("exec-out", "cat", "/sdcard/lip-probe-ui.xml")
            items = []
            for node in ET.fromstring(xml).iter("node"):
                if node.get("package") != "vn.lipread.lip_reader":
                    continue
                value = node.get("content-desc") or node.get("text")
                if value:
                    items.append(value)
            index = len(records)
            (args.output / f"ui-{index:03d}.xml").write_bytes(xml)
            record = {"utc": stamp, "elapsed_s": round(tick - started, 2), "items": items}
            records.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
            (args.output / "observations.json").write_text(
                json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            time.sleep(max(0, args.interval - (time.monotonic() - tick)))
    finally:
        for name, command in {
            "app-logcat.txt": ("logcat", "-d", "-v", "threadtime", "-s", "flutter", "LipNativeFrames", "AndroidRuntime"),
            "camera.txt": ("shell", "dumpsys", "media.camera"),
            "battery.txt": ("shell", "dumpsys", "battery"),
            "package.txt": ("shell", "dumpsys", "package", "vn.lipread.lip_reader"),
        }.items():
            try:
                (args.output / name).write_bytes(adb(*command))
            except subprocess.SubprocessError as error:
                print(f"Could not save {name}: {error}", flush=True)


if __name__ == "__main__":
    main()
