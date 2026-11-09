"""Timestamped bounded camera storage and word ownership for rolling windows."""

from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import math
import struct


@dataclass(frozen=True)
class Frame:
    sequence: int
    seconds: float
    jpeg: bytes


def unpack_frame(packet: bytes) -> Frame:
    if len(packet) < 20 or packet[:4] != b"LIP2":
        raise ValueError("Expected LIP2 timestamped JPEG packet")
    sequence, milliseconds = struct.unpack(">Id", packet[4:16])
    if not math.isfinite(milliseconds) or milliseconds < 0:
        raise ValueError("Invalid capture timestamp")
    if packet[16:18] != b"\xff\xd8":
        raise ValueError("Expected JPEG image")
    return Frame(sequence, milliseconds / 1000, packet[16:])


class FrameBuffer:
    def __init__(self, seconds=8.0, max_bytes=24 * 1024 * 1024, max_frames=300):
        self.frames = deque()
        self.seconds = seconds
        self.max_bytes = max_bytes
        self.max_frames = max_frames
        self.bytes = 0
        self.dropped = 0
        self.last_sequence = -1
        self.last_time = -1.0
        self.gaps = 0

    def add(self, frame):
        if frame.sequence <= self.last_sequence or frame.seconds <= self.last_time:
            raise ValueError("Camera frames must have increasing sequence and timestamps")
        if self.last_time >= 0 and frame.seconds - self.last_time > 0.5:
            self.gaps += 1
        self.last_sequence = frame.sequence
        self.last_time = frame.seconds
        self.frames.append(frame)
        self.bytes += len(frame.jpeg)
        while self.frames and (
            self.bytes > self.max_bytes
            or len(self.frames) > self.max_frames
            or frame.seconds - self.frames[0].seconds > self.seconds
        ):
            self.bytes -= len(self.frames.popleft().jpeg)
            self.dropped += 1

    def snapshot(self, duration, fps, *, after=0.0, until=None):
        if not self.frames:
            return [], 0.0, 0.0
        frames = [
            f
            for f in self.frames
            if f.seconds >= after - 1e-6 and (until is None or f.seconds < until - 1e-6)
        ]
        if not frames:
            return [], after, after
        end = frames[-1].seconds
        # Keep a session-wide sampling grid. Re-anchoring every window to a
        # jittered last camera frame changes the selected images in its overlap,
        # invalidating landmark cache entries and moving word alignments.
        grid_end = math.floor(end * fps + 1e-6) / fps
        start = max(frames[0].seconds, grid_end - duration + 1 / fps)
        # Never fabricate lip movement through camera/network outages.
        for a, b in zip(frames, frames[1:]):
            if b.seconds - a.seconds > 0.5:
                start = max(start, b.seconds)
        frames = [f for f in frames if f.seconds >= start - 1 / fps]
        start = math.ceil(max(start, frames[0].seconds) * fps - 1e-6) / fps
        if grid_end < start - 1e-6:
            frame = frames[-1]
            return [frame.jpeg], frame.seconds, frame.seconds + 1 / fps
        count = max(1, int(round((grid_end - start) * fps)) + 1)
        samples = []
        cursor = 0
        for i in range(count):
            when = start + i / fps
            while cursor + 1 < len(frames) and abs(frames[cursor + 1].seconds - when) <= abs(
                frames[cursor].seconds - when
            ):
                cursor += 1
            samples.append(frames[cursor].jpeg)
        return samples, start, start + count / fps


class WordTimeline:
    """Commit only time-owned words; repeated spoken words retain distinct times."""

    def __init__(self):
        self.committed = []
        self.previous = []
        self.frontier = -1.0
        self.gaps = []

    @property
    def text(self):
        return " ".join(w["text"] for w in self.committed)

    def update(self, words, start, end, *, final=False, right_context=1.0):
        absolute = [dict(w, start=w["start"] + start, end=w["end"] + start) for w in words]
        if start > self.frontier + 0.5 and self.frontier >= 0:
            self.gaps.append({"start": self.frontier, "end": start})
        remaining = [w for w in absolute if (w["start"] + w["end"]) / 2 > self.frontier + 0.02]
        if self.committed:
            last = self.committed[-1]
            matches = [
                (abs((w["start"] + w["end"]) / 2 - self.frontier), i)
                for i, w in enumerate(absolute)
                if w["text"] == last["text"]
                and abs((w["start"] + w["end"]) / 2 - self.frontier) < 0.45
            ]
            if matches:
                _, matched = min(matches)
                remaining = absolute[matched + 1 :]
        cutoff = end if final else end - right_context
        accepted = []
        for word in remaining:
            # Output ownership follows capture time with bounded right context.
            # Requiring identical prefixes indefinitely loses entire spans when
            # the offline decoder revises an earlier word as a window slides.
            if word["end"] > cutoff:
                break
            accepted.append(word)
        self.committed.extend(accepted)
        if accepted:
            self.frontier = (accepted[-1]["start"] + accepted[-1]["end"]) / 2
        self.previous = absolute
        pending = remaining[len(accepted) :]
        return {
            "transcript": " ".join(w["text"] for w in self.committed + pending),
            "stable_transcript": self.text,
            "provisional_transcript": " ".join(w["text"] for w in pending),
        }
