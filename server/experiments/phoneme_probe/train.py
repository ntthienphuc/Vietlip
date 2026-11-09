"""Train only small visual phoneme heads. Select epochs using dev data only."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import time

import numpy as np
import torch
from torch.nn.utils.rnn import pad_sequence

from .codec import ctc_min_frames
from .model import PhonemeHead, greedy, phone_error


def load_examples(dataset, features, splits, segmental, tonal):
    segment_ids = {p:i for i,p in enumerate(segmental)}
    tone_ids = {p:i for i,p in enumerate(tonal)}
    result = []
    for r in dataset['records']:
        if r['split'] not in splits:
            continue
        key = hashlib.sha256(r['id'].encode()).hexdigest()[:24]
        payload = torch.load(features/f'{key}.pt', map_location='cpu', weights_only=True)
        assert payload['id'] == r['id']
        assert payload['frames'] >= ctc_min_frames(r['tonal'])
        result.append(dict(row=r, features=payload['encoded'].float(),
            segmental=torch.tensor([segment_ids[p] for p in r['phones']]),
            tonal=torch.tensor([tone_ids[p] for p in r['tonal']])))
    return result


def batch(examples, device):
    features = pad_sequence([r['features'] for r in examples], batch_first=True).to(device)
    lengths = torch.tensor([len(r['features']) for r in examples], device=device)
    targets = {}
    for key in ('segmental', 'tonal'):
        targets[key] = (torch.cat([r[key] for r in examples]).to(device),
                        torch.tensor([len(r[key]) for r in examples], device=device))
    return features, lengths, targets


@torch.inference_mode()
def evaluate(model, examples, segmental, tonal, device):
    model.eval()
    result = dict(errors=0, phones=0, tonal_errors=0, tonal_tokens=0, empty=0, clips=len(examples))
    for start in range(0, len(examples), 16):
        selected = examples[start:start+16]
        features, lengths, _ = batch(selected, device)
        segment_logits, tone_logits = model(features, lengths)
        for i, item in enumerate(selected):
            hyp = greedy(segment_logits[i], int(lengths[i]), segmental)
            thyp = greedy(tone_logits[i], int(lengths[i]), tonal)
            e, n = phone_error(item['row']['phones'], hyp)
            te, tn = phone_error(item['row']['tonal'], thyp, tones=True)
            result['errors'] += e; result['phones'] += n
            result['tonal_errors'] += te; result['tonal_tokens'] += tn
            result['empty'] += not any(p != '|' for p in hyp)
    result['per'] = result['errors']/max(1,result['phones'])
    result['tonal_token_error_rate'] = result['tonal_errors']/max(1,result['tonal_tokens'])
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--features', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--epochs', type=int, default=25)
    p.add_argument('--batch-size', type=int, default=32)
    p.add_argument('--seed', type=int, default=1706)
    p.add_argument('--device', default='cuda')
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    dataset = json.loads(args.dataset.read_text(encoding='utf8'))
    identity = json.loads((args.features/'IDENTITY.json').read_text())
    assert identity['dataset_sha256'] == hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    tonal = dataset['vocabulary']
    segmental = [t for t in tonal if not t.startswith('tone:')]
    train = load_examples(dataset,args.features,{'train'},segmental,tonal)
    dev = load_examples(dataset,args.features,{'dev'},segmental,tonal)
    model = PhonemeHead(768,256,len(segmental),len(tonal)).to(args.device)
    optimizer = torch.optim.AdamW(model.parameters(),lr=.0015,weight_decay=.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,args.epochs,eta_min=.00015)
    ctc = torch.nn.CTCLoss(blank=0,reduction='mean',zero_infinity=False)
    initial = evaluate(model,dev,segmental,tonal,args.device)
    trace = []; best = float('inf'); start = time.perf_counter()
    for epoch in range(1,args.epochs+1):
        random.shuffle(train)
        model.train(); losses = []
        for offset in range(0,len(train),args.batch_size):
            examples=train[offset:offset+args.batch_size]
            features,lengths,targets=batch(examples,args.device)
            optimizer.zero_grad(set_to_none=True)
            first,second=model(features,lengths)
            loss=ctc(first.log_softmax(-1).transpose(0,1),targets['segmental'][0],lengths,targets['segmental'][1])
            loss_tone=ctc(second.log_softmax(-1).transpose(0,1),targets['tonal'][0],lengths,targets['tonal'][1])
            loss=loss+.3*loss_tone
            if not torch.isfinite(loss):
                raise RuntimeError('Non-finite CTC loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5)
            optimizer.step();losses.append(float(loss.detach()))
        scheduler.step()
        score=evaluate(model,dev,segmental,tonal,args.device)
        trace.append(dict(epoch=epoch,loss=sum(losses)/len(losses),dev=score,
                          elapsed_seconds=time.perf_counter()-start))
        if score['per'] < best:
            best=score['per']
            torch.save(dict(state_dict=model.state_dict(),config=model.config,epoch=epoch,
                segmental_tokens=segmental,tonal_tokens=tonal,feature_identity=identity,
                selection='Minimum development segmental PER, test/phone unused',
                dev=score),args.output/'best.pt')
        (args.output/'TRAINING.json').write_text(json.dumps(dict(seed=args.seed,
            parameters=sum(p.numel() for p in model.parameters()),initial_dev=initial,
            train_clips=len(train),dev_clips=len(dev),history=trace),indent=2))
        print(f"epoch {epoch}: loss {trace[-1]['loss']:.3f}; dev PER {score['per']:.4f}; {trace[-1]['elapsed_seconds']:.1f}s",flush=True)
    torch.save(dict(state_dict=model.state_dict(),optimizer=optimizer.state_dict(),
        scheduler=scheduler.state_dict(),epoch=args.epochs,config=model.config,
        segmental_tokens=segmental,tonal_tokens=tonal,feature_identity=identity),args.output/'last.pt')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    main()
