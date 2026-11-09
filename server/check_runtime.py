"""Run with the packaged interpreter to verify relocation and dependencies."""

import json
from pathlib import Path
import sys

import cv2
import mediapipe as mp
import numpy as np
import sentencepiece
import torch
from desktop_runtime import configure_runtime
from app.config import Settings

configure_runtime()

settings = Settings.from_env()
prefix = Path(sys.prefix).resolve()
for module in (cv2, mp, np, sentencepiece, torch):
    if not Path(module.__file__).resolve().is_relative_to(prefix):
        raise RuntimeError(f"External import: {module.__name__}")
sp = sentencepiece.SentencePieceProcessor(model_file=str(settings.spm_model_path))
sample = "Xin chào Việt Nam"
assert sp.decode(sp.encode(sample)) == sample
with mp.solutions.face_mesh.FaceMesh(static_image_mode=True) as detector:
    detector.process(np.zeros((64, 64, 3), dtype=np.uint8))
if torch.cuda.is_available():
    assert float(torch.ones(4, device="cuda").sum()) == 4
print(
    json.dumps(
        {
            "prefix": str(prefix),
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "tokenizer_roundtrip": True,
            "mediapipe_loaded": True,
            "checkpoint_exists": settings.checkpoint_path.is_file(),
        },
        indent=2,
    )
)
