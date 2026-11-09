"""Fine-tune the small phoneme head on context-cropped live-shaped windows."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time
import torch
from torch.nn.utils.rnn import pad_sequence
from .train import load_examples,batch
from .model import PhonemeHead,greedy,phone_error


def core_logits(logits,examples):
    sliced=[logits[i,r['row']['loss_start']:r['row']['loss_stop']] for i,r in enumerate(examples)]
    lengths=torch.tensor([len(x) for x in sliced],device=logits.device)
    return pad_sequence(sliced,batch_first=True).log_softmax(-1).transpose(0,1),lengths


@torch.inference_mode()
def evaluate(model,examples,tokens):
    model.eval();errors=phones=0
    for offset in range(0,len(examples),32):
        selected=examples[offset:offset+32]
        features,lengths,_=batch(selected,'cuda')
        logits,_=model(features,lengths)
        for i,r in enumerate(selected):
            left,right=r['row']['loss_start'],r['row']['loss_stop']
            hyp=greedy(logits[i,left:right],right-left,tokens)
            e,n=phone_error(r['row']['phones'],hyp);errors+=e;phones+=n
    return dict(errors=errors,phones=phones,per=errors/phones)


def main():
    p=argparse.ArgumentParser()
    for arg in ('dataset','features','initial','output'):p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--epochs',type=int,default=20)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(4);torch.manual_seed(1707);random.seed(1707)
    data=json.loads(args.dataset.read_text(encoding='utf8'))
    identity=json.loads((args.features/'IDENTITY.json').read_text())
    assert identity['dataset_sha256']==hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    saved=torch.load(args.initial,map_location='cpu',weights_only=True)
    assert saved['feature_identity']['checkpoint_sha256']==identity['checkpoint_sha256']
    segmental,tonal=saved['segmental_tokens'],saved['tonal_tokens']
    train=load_examples(data,args.features,{'train'},segmental,tonal)
    dev=load_examples(data,args.features,{'dev'},segmental,tonal)
    model=PhonemeHead(**saved['config']).to('cuda')
    model.load_state_dict(saved['state_dict'])
    optimizer=torch.optim.AdamW(model.parameters(),lr=.0005,weight_decay=.01)
    schedule=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,args.epochs,eta_min=.00005)
    ctc=torch.nn.CTCLoss(blank=0,zero_infinity=False)
    initial=evaluate(model,dev,segmental);best=initial['per']
    def save(epoch,score):
        torch.save(dict(state_dict=model.state_dict(),config=model.config,epoch=epoch,
            segmental_tokens=segmental,tonal_tokens=tonal,feature_identity=identity,dev=score,
            selection='Dev window-core PER only; no phone/test selection',
            training_policy=data['label_policy'],initial_sha256=hashlib.sha256(args.initial.read_bytes()).hexdigest()),
            args.output/'best.pt')
    save(0,initial);history=[];start=time.perf_counter()
    for epoch in range(1,args.epochs+1):
        random.shuffle(train);model.train();losses=[]
        for offset in range(0,len(train),32):
            examples=train[offset:offset+32]
            features,lengths,targets=batch(examples,'cuda')
            optimizer.zero_grad(set_to_none=True)
            first,second=model(features,lengths)
            logp,core_lengths=core_logits(first,examples)
            tonal_logp,_=core_logits(second,examples)
            loss=ctc(logp,targets['segmental'][0],core_lengths,targets['segmental'][1])
            loss=loss+.3*ctc(tonal_logp,targets['tonal'][0],core_lengths,targets['tonal'][1])
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite window loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step()
            losses.append(float(loss.detach()))
        schedule.step();score=evaluate(model,dev,segmental)
        history.append(dict(epoch=epoch,loss=sum(losses)/len(losses),dev=score,seconds=time.perf_counter()-start))
        if score['per']<best:best=score['per'];save(epoch,score)
        (args.output/'TRAINING.json').write_text(json.dumps(dict(train_windows=len(train),dev_windows=len(dev),
            initial_dev=initial,history=history),indent=2))
        print(json.dumps(history[-1]),flush=True)
    torch.save(dict(state_dict=model.state_dict(),optimizer=optimizer.state_dict(),epoch=args.epochs),args.output/'last.pt')

if __name__=='__main__':main()
