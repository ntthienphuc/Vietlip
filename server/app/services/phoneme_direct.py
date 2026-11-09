"""CTC prefix beam search through a Vietnamese pronunciation trie.

Produces text without any SO17 text candidates. A small count LM resolves
homophones; frame posteriors are always supplied by the visual phoneme head.
"""

from __future__ import annotations
from functools import lru_cache
import hashlib
import heapq
import json
import math
from pathlib import Path
import time
import numpy as np
import torch
from experiments.phoneme_probe.model import PhonemeHead
from .word_alignment import align_words

NEG = -float("inf")


def logadd(a, b):
    if a == NEG:
        return b
    if b == NEG:
        return a
    high, low = (a, b) if a >= b else (b, a)
    return high + math.log1p(math.exp(low - high))


class PronunciationDecoder:
    def __init__(
        self,
        resource,
        tokens,
        *,
        branch="segmental",
        lm_weight=0.5,
        word_score=0.0,
        beam=48,
        token_beam=12,
    ):
        self.tokens = tokens
        self.lookup = {p: i for i, p in enumerate(tokens)}
        self.boundary = self.lookup["|"]
        self.lm_weight = lm_weight
        self.word_score = word_score
        self.beam = beam
        self.token_beam = token_beam
        self.entries = [r for r in resource["entries"] if all(p in self.lookup for p in r[branch])]
        self.words = [r["word"] for r in self.entries]
        self.phones = [tuple(self.lookup[p] for p in r[branch]) for r in self.entries]
        self.children = [{}]
        self.ends = [[]]
        self.paths = [()]
        for i, phones in enumerate(self.phones):
            node = 0
            for phone in phones:
                if phone not in self.children[node]:
                    self.children[node][phone] = len(self.children)
                    self.children.append({})
                    self.ends.append([])
                    self.paths.append(self.paths[node] + (phone,))
                node = self.children[node][phone]
            self.ends[node].append(i)
        self.uni = resource["unigram"]
        self.bi = resource["bigram"]
        self.tri = resource["trigram"]
        self.contexts = resource["contexts"]
        self.total = sum(self.uni.values())
        self.vocab = len(self.entries)

    @lru_cache(maxsize=200000)
    def language_score(self, history, word):
        text = self.words[word]
        a, b = (["<s>", "<s>"] + [self.words[i] for i in history])[-2:]
        # Additive unigram + interpolated count bigram/trigram, all TRAIN only.
        p1 = (self.uni.get(text, 0) + 0.1) / (self.total + 0.1 * self.vocab)
        count_b = self.uni.get(b, 0) if b != "<s>" else self.contexts.get("<s>\t<s>", 0)
        p2 = (self.bi.get(b + "\t" + text, 0) + 5 * p1) / (count_b + 5)
        p3 = (self.tri.get(a + "\t" + b + "\t" + text, 0) + 5 * p2) / (
            self.contexts.get(a + "\t" + b, 0) + 5
        )
        return math.log(max(p3, 1e-20))

    def decode(self, logp, nbest=4, fps=25):
        if logp.ndim != 2 or len(logp) == 0 or not np.isfinite(logp).all():
            raise ValueError("Expected finite nonempty T x phoneme log probabilities")
        # State: completed word IDs + unfinished pronunciation-trie node.
        # Separate blank/nonblank probability implements CTC repeat semantics.
        active = {((), 0): (0.0, NEG)}
        for frame in logp:
            top = np.argpartition(frame, -min(self.token_beam, len(frame)))[-self.token_beam :]
            allowed = set(int(i) for i in top if i)
            following = {}

            def update(key, pb=NEG, pnb=NEG):
                old = following.get(key, (NEG, NEG))
                following[key] = (logadd(old[0], pb), logadd(old[1], pnb))

            for (history, node), (pb, pnb) in active.items():
                total = logadd(pb, pnb)
                last = self.paths[node][-1] if node else (self.boundary if history else -1)
                update((history, node), pb=total + float(frame[0]))
                if last > 0:
                    update((history, node), pnb=pnb + float(frame[last]))
                for token, child in self.children[node].items():
                    if token not in allowed:
                        continue
                    value = (pb if token == last else total) + float(frame[token])
                    if value == NEG:
                        continue
                    if self.ends[child]:
                        context = history[-2:]
                        for word in self.ends[child]:
                            score = (
                                value
                                + self.lm_weight * self.language_score(context, word)
                                + self.word_score
                            )
                            update((history + (word,), 0), pnb=score)
                    else:
                        update((history, child), pnb=value)
            active = dict(heapq.nlargest(self.beam, following.items(), key=lambda x: logadd(*x[1])))
        completed = {}
        for (history, node), probability in active.items():
            score = logadd(*probability)
            trailing = self.paths[node]
            if history:
                completed.setdefault(history, []).append((score, trailing, False))
            # A complete syllable at the right edge may lack its final | frame.
            leaf = self.children[node].get(self.boundary)
            if leaf is not None:
                for word in self.ends[leaf]:
                    value = (
                        score
                        + self.lm_weight * self.language_score(history[-2:], word)
                        + self.word_score
                    )
                    completed.setdefault(history + (word,), []).append((value, (), True))
        candidates = []
        for history, paths in completed.items():
            score, trailing, no_boundary = max(paths, key=lambda x: x[0])
            candidates.append((score, history, trailing, no_boundary))
        candidates = heapq.nlargest(nbest, candidates)
        output = []
        for score, history, trailing, no_boundary in candidates:
            ids = [p for word in history for p in self.phones[word]]
            if no_boundary:
                ids = ids[:-1]
            aligned = self._align(logp, ids + list(trailing), history, fps)
            if not aligned:
                continue
            output.append(
                dict(
                    text=" ".join(self.words[i] for i in history),
                    raw_score=score,
                    words=aligned,
                    source="direct_phoneme_ctc",
                    phoneme_ids=ids,
                )
            )
        return output

    def _align(self, logp, ids, history, fps):
        # Reuse the app's CTC Viterbi aligner with per-syllable token grouping.
        tokens = [str(i) for i in range(len(self.tokens))]
        # Boundary ends the previous word; group the token before it, not after it.
        # Obtain per-token spans by marking every predicted symbol as a new group.
        spans = align_words(logp, ids, ["▁" + t for t in tokens], fps)
        if len(spans) != len(ids):
            return []
        result = []
        offset = 0
        for word in history:
            length = len(self.phones[word])
            available = min(length, len(spans) - offset)
            if available < length - 1:
                return []
            selected = spans[offset : offset + available]
            result.append(
                dict(text=self.words[word], start=selected[0]["start"], end=selected[-1]["end"])
            )
            offset += length
        return result


class DirectPhonemeDecoder:
    def __init__(self, head_path, lexicon_path, visual_checkpoint, device, config):
        self.device = device
        self.config = dict(config)
        payload = torch.load(head_path, map_location="cpu", weights_only=True)
        expected = payload["feature_identity"]["checkpoint_sha256"]
        if hashlib.sha256(Path(visual_checkpoint).read_bytes()).hexdigest() != expected:
            raise ValueError("Direct phoneme head visual checkpoint mismatch")
        self.head_sha256 = hashlib.sha256(Path(head_path).read_bytes()).hexdigest()
        self.lexicon_sha256 = hashlib.sha256(Path(lexicon_path).read_bytes()).hexdigest()
        self.model = PhonemeHead(**payload["config"]).to(device).eval()
        self.model.load_state_dict(payload["state_dict"], strict=True)
        self.branch = self.config.pop("branch", "segmental")
        self.decoder = PronunciationDecoder(
            json.loads(Path(lexicon_path).read_text(encoding="utf8")),
            payload[self.branch + "_tokens"],
            branch=self.branch,
            **self.config,
        )

    def decode(self, encoded):
        started = time.perf_counter()
        with torch.inference_mode():
            logits = self.model(encoded[None].to(self.device).float())[
                0 if self.branch == "segmental" else 1
            ][0]
            logp = logits.log_softmax(-1).cpu().numpy()
        results = self.decoder.decode(logp)
        return results, dict(
            enabled=True,
            mode="direct_phoneme_ctc",
            branch=self.branch,
            head_sha256=self.head_sha256,
            lexicon_sha256=self.lexicon_sha256,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            returned_candidates=len(results),
            scores_are_calibrated_probabilities=False,
        )
