"""Paced PC WebSocket replay of identical JPEG packets against configured servers.

Production endpoint scheduling is allowed to vary with actual runtime. Use the
separate frozen-window comparison for paired accuracy selection, not this run.
Client receipt is not a physical phone render receipt. Audio is never sent.
"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

import cv2
from websockets.asyncio.client import connect

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.visual_activity_probe.prepare import causal_frames
from experiments.visual_activity_probe.frozen_captions import digest, score, write


async def replay(url, packets):
    events = []
    ack = -1
    completed = asyncio.Event()
    start = time.perf_counter()
    async with connect(url, max_size=2**20, ping_timeout=60, open_timeout=15) as ws:
        await ws.send(
            json.dumps(dict(type="start", protocol=2, input_kind="raw_face", auto_endpoint=True))
        )
        ready = json.loads(await ws.recv())
        if ready["type"] != "ready":
            raise RuntimeError(str(ready))
        ready_ms = (time.perf_counter() - start) * 1000
        origin = time.perf_counter()

        async def receive():
            nonlocal ack
            async for payload in ws:
                e = json.loads(payload)
                if e["type"] == "ack":
                    if e["sequence"] != ack + 1:
                        raise ValueError("Missing/out-of-order frame ACK")
                    ack = e["sequence"]
                    continue
                events.append(dict(e, client_wall_seconds=time.perf_counter() - origin))
                if e["type"] == "error":
                    raise RuntimeError(str(e))
                if e["type"] == "session_final":
                    completed.set()
                    return
            if not completed.is_set():
                raise RuntimeError("WebSocket closed without session_final")

        receiver = asyncio.create_task(receive())
        late, inflight = [], []
        try:
            for i, packet in enumerate(packets):
                await asyncio.sleep(max(0, origin + i / 25 - time.perf_counter()))
                if receiver.done():
                    await receiver
                    raise RuntimeError("Session completed before source EOF")
                late.append(time.perf_counter() - origin - i / 25)
                inflight.append(i - ack - 1)
                if inflight[-1] >= 8:
                    raise RuntimeError("Backlog exceeded test limit; no frame dropping permitted")
                await ws.send(packet)
            await ws.send(json.dumps(dict(type="stop")))
            await asyncio.wait_for(receiver, 60)
        finally:
            if not receiver.done():
                receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
    if ack + 1 != len(packets):
        raise ValueError("Incomplete source acknowledgements")
    return dict(
        url=url,
        ready=ready,
        ready_ms=ready_ms,
        frames=len(packets),
        acknowledgements=ack + 1,
        peak_inflight=max(inflight),
        sender_max_lateness_ms=max(late) * 1000,
        events=events,
    )


async def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    packets = []
    hash_value = hashlib.sha256()
    for i, _, _, frame in causal_frames(args.video):
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            raise ValueError("JPEG encoding failed")
        packet = b"LIP2" + struct.pack(">Id", i, i * 40.0) + jpeg.tobytes()
        packets.append(packet)
        hash_value.update(struct.pack(">I", len(packet)))
        hash_value.update(packet)
    report = dict(
        scope=__doc__,
        video=str(args.video.resolve()),
        video_sha256=digest(args.video),
        packets_sha256=hash_value.hexdigest(),
        source_seconds=len(packets) / 25,
        audio_sent=False,
        runs=[],
    )
    write(args.output / "INPUT.json", {k: v for k, v in report.items() if k != "runs"})
    for i, url in enumerate(args.url):
        result = await replay(url, packets)
        # Text is used only after all visual predictions for this run exist.
        refs = json.loads(args.references.read_text(encoding="utf8"))["sentences"]
        final = result["events"][-1]
        result.update(**score(" ".join(refs), final["transcript"]))
        report["runs"].append(result)
        write(args.output / "RESULTS.json", report)
        print(
            json.dumps(
                dict(
                    run=i,
                    url=url,
                    frames=result["frames"],
                    word_errors=result["word_errors"],
                    reference_units=result["reference_units"],
                    ready_ms=result["ready_ms"],
                    events=len(result["events"]),
                ),
                ensure_ascii=False,
            ),
            flush=True,
        )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ("video", "references", "output"):
        p.add_argument("--" + flag, type=Path, required=True)
    p.add_argument("--url", nargs="+", required=True)
    asyncio.run(main(p.parse_args()))
