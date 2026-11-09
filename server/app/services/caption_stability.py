"""Causal local agreement for captions from overlapping offline decodes.

Only a prefix supported by distinct successive windows becomes visible early.
At an endpoint, the last full-context decode owns the remaining words. No
reference text, vocabulary prompts, language model or audio enters this policy.
"""

from .streaming_buffer import WordTimeline


class AgreementTimeline(WordTimeline):
    def __init__(self):
        super().__init__()
        self.last_window = None
        self.pending = []

    def _remaining(self, words):
        remaining = [w for w in words if (w["start"] + w["end"]) / 2 > self.frontier + 0.02]
        if self.committed:
            last = self.committed[-1]
            matches = [
                (abs((w["start"] + w["end"]) / 2 - self.frontier), i)
                for i, w in enumerate(words)
                if w["text"] == last["text"]
                and abs((w["start"] + w["end"]) / 2 - self.frontier) < 0.45
            ]
            if matches:
                remaining = words[min(matches)[1] + 1 :]
            else:
                # A revised token may occupy the same CTC onset while its end
                # moves by one or two frames. Midpoint-only ownership would
                # append both spellings (e.g. "lấy lái") for one spoken slot.
                # Require both an onset match and actual interval overlap;
                # adjacent repeated words must remain distinct.
                occupied = [
                    (abs(w["start"] - last["start"]), i)
                    for i, w in enumerate(words)
                    if abs(w["start"] - last["start"]) <= 0.040001
                    and min(w["end"], last["end"]) - max(w["start"], last["start"]) > 0.000001
                    and abs((w["start"] + w["end"]) / 2 - self.frontier) <= 0.12
                ]
                if occupied:
                    remaining = words[min(occupied)[1] + 1 :]
        return remaining

    def _commit(self, words):
        self.committed.extend(words)
        if words:
            self.frontier = (words[-1]["start"] + words[-1]["end"]) / 2

    def discard_pending(self):
        """An unavailable decode breaks agreement; keep only visible captions."""
        self.previous = []
        self.pending = []
        self.last_window = None

    def update(self, words, start, end, *, final=False, right_context=1.0):
        absolute = [dict(w, start=w["start"] + start, end=w["end"] + start) for w in words]
        # A sliding window must not discard an unresolved prefix that has left
        # its field of view. Preserve it from the preceding decode, explicitly
        # distinguish this bounded-memory fallback from agreement in diagnostics.
        previous = self._remaining(self.previous)
        expired = [w for w in previous if (w["start"] + w["end"]) / 2 < start - 0.02]
        self._commit(expired)
        remaining = self._remaining(absolute)
        previous = self._remaining(self.previous)
        accepted = []
        distinct = self.last_window != (start, end)
        for i, word in enumerate(remaining):
            if final:
                accepted.append(word)
                continue
            if word["end"] > end - right_context:
                break
            if (
                not distinct
                or i >= len(previous)
                or word["text"] != previous[i]["text"]
                or abs(
                    (word["start"] + word["end"] - previous[i]["start"] - previous[i]["end"]) / 2
                )
                > 0.65
            ):
                break
            accepted.append(word)
        self._commit(accepted)
        self.pending = remaining[len(accepted) :]
        self.previous = [] if final else absolute
        self.last_window = (start, end)
        # Single-pass guesses are retained for diagnostics, not rendered as
        # captions that disappear or change on the following window.
        return dict(
            transcript=self.text,
            stable_transcript=self.text,
            provisional_transcript="",
            unstable_transcript=" ".join(w["text"] for w in self.pending),
            stability_policy="local_agreement_2",
            agreement_committed_words=0 if final else len(accepted),
            endpoint_committed_words=len(accepted) if final else 0,
            expired_committed_words=len(expired),
        )
