"""Aggregate saved real-inference reports without rerunning or changing predictions."""
import json
import statistics
from pathlib import Path
from benchmark_models import errors, normalized_words

root = Path(__file__).resolve().parents[2] / 'artifacts/validation'
rows = []
for path in sorted(root.glob('*.json')):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict) or 'wer' not in data:
        continue
    if 'records' in data:
        error_count = sum(errors(normalized_words(r['reference']), normalized_words(r['hypothesis'])) for r in data['records'])
        words = sum(len(normalized_words(r['reference'])) for r in data['records'])
        wer = error_count / words
    else:
        error_count, words, wer = data['errors'], data['reference_words'], data['wer']
    row = dict(file=path.name, wer=wer, errors=error_count, reference_words=words,
               mean_rtf=data.get('mean_rtf'))
    if 'events' in data:
        events = [e for e in data['events'] if e['type'] == 'partial']
        row.update(first_partial_seconds=events[0]['wall_seconds'] if events else None,
            median_decode_ms=statistics.median(e['elapsed_ms'] for e in events) if events else None,
            finalization_seconds=data['finalization_seconds'],
            transport_dropped_frames=data['transport_dropped_frames'],
            source_seconds=data['source_seconds'], sent_frames=data['sent_frames'])
    rows.append(row)
result = {'normalization': 'Unicode NFC, lowercase, punctuation removed, Vietnamese whitespace units', 'runs': rows}
(root/'METRICS_SUMMARY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
