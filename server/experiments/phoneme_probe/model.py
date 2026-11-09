"""Small parallel CTC heads, with a 160 ms local temporal receptive field."""
from __future__ import annotations
import torch
from torch import nn


class PhonemeHead(nn.Module):
    def __init__(self, input_dim, hidden_dim, segmental_size, tonal_size):
        super().__init__()
        self.config = dict(input_dim=input_dim, hidden_dim=hidden_dim,
                           segmental_size=segmental_size, tonal_size=tonal_size)
        self.norm = nn.LayerNorm(input_dim)
        self.project = nn.Linear(input_dim, hidden_dim)
        self.temporal = nn.Conv1d(hidden_dim, hidden_dim, 5, padding=2, groups=hidden_dim)
        self.dropout = nn.Dropout(.15)
        self.segmental = nn.Linear(hidden_dim, segmental_size)
        self.tonal = nn.Linear(hidden_dim, tonal_size)

    def forward(self, features, lengths=None):
        hidden = torch.nn.functional.gelu(self.project(self.norm(features)))
        mask = None
        if lengths is not None:
            mask = torch.arange(hidden.shape[1], device=hidden.device)[None, :] < lengths[:, None]
            hidden = hidden * mask.unsqueeze(-1)
        hidden = hidden + torch.nn.functional.gelu(self.temporal(hidden.transpose(1,2)).transpose(1,2))
        hidden = self.dropout(hidden)
        return self.segmental(hidden), self.tonal(hidden)


def greedy(logits, length, tokens):
    ids = logits[:length].argmax(-1).unique_consecutive().tolist()
    return [tokens[i] for i in ids if i != 0]


def phone_error(reference, hypothesis, *, include_boundary=False, tones=False):
    from .codec import edit_distance
    def retain(xs):
        return [p for p in xs if (include_boundary or p != '|') and (tones or not p.startswith('tone:'))]
    ref, hyp = retain(reference), retain(hypothesis)
    return edit_distance(ref, hyp), len(ref)
