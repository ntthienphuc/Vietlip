"""Compare policies on identical saved window hypotheses; no new inference."""
import argparse
import json
from pathlib import Path
from benchmark_models import normalized_words, errors
from app.services.streaming_buffer import WordTimeline
from app.services.caption_stability import AgreementTimeline


def evaluate(data, factory):
    timeline = factory()
    previous = []
    erasures = 0
    outputs = []
    for event in data['events']:
        if not event.get('window_words'):
            continue
        update = timeline.update(event['window_words'], event['window_start'],
                                 event['window_end'], right_context=1.,
                                 final=event['type'] in {'segment_final', 'session_final'})
        words = normalized_words(update['transcript'])
        prefix = 0
        for a, b in zip(previous, words):
            if a != b: break
            prefix += 1
        erasures += len(previous) - prefix
        previous = words
        outputs.append(dict(wall_seconds=event.get('wall_seconds'),
                            window_end=event['window_end'], type=event['type'],
                            turn_id=event.get('turn_id'), **update))
    reference = normalized_words(data['reference'])
    hypothesis = normalized_words(timeline.text)
    return dict(errors=errors(reference, hypothesis), words=len(reference),
                wer=errors(reference, hypothesis) / max(1, len(reference)),
                erasures=erasures, hypothesis=timeline.text, outputs=outputs)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('files', nargs='+')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    results = []
    for file in args.files:
        data = json.loads(Path(file).read_text(encoding='utf8'))
        policies = {name: evaluate(data, cls) for name, cls in
                    [('time_only', WordTimeline), ('agreement', AgreementTimeline)]}
        results.append(dict(file=file, policies=policies))
        print(json.dumps(dict(file=file, policies={k: {m: v[m] for m in
                         ('wer', 'errors', 'words', 'erasures')} for k, v in policies.items()})))
    Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf8')
