"""Cache frozen visual states once; never reads audio or feeds references to the encoder."""
from __future__ import annotations
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time

import torch
from scripts.benchmark_models import settings
from app.services.native_engine import NativeAvsrEngine


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--phone-manifest', type=Path)
    p.add_argument('--phone-tensors', type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    dataset = json.loads(args.dataset.read_text(encoding='utf8'))
    identity = dict(dataset_sha256=hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                    checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                    dtype='float32', encoder='frozen_eval', audio_used=False)
    identity_path = args.output/'IDENTITY.json'
    if identity_path.exists():
        assert json.loads(identity_path.read_text()) == identity, 'Cache identity mismatch'
    else:
        identity_path.write_text(json.dumps(identity, indent=2))
    engine = NativeAvsrEngine(replace(settings(args.checkpoint, device='cuda'), precision='float32'))
    engine.load()
    engine._model.requires_grad_(False)
    model = engine._model
    items = list(dataset['records'])
    if args.phone_manifest:
        phone = json.loads(args.phone_manifest.read_text(encoding='utf8'))
        for r in phone['segments']:
            items.append(dict(id=f"phone/{r['id']}", split='phone', text=r['reference'],
                tensor=str(args.phone_tensors/f"prepared-{r['id']}.pt")))
    start = time.perf_counter()
    receipt = []
    for i, r in enumerate(items):
        key = hashlib.sha256(r['id'].encode()).hexdigest()[:24]
        dest = args.output/f'{key}.pt'
        if dest.exists():
            receipt.append(dict(id=r['id'], file=dest.name, resumed=True))
            continue
        if 'tensor' in r:
            tensor = torch.load(r['tensor'], weights_only=True, map_location='cpu')
        else:
            assert hashlib.sha256(Path(r['video']).read_bytes()).hexdigest() == r['sha256'], r['id']
            prepared = engine._preprocessor.prepare(Path(r['video']), input_kind='mouth_roi')
            tensor = prepared.tensor
        tick = time.perf_counter()
        with torch.inference_mode():
            frontend = model.frontend(tensor.to('cuda').unsqueeze(0))
            encoded = model.encoder(model.proj_encoder(frontend), None)[0][0]
            assert torch.isfinite(encoded).all()
            # Detached CPU feature payload contains no transcripts.
            payload = dict(encoded=encoded.cpu().clone(), frames=len(encoded), id=r['id'])
        torch.save(payload, dest)
        elapsed = time.perf_counter()-tick
        receipt.append(dict(id=r['id'], file=dest.name, frames=len(encoded), seconds=elapsed))
        if (i+1) % 50 == 0 or i == 0 or i+1 == len(items):
            (args.output/'PROGRESS.json').write_text(json.dumps(dict(done=i+1,total=len(items),
                seconds=time.perf_counter()-start,records=receipt),indent=2))
            print(f'{i+1}/{len(items)} feature cache; {time.perf_counter()-start:.1f}s',flush=True)
    (args.output/'COMPLETE.json').write_text(json.dumps(dict(identity=identity,
        total=len(items),seconds=time.perf_counter()-start,records=receipt),indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    main()
