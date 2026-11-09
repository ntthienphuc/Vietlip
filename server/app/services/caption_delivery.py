"""Bounded caption receipts; diagnostics only, never alter caption decisions."""

from collections import OrderedDict
import math
import time


class CaptionDelivery:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.sequence = 0
        self.pending = OrderedDict()
        self.last_text = ""

    def stamp(self, payload):
        if payload.get("type") not in ("partial", "segment_final"):
            return
        self.sequence += 1
        payload["caption_event_id"] = self.sequence
        self.pending[self.sequence] = dict(
            sent=self.clock(),
            type=payload["type"],
            turn_id=payload.get("turn_id"),
            window_end=payload.get("window_end"),
            capture_clock_seconds=payload.get("capture_clock_seconds"),
            caption_changed=payload.get("transcript", "") != self.last_text,
        )
        self.last_text = payload.get("transcript", "")
        while len(self.pending) > 64:
            self.pending.popitem(last=False)

    def acknowledge(self, message):
        event_id = message.get("caption_event_id")
        paint_ms = message.get("receive_to_frame_ms")
        if (
            type(event_id) is not int
            or type(paint_ms) not in (int, float)
            or not math.isfinite(paint_ms)
            or not 0 <= paint_ms <= 60000
        ):
            return None
        sent = self.pending.pop(event_id, None)
        if sent is None:
            return None
        elapsed_ms = (self.clock() - sent.pop("sent")) * 1000
        # Receipt cannot arrive before the client's reported frame callback.
        if paint_ms > elapsed_ms + 20:
            return None
        source, end = sent.pop("capture_clock_seconds"), sent["window_end"]
        tail = None if source is None or end is None else (source - end) * 1000 + elapsed_ms
        return dict(
            type="caption_render_ack",
            caption_event_id=event_id,
            caption_type=sent.pop("type"),
            **sent,
            receive_to_flutter_frame_ms=round(paint_ms, 3),
            server_send_to_render_ack_ms=round(elapsed_ms, 3),
            window_end_to_render_ack_ms=None if tail is None else round(tail, 3),
            timing_scope="Flutter post-frame receipt; includes return network delay; visual padded endpoint, not acoustic end or physical display scanout",
        )
