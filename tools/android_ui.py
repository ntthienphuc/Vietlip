"""Small Android QA helper; actions are grounded in a freshly dumped UI tree.

ADB controls installation/UI only. It does not configure an inference tunnel.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--tap", help="Exact current accessibility label or text")
    p.add_argument("--input", help="Text to enter in the only visible editable field")
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def adb(*parts):
        return subprocess.check_output(["adb", *parts], timeout=30)

    def snapshot(suffix):
        status = adb("shell", "uiautomator", "dump", "/sdcard/vietlip-ui.xml")
        if b"dumped to:" not in status:
            raise RuntimeError("No fresh Android UI dump")
        raw = adb("exec-out", "cat", "/sdcard/vietlip-ui.xml")
        args.output.with_name(args.output.name+suffix+".xml").write_bytes(raw)
        return list(ET.fromstring(raw).iter("node"))

    nodes = snapshot("-before")
    if args.tap or args.input is not None:
        matches = [n for n in nodes if (n.get("class") == "android.widget.EditText"
                   if args.input is not None else args.tap in (
                       (n.get("text") or "").split("\n")[0],
                       (n.get("content-desc") or "").split("\n")[0]))]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one matching visible node; found {len(matches)}")
        node = matches[0]
        x1,y1,x2,y2 = map(int,re.findall(r"\d+",node.get("bounds")))
        adb("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2))
        if args.input is not None:
            adb("shell", "input", "keyevent", "123")
            adb("shell", "input", "keyevent", *(["67"] * max(1, len(node.get("text", "")))))
            adb("shell", "input", "text", args.input)
            adb("shell", "input", "keyevent", "4")
        nodes = snapshot("-after")
    args.output.with_suffix(".png").write_bytes(adb("exec-out", "screencap", "-p"))
    for n in nodes:
        label=n.get("content-desc") or n.get("text")
        if label:
            print(label)


if __name__ == "__main__":
    main()
