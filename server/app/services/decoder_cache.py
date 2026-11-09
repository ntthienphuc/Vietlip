"""Request-scoped cross-attention projections; no cache crosses an utterance.

All beam hypotheses attend to identical encoder memory. Project its keys and
values once per decoder layer instead of once per token and beam. This preserves
full-context attention; it does not turn the encoder into a causal network.
"""

from contextlib import contextmanager
from types import MethodType


@contextmanager
def cached_cross_attention(decoder, enabled=True):
    if not enabled:
        yield
        return
    original = []
    try:
        for layer in decoder.decoders:
            attention = layer.src_attn
            original.append((attention, attention.forward_qkv))
            state = {}

            def project(self, query, key, value, _state=state):
                batch = query.shape[0]
                q = self.linear_q(query).view(batch, -1, self.h, self.d_k).transpose(1, 2)
                if not _state:
                    # BatchBeamSearch expands the same encoded utterance across
                    # beam rows; cache only that common source sequence.
                    _state["k"] = (
                        self.linear_k(key[:1]).view(1, -1, self.h, self.d_k).transpose(1, 2)
                    )
                    _state["v"] = (
                        self.linear_v(value[:1]).view(1, -1, self.h, self.d_k).transpose(1, 2)
                    )
                return (
                    q,
                    _state["k"].expand(batch, -1, -1, -1),
                    _state["v"].expand(batch, -1, -1, -1),
                )

            attention.forward_qkv = MethodType(project, attention)
        yield
    finally:
        for attention, method in original:
            attention.forward_qkv = method
