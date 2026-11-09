"""Verify training provenance, cross-machine features and paired live replay."""
import argparse
import hashlib
import json
from pathlib import Path
import torch


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    args=p.parse_args();root=args.root
    target=root/'AUDIT.json'
    if target.exists():raise RuntimeError('Preserve the previous audit')
    torch.set_num_threads(4)
    receipt=read(root/'WORKER_RESULT.json')
    assert receipt['exit_code']==0
    assert hashlib.sha256((root/'results.zip').read_bytes()).hexdigest()==receipt['results_sha256']
    source_checks={}
    source_hashes={k.replace('\\','/'):v for k,v in receipt['source_sha256'].items()}
    for name in ('model.py','train.py','train_windows.py','window_features.py','prepare_windows.py','codec.py'):
        local=Path(__file__).with_name(name)
        expected=source_hashes['server/experiments/phoneme_probe/'+name]
        source_checks[name]=hashlib.sha256(local.read_bytes()).hexdigest()==expected
        assert source_checks[name],name
    identity=read(root/'remote_result/features/IDENTITY.json')
    assert hashlib.sha256((root/'data/DATASET.json').read_bytes()).hexdigest()==identity['dataset_sha256']
    corpus=read(root/'corpus_cache/CACHE.json')
    assert identity['checkpoint_sha256']==corpus['checkpoint_sha256']
    differences=[]
    for row in corpus['records']:
        name=hashlib.sha256(row['id'].encode()).hexdigest()[:24]+'.pt'
        local=torch.load(row['feature_file'],weights_only=True,map_location='cpu')['encoded']
        remote=torch.load(root/'remote_result/features'/name,weights_only=True,map_location='cpu')['encoded']
        assert local.shape==remote.shape
        difference=float((local-remote).abs().max())
        differences.append(difference)
    numerical=read(root/'CROSS_GPU.json')
    assert numerical['rows']==len(differences)
    assert numerical['maximum_absolute_difference']==max(differences)
    assert numerical['maximum_relative_rms']<.0001
    assert all(n==0 for n in numerical['selection_changes'].values())
    scores=read(root/'evaluation_v2/RESULTS.json')
    replay=read(root/'ws_paired/RESULTS.json')
    assert not replay['smoke_only'] and len(replay['clips'])==3
    assert replay['weights']['window']==scores['selected_weights']['window']
    assert replay['weights']['v1']==scores['selected_weights']['v1']
    agreements={}
    for clip in replay['clips']:
        assert clip['frames']==clip['acknowledgements']
        for live,offline in [('baseline','baseline'),('v1','v1_dev'),('window','window')]:
            actual=clip['outcomes'][live];expected=scores['live'][offline][clip['clip']]
            assert actual['hypothesis']==expected['hypothesis']
            assert actual['errors']==expected['errors']
            agreements[clip['clip']+'/'+live]=True
    head=torch.load(root/'remote_result/training/best.pt',weights_only=True,map_location='cpu')
    outcome=dict(source_checks=source_checks,remote_feature_rows=len(differences),
        maximum_cross_gpu_feature_difference=max(differences),paired_caption_agreement=agreements,
        maximum_cross_gpu_relative_rms=numerical['maximum_relative_rms'],
        cross_gpu_candidate_selection_changes=numerical['selection_changes'],
        selected_epoch=head['epoch'],selected_dev=head['dev'],training_complete=receipt['exit_code']==0,
        head_sha256=hashlib.sha256((root/'remote_result/training/best.pt').read_bytes()).hexdigest(),
        scope='Cross-machine provenance and exact fixed-window captions; no new physical camera test.')
    target.write_text(json.dumps(outcome,indent=2),encoding='utf8')
    print(json.dumps(outcome),flush=True)


if __name__=='__main__':main()
