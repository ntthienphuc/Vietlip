"""Summarize a confirmed seven-sentence phone round without mixing live and replay."""
import argparse
import json
from pathlib import Path
import statistics
from benchmark_models import errors, normalized_words


def score(reference, hypothesis):
    ref, hyp = normalized_words(reference), normalized_words(hypothesis)
    a, b = ''.join(ref), ''.join(hyp)
    return dict(word_errors=errors(ref,hyp),reference_units=len(ref),
        wer=errors(ref,hyp)/max(1,len(ref)),char_errors=errors(a,b),
        reference_characters_no_spaces=len(a),cer_no_spaces=errors(a,b)/max(1,len(a)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('round',type=Path)
    args=parser.parse_args();root=args.round
    confirmed=json.loads((root/'REFERENCE_CONFIRMED.json').read_text(encoding='utf8'))
    reference=' '.join(r['reference'] for r in confirmed['segments'])
    original=[json.loads(line) for line in (root/'ORIGINAL_LIVE_TRACE.jsonl').read_text(encoding='utf8').splitlines()]
    final=original[-1]
    result={'reference_status':confirmed['reference_status'],
        'normalization':'NFC, lowercase, punctuation removed, Vietnamese whitespace units; CER excludes spaces.',
        'phone_original':dict(**score(reference,final['transcript']),
            transcript=final['transcript'],received_frames=final['received_frames'],
            capture_fps=final['capture_fps'],capture_gaps=final['capture_gaps'],
            incomplete=final['incomplete'],automatic_segments=sum(e['type']=='segment_final' for e in original)),
        'replays':{},'checkpoint_diagnostic':[],'decoder_diagnostic':[]}
    for name in ['BASELINE_REPLAY','AFTER_REPLAY','ROUND02_REGRESSION_REPLAY']:
        data=json.loads((root/(name+'.json')).read_text(encoding='utf8'))
        events=[e for e in data['events'] if e.get('window_words')]
        finals=[e for e in events if e['type']=='segment_final']
        row=dict(**score(data['reference'],data['hypothesis']),
            transcript=data['hypothesis'],sent_frames=data['sent_frames'],
            dropped_frames=data['transport_dropped_frames'],automatic_segments=len(finals),
            median_window_processing_ms=statistics.median(e['elapsed_ms'] for e in events),
            stop_to_final_seconds=data['finalization_seconds'])
        if name!='ROUND02_REGRESSION_REPLAY' and len(finals)==len(confirmed['segments']):
            delays=[e['wall_seconds']-r['audio_end_estimate']
                    for e,r in zip(finals,confirmed['segments'])]
            row['estimated_audio_end_to_server_final_seconds']={
                'per_sentence':delays,'median':statistics.median(delays),
                'min':min(delays),'max':max(delays),
                'scope':'Audio ASR word-end estimates on paced prerecorded replay; not phone-visible latency.'}
        result['replays'][name]=row
    diagnostic=json.loads((root/'checkpoint-diagnostic/RESULTS.json').read_text(encoding='utf8'))
    for model in dict.fromkeys(r['model'] for r in diagnostic['records']):
        rows=[r for r in diagnostic['records'] if r['model']==model]
        result['checkpoint_diagnostic'].append(dict(model=model,
            word_errors=sum(r['errors'] for r in rows),reference_units=sum(r['words'] for r in rows),
            median_decode_seconds=statistics.median(r['decode_seconds'] for r in rows),
            scope='Audio-assisted slices; excludes preprocessing; not comparable with continuous live WER.'))
    decoder=json.loads((root/'FULL_DECODER_SWEEP.json').read_text(encoding='utf8'))['records']
    for beam,ctc in dict.fromkeys((r['beam'],r['ctc']) for r in decoder):
        rows=[r for r in decoder if (r['beam'],r['ctc'])==(beam,ctc)]
        result['decoder_diagnostic'].append(dict(beam=beam,ctc=ctc,
            word_errors=sum(r['errors'] for r in rows),reference_units=76,
            median_decode_seconds=statistics.median(r['seconds'] for r in rows)))
    result['limits']=[
        'This phone clip is now development data; no spontaneous or independent held-out section was recorded.',
        'Original phone and PC replay differ in capture, sampling and compression; only pair replay with replay.',
        'Checkpoint and decoder sweeps used audio-assisted slices and have not justified a production model change.',
        'ASR audio transcript had errors; final reference comes from explicit speaker confirmation.',
        'Phone USB disconnected before final physical-device recheck; server changes are validated by replay and tests.',
        'No visual model fine-tuning or LLM correction was deployed; no generic unseen-word success is established.',
        'After-replay first seconds overlapped CPU unit tests; runtime comparison does not establish a speedup.']
    (root/'EVALUATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'phone':result['phone_original']['wer'],
        'replay_before':result['replays']['BASELINE_REPLAY']['wer'],
        'replay_after':result['replays']['AFTER_REPLAY']['wer'],
        'previous_clip':result['replays']['ROUND02_REGRESSION_REPLAY']['wer']},indent=2))


if __name__=='__main__':main()
