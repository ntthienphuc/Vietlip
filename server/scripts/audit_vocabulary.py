"""Audit representability and exposure in supplied transcripts, never infer unseen pretraining."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import sentencepiece as spm
from sentencepiece import sentencepiece_model_pb2


def units(text):
    # Vietnamese space-delimited units are usually syllables, not lexical words.
    return re.findall(r'[^\W_]+', unicodedata.normalize('NFC', text).lower())


def digest(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', action='append', type=Path, required=True)
    parser.add_argument('--sentences', type=Path, required=True,
                        help='JSON array: id, text, optional purpose')
    parser.add_argument('--tokenizer', type=Path,
        default=Path(__file__).resolve().parents[1] / 'assets/tokenizers/vi.model')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sentences = json.loads(args.sentences.read_text(encoding='utf-8-sig'))
    probes = [' '.join(units(row['text'])) for row in sentences]
    counts = Counter()
    occurrences = Counter()
    exact = Counter()
    manifests = []
    for path in args.manifest:
        rows = 0
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf8') as stream:
            for line in stream:
                row = json.loads(line)
                text_units = units(row['text'])
                counts.update(text_units)
                text = ' '.join(text_units)
                for index, probe in enumerate(probes):
                    occurrences[index] += int(f' {probe} ' in f' {text} ')
                    exact[index] += int(probe == text)
                rows += 1
        manifests.append({'path':str(path.resolve()), 'sha256':digest(path), 'rows':rows})
    tokenizer = spm.SentencePieceProcessor(model_file=str(args.tokenizer))
    proto = sentencepiece_model_pb2.ModelProto()
    proto.ParseFromString(args.tokenizer.read_bytes())
    results = []
    for index, (row, text) in enumerate(zip(sentences, probes)):
        ids = tokenizer.encode(text)
        pieces = tokenizer.encode(text, out_type=str)
        results.append({**row, 'normalized':text, 'pieces':pieces,
            'round_trip':tokenizer.decode(ids),
            'representable':tokenizer.unk_id() not in ids and tokenizer.decode(ids) == text,
            'byte_fallback_pieces':[p for p in pieces if tokenizer.is_byte(tokenizer.piece_to_id(p))],
            'corpus_unit_counts':{w:counts[w] for w in dict.fromkeys(text.split())},
            'absent_units':[w for w in dict.fromkeys(text.split()) if not counts[w]],
            'manifest_rows_containing_sentence':occurrences[index],
            'manifest_rows_equal_sentence':exact[index]})
    result = {
        'scope':'Only supplied transcript manifests; not complete pretraining exposure or visual accuracy.',
        'unit_definition':'NFC lowercase Unicode letter/number runs; Vietnamese space units are not lexical words.',
        'manifests':manifests,
        'tokenizer':{'path':str(args.tokenizer.resolve()), 'sha256':digest(args.tokenizer),
            'vocabulary_size':tokenizer.get_piece_size(), 'byte_fallback':proto.trainer_spec.byte_fallback,
            'declared_training_inputs':list(proto.trainer_spec.input)},
        'corpus_unit_types':len(counts), 'corpus_unit_occurrences':sum(counts.values()),
        'sentences':results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'rows':sum(m['rows'] for m in manifests), 'types':len(counts),
        'results':[{'id':r['id'], 'absent_units':r['absent_units'],
                    'sentence_matches':r['manifest_rows_containing_sentence'],
                    'representable':r['representable']} for r in results]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
