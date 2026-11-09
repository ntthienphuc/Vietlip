"""CPU PyTorch inference for PAZ's CNN2Plus1D_Light visual speech model.

Architecture adapted from Octavio Arriaga's PAZ (MIT); see vendor/paz/LICENSE.
Preserves Keras epsilon, channel normalization and half-pixel bilinear resize.
Weights are explicitly supplied; importing this module enables no live feature.
"""

from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


class ChannelNorm(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.norm = nn.LayerNorm(channels, eps=0.001)

    def forward(self, x):
        return self.norm(x.permute(0, 2, 3, 4, 1)).permute(0, 4, 1, 2, 3)


class Conv2Plus1(nn.Module):
    def __init__(self, incoming, outgoing, spatial=3):
        super().__init__()
        self.spatial = nn.Conv3d(
            incoming, outgoing, (1, spatial, spatial), padding=(0, spatial // 2, spatial // 2)
        )
        self.temporal = nn.Conv3d(outgoing, outgoing, (3, 1, 1), padding=(1, 0, 0))

    def forward(self, x):
        return self.temporal(self.spatial(x))


class Residual(nn.Module):
    def __init__(self, incoming, outgoing):
        super().__init__()
        self.first = Conv2Plus1(incoming, outgoing)
        self.first_norm = ChannelNorm(outgoing)
        self.second = Conv2Plus1(outgoing, outgoing)
        self.second_norm = ChannelNorm(outgoing)
        self.project = (
            nn.Sequential(nn.Conv3d(incoming, outgoing, 1), ChannelNorm(outgoing))
            if incoming != outgoing
            else nn.Identity()
        )

    def forward(self, x):
        y = F.relu(self.first_norm(self.first(x)))
        return self.project(x) + self.second_norm(self.second(y))


def resize_frames(x, size):
    n, c, t, h, w = x.shape
    frames = x.permute(0, 2, 1, 3, 4).reshape(n * t, c, h, w)
    frames = F.interpolate(frames, size=(size, size), mode="bilinear", align_corners=False)
    return frames.reshape(n, t, c, size, size).permute(0, 2, 1, 3, 4)


class CnnSpeechModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.stem = Conv2Plus1(3, 16, spatial=7)
        self.batch_norm = nn.BatchNorm3d(16, eps=0.001)
        self.blocks = nn.ModuleList([Residual(16, 16), Residual(16, 32), Residual(32, 64)])
        self.output = nn.Linear(64, 1)

    def forward(self, x):
        # Public input layout and intensity match the upstream RGB model exactly.
        x = x.permute(0, 4, 1, 2, 3)
        x = resize_frames(F.relu(self.batch_norm(self.stem(x))), 48)
        x = resize_frames(self.blocks[0](x), 24)
        x = resize_frames(self.blocks[1](x), 12)
        x = self.blocks[2](x).mean(dim=(2, 3, 4))
        return torch.sigmoid(self.output(x))

    @classmethod
    def from_npz(cls, path: Path):
        model = cls()
        expected = model.state_dict()
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != set(expected):
                raise ValueError("Unexpected visual activity model keys")
            weights = {}
            for name, target in expected.items():
                array = archive[name]
                if tuple(array.shape) != tuple(target.shape) or not np.isfinite(array).all():
                    raise ValueError(f"Invalid visual activity model tensor: {name}")
                weights[name] = torch.from_numpy(array.copy()).to(dtype=target.dtype)
        model.load_state_dict(weights, strict=True)
        return model.cpu().eval()

    @torch.inference_mode()
    def score(self, crops):
        if crops.shape != (38, 96, 96, 3):
            raise ValueError("Visual confirmation needs 38 RGB face crops")
        value = self(torch.from_numpy(np.asarray(crops, dtype=np.float32))[None]).item()
        if not np.isfinite(value):
            raise ValueError("Nonfinite visual activity score")
        return value
