"""Bounded stateless face-detection cache for overlapping live windows."""

from collections import OrderedDict
import hashlib


class LandmarkCache:
    def __init__(self, capacity=512):
        self.capacity = capacity
        self.entries = OrderedDict()
        self.hits = 0
        self.misses = 0

    def detect(self, frames, detector, backend, name):
        result = []
        for frame in frames:
            key = (
                name,
                frame.shape,
                hashlib.blake2b(memoryview(frame).cast("B"), digest_size=16).digest(),
            )
            if key in self.entries:
                self.hits += 1
                value = self.entries.pop(key)
            else:
                self.misses += 1
                value = detector.detect([frame], backend)[0]
            self.entries[key] = value
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)
            result.append(None if value is None else value.copy())
        return result
