"""Application checkpoint selection with identical cached pixels and frozen splits.

No training or reference text enters inference. Weight averages are ephemeral;
original checkpoints are read-only. Select only on corpus dev, then evaluate the
winner and baseline on corpus test and complete captions from fixed live windows.
These historical corpus splits do not establish unseen pretrained-model data.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import gc
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch

from app.services.native_engine import NativeAvsrEngine
from app.services.video_preprocessor import PreparedVideo
from experiments.phoneme_probe.codec import edit_distance, words
from experiments.phoneme_probe.evaluate_direct import captions
from experiments.phoneme_probe.fixed_windows import camera_frames
from scripts.benchmark_models import settings


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    temp.replace(path)


def summary(rows):
    e = sum(r['errors'] for r in rows)
    n = sum(r['words'] for r in rows)
    ce = sum(r['char_errors'] for r in rows)
    cn = sum(r['chars'] for r in rows)
    return dict(windows=len(rows), errors=e, words=n, wer=e/max(n, 1),
                char_errors=ce, chars=cn, cer=ce/max(cn, 1),
                unavailable=sum(not r['candidates'][0]['words'] for r in rows),
                median_decode_ms=statistics.median(r['decode_ms'] for r in rows))


def load_average(engine, paths):
    """Average floating weights/BN moments, retain integer counters from first.

    Counter disagreement is recorded; counters do not affect eval-mode inference.
    Every source must have exactly the same keys, shapes and dtypes.
    """
    state = None
    metadata = []
    counters = []
    for path, multiplicity in Counter(paths).items():
        payload = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
        source = payload.get('model', payload.get('state_dict', payload))
        if all(k.startswith('model.') for k in source):
            source = {k[6:]: v for k, v in source.items()}
        metadata.append(dict(path=str(path), sha256=digest(path), identity=payload.get('identity'),
                             weight=multiplicity/len(paths)))
        if state is None:
            state = {k: v.clone().mul_(multiplicity) if v.is_floating_point() else v.clone()
                     for k, v in source.items()}
        else:
            if state.keys() != source.keys():
                raise ValueError('Incompatible checkpoint keys')
            for key, value in source.items():
                target = state[key]
                if target.shape != value.shape or target.dtype != value.dtype:
                    raise ValueError(f'Incompatible state: {key}')
                if value.is_floating_point():
                    target.add_(value, alpha=multiplicity)
                elif not torch.equal(target, value):
                    counters.append(key)
        del source, payload
        gc.collect()
    for value in state.values():
        if value.is_floating_point():
            value.div_(len(paths))
            if not torch.isfinite(value).all():
                raise ValueError('Nonfinite averaged state')
    state_hash = hashlib.sha256()
    for key, value in state.items():
        state_hash.update(key.encode())
        state_hash.update(value.numpy().tobytes())
    engine._model.load_state_dict(state, strict=True)
    del state
    gc.collect()
    return dict(sources=metadata, state_sha256=state_hash.hexdigest(),
                integer_counter_disagreements=sorted(set(counters)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--reuse-pixels', type=Path, help='Completed earlier run; verify cached pixels against its SO17 records')
    p.add_argument('--resume', action='store_true', help='Resume only matching protocol and verified completed checkpoints')
    p.add_argument('--runs', nargs='+', default=['SO_seed17', 'SO_seed29', 'SO_seed43',
        'WW_seed17', 'WW_seed29', 'WW_seed43', 'VLR_pretrained', 'SO_average', 'WW_average', 'all_average'])
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=args.resume)
    root = Path(__file__).resolve().parents[2]
    old = root/'artifacts/phoneme_window_20261107'
    new = root/'artifacts/phoneme_direct_20261109/device'
    manifest_path = old/'BENCHMARK.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    baseline_cache = json.loads((old/'corpus_cache/CACHE.json').read_text(encoding='utf8'))
    expected = {r['id']: r for r in baseline_cache['records']}
    live = dict(clips=[])
    for path in [old/'LIVE_WINDOWS.json', new/'LIVE_WINDOWS.json']:
        live['clips'].extend(json.loads(path.read_text(encoding='utf8'))['clips'])
    live_expected = {}
    for path in [old/'live_cache/CACHE.json', new/'live_cache/CACHE.json']:
        live_expected.update({r['id']: r for r in json.loads(path.read_text(encoding='utf8'))['records']})
    models = root/'server/models'
    recipes = {name: [models/f'{name}.pt'] for name in
        ['SO_seed17','SO_seed29','SO_seed43','WW_seed17','WW_seed29','WW_seed43','VLR_pretrained']}
    recipes.update(SO_average=[models/f'SO_seed{s}.pt' for s in (17,29,43)],
                   WW_average=[models/f'WW_seed{s}.pt' for s in (17,29,43)],
                   all_average=[models/f'{a}_seed{s}.pt' for a in ('SO','WW') for s in (17,29,43)])
    for name, copies, base in [('SO17_mix25',1,18),('SO17_mix50',1,6),('SO17_mix75',3,6)]:
        recipes[name]=recipes['all_average']*copies+[models/'SO_seed17.pt']*base
    engine = NativeAvsrEngine(replace(settings(models/'SO_seed17.pt',device='cuda',beam=3),
                                      precision='float32', nbest=3, ctc_weight=.1))
    engine.load()
    assert engine._phoneme_rescorer is None
    cache_dir = args.reuse_pixels/'pixels' if args.reuse_pixels else args.output/'pixels'
    if not args.reuse_pixels:
        cache_dir.mkdir()
    cache = {}
    if args.reuse_pixels:
        prior_dev=json.loads((args.reuse_pixels/'SO_seed17_DEV.json').read_text(encoding='utf8'))['records']
        prior_eval=json.loads((args.reuse_pixels/'SO_seed17_EVAL.json').read_text(encoding='utf8'))
        for row in prior_dev+prior_eval['corpus']+prior_eval['live']:
            key=hashlib.sha256(row['id'].encode()).hexdigest()[:24]
            path=cache_dir/f'{key}.pt'
            tensor=torch.load(path,map_location='cpu',weights_only=True)
            sha=hashlib.sha256(tensor.numpy().tobytes()).hexdigest()
            assert sha==row['tensor_sha256'],row['id']
            cache[row['id']]=dict(path=path,hash=sha)
    provenance = dict(selection='Lowest corpus dev core WER, then CER. Live/test never select.',
        manifest_sha256=digest(manifest_path), runs=args.runs,
        scope=__doc__, beam=3, ctc_weight=.1, precision='float32',
        pixel_source=str(args.reuse_pixels) if args.reuse_pixels else None)
    if args.resume:
        previous = json.loads((args.output/'PROTOCOL.json').read_text(encoding='utf8'))
        if previous != provenance:
            raise ValueError('Resume protocol differs from original run')
    else:
        write(args.output/'PROTOCOL.json', provenance)

    def save_tensor(row, tensor):
        key = hashlib.sha256(row['id'].encode()).hexdigest()[:24]
        path = cache_dir/f'{key}.pt'
        torch.save(tensor.clone(), path)
        cache[row['id']] = dict(path=path, hash=hashlib.sha256(tensor.numpy().tobytes()).hexdigest())

    def corpus_pixels(rows):
        for i,row in enumerate(rows):
            if row['id'] in cache:
                continue
            path = Path(row['video'])
            assert digest(path) == row['sha256']
            prepared = engine._preprocessor.prepare(path, input_kind='mouth_roi')
            tensor = prepared.tensor[row['window_start']:row['window_stop']]
            save_tensor(row, tensor)
            if i % 30 == 0:
                print('prepared',i+1,'/',len(rows),flush=True)

    def decode(row, live_row=False):
        data = cache[row['id']]
        tensor = torch.load(data['path'], map_location='cpu', weights_only=True)
        assert hashlib.sha256(tensor.numpy().tobytes()).hexdigest() == data['hash']
        prepared = PreparedVideo(tensor, len(tensor), {})
        torch.cuda.synchronize()
        tick = time.perf_counter()
        result = engine._decode_native(prepared, realtime=True)
        torch.cuda.synchronize()
        candidates = [dict(text=result.transcript, words=result.diagnostics['words'])]
        output = dict(id=row['id'], candidates=candidates, tensor_sha256=data['hash'],
                      decode_ms=(time.perf_counter()-tick)*1000)
        if live_row:
            output.update(clip=row['clip'], event=row['event'])
        else:
            hyp = words(' '.join(w['text'] for w in candidates[0]['words']
                if row['loss_start']/25 <= (w['start']+w['end'])/2 < row['loss_stop']/25))
            ref = words(row['text'])
            output.update(split=row['split'], reference=row['text'], core_text=' '.join(hyp),
                errors=edit_distance(ref,hyp), words=len(ref),
                char_errors=edit_distance(''.join(ref),''.join(hyp)), chars=len(''.join(ref)))
        return output

    dev = [r for r in manifest['records'] if r['split']=='dev']
    corpus_pixels(dev)
    sweep = []
    for name in args.runs:
        identity = load_average(engine, recipes[name])
        completed = args.output/f'{name}_DEV.json'
        if args.resume and completed.exists():
            prior = json.loads(completed.read_text(encoding='utf8'))
            assert prior['identity'] == identity, name
            assert [r['id'] for r in prior['records']] == [r['id'] for r in dev], name
            for row in prior['records']:
                assert row['tensor_sha256'] == cache[row['id']]['hash'], row['id']
            sweep.append(dict(name=name, **summary(prior['records'])))
            print('RESUME dev', name, flush=True)
            continue
        rows = []
        for i,row in enumerate(dev):
            result = decode(row)
            if name == 'SO_seed17':
                assert result['candidates'][0]['text'] == expected[row['id']]['candidates'][0]['text'], row['id']
            rows.append(result)
            if i % 30 == 0:
                print(name,i+1,'/',len(dev),flush=True)
        write(args.output/f'{name}_DEV.json',dict(identity=identity,records=rows))
        value = dict(name=name, **summary(rows))
        sweep.append(value)
        write(args.output/'DEV_SWEEP.json',sweep)
        print('DEV',json.dumps(value),flush=True)
    selected = min(sweep,key=lambda r:(r['errors'],r['char_errors']))['name']
    write(args.output/'SELECTED.json',dict(name=selected,recipe=[str(x) for x in recipes[selected]],
                                        selected_on='dev only',dev=sweep))
    test = [r for r in manifest['records'] if r['split']!='dev']
    corpus_pixels(test)
    live_rows = []
    for clip in live['clips']:
        path = Path(clip['video'])
        assert digest(path)==clip['sha256']
        frames = camera_frames(path,360 if clip['input_kind']=='raw_face' else 0)
        for i,event in enumerate(clip['windows']):
            row=dict(id=f"{clip['id']}/{i}",clip=clip['id'],event=event)
            left,right=round(event['window_start']*25),round(event['window_end']*25)
            if row['id'] not in cache:
                prepared=engine._preprocessor.prepare_frames(frames[left:right],source_fps=25,input_kind=clip['input_kind'])
                save_tensor(row,prepared.tensor)
            assert cache[row['id']]['hash']==live_expected[row['id']]['tensor_sha256'],row['id']
            live_rows.append(row)
        print('prepared live',clip['id'],flush=True)
        del frames
    results = {}
    for name in dict.fromkeys(['SO_seed17',selected]):
        identity = load_average(engine,recipes[name])
        completed = args.output/f'{name}_EVAL.json'
        if args.resume and completed.exists():
            previous = json.loads((args.output/f'{name}_DEV.json').read_text(encoding='utf8'))
            assert previous['identity'] == identity, name
            prior = json.loads(completed.read_text(encoding='utf8'))
            rows, live_predictions = prior['corpus'], prior['live']
            assert [r['id'] for r in rows] == [r['id'] for r in test], name
            assert [r['id'] for r in live_predictions] == [r['id'] for r in live_rows], name
            for row in rows + live_predictions:
                assert row['tensor_sha256'] == cache[row['id']]['hash'], row['id']
            print('RESUME evaluation', name, flush=True)
        else:
            rows = [decode(row) for row in test]
            live_predictions = [decode(row,True) for row in live_rows]
        if name=='SO_seed17':
            for row in live_predictions:
                assert row['candidates'][0]['text']==live_expected[row['id']]['candidates'][0]['text'],row['id']
        caption = captions(live_predictions,live)
        results[name] = dict(identity=identity,
            corpus={split:summary([r for r in rows if r['split']==split]) for split in ('test','lexical_test')},
            live={k:{a:b for a,b in v.items() if a!='history'} for k,v in caption.items()})
        write(args.output/f'{name}_EVAL.json',dict(corpus=rows,live=live_predictions,captions=caption))
        write(args.output/'RESULTS.json',dict(selected=selected,dev=sweep,evaluation=results,protocol=provenance))
        print('EVAL',name,json.dumps(results[name],ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
