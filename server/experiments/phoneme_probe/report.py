"""Paired error deltas, head timing, and a machine-readable decision receipt."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import time

import numpy as np
import torch
from .codec import words
from .evaluate import rerank
from .model import PhonemeHead


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    args=p.parse_args()
    root=args.root
    d=json.loads((root/'data_v1/DATASET.json').read_text(encoding='utf8'))
    e=json.loads((root/'evaluation_v1/EVALUATION.json').read_text(encoding='utf8'))
    rows=json.loads((root/'evaluation_v1/ROWS.json').read_text(encoding='utf8'))
    source={r['id']:r['source_id'] for r in d['records']}
    rng=np.random.default_rng(1706)
    intervals={}
    for split in ('test','lexical_test'):
        groups=defaultdict(lambda:[0,0])
        for r in rows:
            if r['split']!=split:continue
            selected=rerank(r['candidates'],r['ctc_scores'],e['selected_weight'])
            groups[source[r['id']]][0]+=r['candidates'][selected]['errors']-r['candidates'][0]['errors']
            groups[source[r['id']]][1]+=len(words(r['reference']))
        a=np.array(list(groups.values()))
        resampled=a[rng.integers(0,len(a),size=(5000,len(a)))].sum(axis=1)
        rates=resampled[:,0]/resampled[:,1]
        intervals[split]=dict(sources=len(a),delta_wer=float(a[:,0].sum()/a[:,1].sum()),
            percentile95=np.percentile(rates,[2.5,97.5]).tolist(),
            method='Paired source-cluster percentile bootstrap, 5000 draws; conditional on this curated sample.')
    torch.set_num_threads(4)
    saved=torch.load(root/'train_v1/best.pt',weights_only=True,map_location='cpu')
    head=PhonemeHead(**saved['config']).to('cuda').eval()
    head.load_state_dict(saved['state_dict'])
    x=torch.randn(1,150,768,device='cuda')
    timings=[]
    with torch.inference_mode():
        for i in range(320):
            torch.cuda.synchronize();tick=time.perf_counter()
            head(x)
            torch.cuda.synchronize()
            if i>=20:timings.append((time.perf_counter()-tick)*1000)
    receipt=dict(created_utc=datetime.now(timezone.utc).isoformat(),
        parameters=sum(p.numel() for p in head.parameters()),
        checkpoint_bytes=(root/'train_v1/best.pt').stat().st_size,
        head_timing=dict(input_frames=150,input_seconds=6,warmup=20,runs=300,
            median_ms=statistics.median(timings),p95_ms=float(np.percentile(timings,95)),
            scope='CUDA head only, cached feature shape; excludes encoding, CTC scoring, decoding, transport and display.'),
        paired_intervals=intervals,
        production_changed=False,
        source_sha256={str(f.relative_to(Path(__file__).parents[3])):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in Path(__file__).parent.glob('*.py')},
        evidence_sha256={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in [root/'data_v1/DATASET.json',root/'features_v1/IDENTITY.json',
                      root/'train_v1/TRAINING.json',root/'train_v1/best.pt',
                      root/'evaluation_v1/EVALUATION.json',root/'evaluation_v1/ROWS.json',
                      root/'AUDIT.json']})
    path=root/'RECEIPT.json'
    if path.exists():raise FileExistsError(path)
    path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in receipt.items() if 'sha256' not in k}),flush=True)


if __name__=='__main__':main()
