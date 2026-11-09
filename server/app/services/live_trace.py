"""Optional, size-bounded local caption event trace for application diagnostics."""

import json
import logging
import os
from pathlib import Path
import time
from uuid import uuid4

logger = logging.getLogger(__name__)


class LiveTrace:
    def __init__(self):
        self.started = time.monotonic()
        self.file = None
        self.bytes = 0
        directory = os.environ.get("LIP_REALTIME_TRACE_DIR")
        if directory:
            try:
                root = Path(directory)
                root.mkdir(parents=True, exist_ok=True)
                self.file = (root / f"live-{uuid4().hex}.jsonl").open("x", encoding="utf8")
            except OSError:
                logger.warning("Could not create local live trace", exc_info=True)

    def record(self, event):
        if self.file is None or event.get("type") in {"ack", "telemetry"}:
            return
        record = dict(
            event,
            wall_seconds=round(time.monotonic() - self.started, 4),
            received_at_unix=time.time(),
        )
        line = json.dumps(record, ensure_ascii=False) + "\n"
        self.bytes += len(line.encode("utf8"))
        if self.bytes > 4 * 1024 * 1024:
            self.close()
            return
        try:
            self.file.write(line)
            self.file.flush()
        except OSError:
            logger.warning("Could not write local live trace", exc_info=True)
            self.close()

    def close(self):
        if self.file is not None:
            try:
                self.file.close()
            except OSError:
                pass
            self.file = None
