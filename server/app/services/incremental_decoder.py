"""Inference-only KV cache for the native pre-normalized Transformer decoder.

Encoder memory is still full-context. Each beam owns self-attention K/V states;
source projections are shared for exactly one BatchBeamSearch invocation.
"""

import torch
from torch.nn import functional as F
from espnet.nets.scorer_interface import BatchScorerInterface


class IncrementalDecoderScorer(BatchScorerInterface):
    def __init__(self, decoder):
        self.decoder = decoder
        if not decoder.normalize_before or any(
            not layer.normalize_before or layer.concat_after for layer in decoder.decoders
        ):
            raise ValueError("KV adapter requires pre-normalized, non-concatenating layers")
        self.source = None

    @staticmethod
    def _split(attention, x):
        return x.view(x.shape[0], -1, attention.h, attention.d_k).transpose(1, 2)

    def init_state(self, x):
        if self.decoder.training:
            raise RuntimeError("KV decoder is inference-only")
        memory = x.unsqueeze(0)
        self.source = [
            (
                self._split(layer.src_attn, layer.src_attn.linear_k(memory)),
                self._split(layer.src_attn, layer.src_attn.linear_v(memory)),
            )
            for layer in self.decoder.decoders
        ]
        return None

    def batch_init_state(self, x):
        return self.init_state(x)

    @staticmethod
    def _attend(attention, query, key, value):
        q = IncrementalDecoderScorer._split(attention, attention.linear_q(query))
        # The query is the newest token. Every cached position is in its past;
        # no triangular mask or future token is present.
        output = F.scaled_dot_product_attention(q, key, value, dropout_p=0.0)
        output = output.transpose(1, 2).contiguous().view(query.shape[0], 1, -1)
        return attention.linear_out(output)

    def batch_score(self, ys, states, xs):
        if self.source is None:
            self.init_state(xs[0])
        batch, length = ys.shape
        positional = self.decoder.embed[1]
        # Native PositionalEncoding starts with 5000 positions; this only grows
        # the table when needed and preserves the module's own scale convention.
        embedding = self.decoder.embed[0](ys[:, -1:])
        if (
            positional.pe is None
            or positional.pe.shape[1] < length
            or positional.pe.device != embedding.device
            or positional.pe.dtype != embedding.dtype
        ):
            positional.extend_pe(embedding.new_zeros(1, length, embedding.shape[-1]))
        x = embedding * positional.xscale + positional.pe[:, length - 1 : length].to(embedding)
        caches = []
        for i, layer in enumerate(self.decoder.decoders):
            normalized = layer.norm1(x)
            key = self._split(layer.self_attn, layer.self_attn.linear_k(normalized))
            value = self._split(layer.self_attn, layer.self_attn.linear_v(normalized))
            if states[0] is not None:
                key = torch.cat((torch.stack([state[i][0] for state in states]), key), dim=2)
                value = torch.cat((torch.stack([state[i][1] for state in states]), value), dim=2)
            caches.append((key, value))
            x = x + self._attend(layer.self_attn, normalized, key, value)
            source_key, source_value = self.source[i]
            x = x + self._attend(
                layer.src_attn,
                layer.norm2(x),
                source_key.expand(batch, -1, -1, -1),
                source_value.expand(batch, -1, -1, -1),
            )
            x = x + layer.feed_forward(layer.norm3(x))
        scores = torch.log_softmax(
            self.decoder.output_layer(self.decoder.after_norm(x[:, -1])), dim=-1
        )
        next_states = [[(key[b], value[b]) for key, value in caches] for b in range(batch)]
        return scores, next_states

    def score(self, y, state, x):
        scores, states = self.batch_score(y[None], [state], x[None])
        return scores[0], states[0]
