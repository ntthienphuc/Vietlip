"""Build a lexicon and small LM from source-separated TRAIN text only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from .codec import VietnamesePhones,UnsupportedSyllable,words


def main():
    p=argparse.ArgumentParser()
    for name in ('dataset','vphon','output'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    data=json.loads(args.dataset.read_text(encoding='utf8'))
    manifest=Path(data['source_manifest'])
    assert hashlib.sha256(manifest.read_bytes()).hexdigest()==data['source_manifest_sha256']
    codec=VietnamesePhones(args.vphon)
    hold=set(data['lexical_holdout'])
    unigram=Counter();bigram=Counter();trigram=Counter();contexts=Counter()
    sources=set();train_rows=0;excluded=Counter();seen=set()
    for line in manifest.open(encoding='utf8'):
        row=json.loads(line)
        group=int(hashlib.sha256(f"{data['seed']}:{row['source_id']}".encode()).hexdigest()[:8],16)%100
        if group>=70:excluded['dev_test_source']+=1;continue
        tokens=words(row['text'])
        if set(tokens)&hold:excluded['lexical_holdout']+=1;continue
        if tuple(tokens) in seen:excluded['duplicate_text']+=1;continue
        seen.add(tuple(tokens));sources.add(row['source_id']);train_rows+=1
        # Unsupported strings remain LM context; lexicon limits output separately.
        previous=['<s>','<s>']
        for word in tokens:
            unigram[word]+=1;bigram[(previous[-1],word)]+=1
            trigram[(*previous,word)]+=1;contexts[tuple(previous)]+=1
            previous=[previous[-1],word]
    assert not hold&set(unigram)
    for r in data['records']:
        if r['split']!='train':assert r['source_id'] not in sources
    dictionary=args.vphon/'text/wordlist.txt'
    syllables=set(unigram)
    for line in dictionary.read_text(encoding='utf8').splitlines():
        syllables.update(words(line.replace('-',' ')))
    entries=[]
    inventory=set(data['vocabulary'])
    for word in sorted(syllables):
        try:
            phones=codec.encode(word);tonal=codec.encode(word,tones=True)
        except UnsupportedSyllable:continue
        if set(tonal)-inventory:continue
        entries.append(dict(word=word,segmental=phones,tonal=tonal,count=unigram[word]))
    report=dict(version=1,scope='Independent vPhon dictionary; n-grams from original TRAIN source groups only, excluding all lexical holdout syllables. No phone recordings or dev/test reference text used.',
        dataset_sha256=hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        manifest_sha256=data['source_manifest_sha256'],
        dictionary_sha256=hashlib.sha256(dictionary.read_bytes()).hexdigest(),
        dependency=data['dependency'],train_rows=train_rows,train_sources=len(sources),
        train_tokens=sum(unigram.values()),excluded=dict(excluded),lexical_holdout=data['lexical_holdout'],
        entries=entries,unigram=dict(unigram),
        bigram={'\t'.join(k):v for k,v in bigram.items()},
        trigram={'\t'.join(k):v for k,v in trigram.items()},
        contexts={'\t'.join(k):v for k,v in contexts.items()})
    (args.output/'LEXICON_LM.json').write_text(json.dumps(report,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('entries','unigram','bigram','trigram','contexts')}))
    print('lexicon_syllables',len(entries),flush=True)


if __name__=='__main__':main()
