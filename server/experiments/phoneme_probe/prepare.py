"""Freeze deterministic source-disjoint probe splits before model inference."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from .codec import VietnamesePhones, UnsupportedSyllable, VPHON_COMMIT, words, ctc_min_frames


def digest(value):
    return hashlib.sha256(value.encode('utf8')).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--training', type=Path, required=True)
    p.add_argument('--vphon', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--train-size', type=int, default=2048)
    p.add_argument('--eval-size', type=int, default=128)
    p.add_argument('--seed', type=int, default=1706)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    codec = VietnamesePhones(args.vphon)
    local = {str(x.relative_to(args.training/'raw').with_suffix('')).replace('\\', '/'): x
             for x in (args.training/'raw').rglob('*.mp4')}
    eligible, reasons, unsupported, seen = [], Counter(), Counter(), set()
    manifest = args.training/'train_manifest.jsonl'
    with manifest.open(encoding='utf8') as f:
        for line in f:
            r = json.loads(line)
            if r['clip_id'] not in local:
                reasons['video_not_local'] += 1; continue
            if not (50 <= r['frames'] <= 200 and r.get('full_eligible')):
                reasons['duration_or_original_eligibility'] += 1; continue
            if r['video_sha256'] in seen:
                reasons['duplicate_video_hash'] += 1; continue
            try:
                phones = codec.encode(r['text'])
                tonal = codec.encode(r['text'], tones=True)
            except UnsupportedSyllable as exc:
                unsupported[str(exc)] += 1
                reasons['unsupported_syllable'] += 1; continue
            if ctc_min_frames(tonal) > r['frames']:
                reasons['ctc_target_too_long'] += 1; continue
            seen.add(r['video_sha256'])
            group = int(digest(f"{args.seed}:{r['source_id']}")[:8], 16) % 100
            split = 'train' if group < 70 else 'dev' if group < 85 else 'test'
            eligible.append(dict(id=r['clip_id'], source_id=r['source_id'],
                video=str(local[r['clip_id']]), sha256=r['video_sha256'],
                text=r['text'], words=words(r['text']), phones=phones, tonal=tonal,
                frames=r['frames'], split=split))
    counts = Counter(w for r in eligible for w in set(r['words']))
    # Select syllables using labels only; selection does not see model outcomes.
    candidates = [w for w, n in counts.items() if 80 <= n <= 500 and len(w) >= 3]
    heldout = sorted(candidates, key=lambda w: digest(f'{args.seed}:lex:{w}'))[:12]
    holdset = set(heldout)
    pools = {k: [] for k in ('train', 'dev', 'test', 'lexical_test')}
    for r in eligible:
        contains = bool(set(r['words']) & holdset)
        if contains and r['split'] != 'test':
            reasons['lexical_exclusion_train_dev'] += 1; continue
        key = 'lexical_test' if contains else r['split']
        pools[key].append(r)
    selected = []
    for split, pool in pools.items():
        n = args.train_size if split == 'train' else args.eval_size
        per_source = Counter()
        chosen = []
        for r in sorted(pool, key=lambda r: digest(f"{args.seed}:{r['id']}")):
            if per_source[r['source_id']] >= (24 if split == 'train' else 8):
                continue
            r['split'] = split
            chosen.append(r); per_source[r['source_id']] += 1
            if len(chosen) == n:
                break
        if len(chosen) != n:
            raise RuntimeError(f'Insufficient {split}: {len(chosen)}/{n}; use a new output with smaller size')
        selected.extend(chosen)
    train_words = set(w for r in selected if r['split'] == 'train' for w in r['words'])
    assert not train_words & holdset
    train_phones = set(p for r in selected if r['split'] == 'train' for p in r['tonal'])
    inventory = ['<blank>'] + sorted(train_phones)
    unseen = sorted(set(p for r in selected for p in r['tonal']) - train_phones)
    if unseen:
        raise RuntimeError(f'Evaluation phones absent from training: {unseen}')
    groups = {k: {r['source_id'] for r in selected if r['split'] == k}
              for k in pools}
    for a, b in [('train', 'dev'), ('train', 'test'), ('train', 'lexical_test'),
                 ('dev', 'test'), ('dev', 'lexical_test')]:
        assert not groups[a] & groups[b]
    report = dict(seed=args.seed, dialect='n',
        dependency=dict(name='vPhon', commit=VPHON_COMMIT, license='GPL-3.0-or-later',
            path=str(args.vphon.resolve())),
        source_manifest=str(manifest), source_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        scope='Frozen SO17 encoder; held out from NEW HEAD training only. Encoder pretraining exposure is not excluded. Source-disjoint does not prove speaker-disjoint.',
        tones='Six separate tone classes; checked D1/D2 map to B1/B2. Segmental branch omits tones.',
        lexical_unit='Normalized Vietnamese whitespace syllable, not necessarily a lexical word.',
        local_videos=len(local), eligible=len(eligible), excluded=dict(reasons),
        unsupported_top=unsupported.most_common(40), lexical_holdout=heldout,
        lexical_leakage_new_head=len(train_words & holdset),
        counts={k: sum(r['split'] == k for r in selected) for k in pools},
        sources={k: len(v) for k,v in groups.items()}, vocabulary=inventory, records=selected)
    (args.output/'DATASET.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('records','vocabulary')},ensure_ascii=False),flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    main()
