"""Reference-free LLM invocation followed by independent WER evaluation."""
import asyncio,json,time,argparse
from pathlib import Path
from dataclasses import asdict
from benchmark_models import errors,normalized_words
from app.services.candidate_selector import CandidateSelector

async def main(args):
    out=Path(__file__).resolve().parents[2]/'artifacts/optimization_v2'
    rows=json.loads((out/'WW_seed29_frozen_ctc0.5.json').read_text(encoding='utf8'))
    selector=CandidateSelector('http://127.0.0.1:7110/v1','qwen3-1.7b',args.budget)
    records=[]
    for row in rows:
        candidates=[row['hypothesis']]+[r['text'] for r in row['alternatives']]
        selection=await selector.select(candidates)
        result=dict(file=row['file'],split=row['split'],baseline_errors=row['errors'],
            selected_errors=errors(normalized_words(row['reference']),normalized_words(selection.text)),
            oracle_errors=min(errors(normalized_words(row['reference']),normalized_words(t)) for t in candidates),
            words=row['words'],selection=asdict(selection),candidates=candidates)
        records.append(result)
        print(row['file'],selection.status,selection.elapsed_ms,row['errors'],result['selected_errors'],flush=True)
        (out/args.output).write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
    await selector.close()

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--budget',type=float,default=30)
    p.add_argument('--output',default='llm_selector_unbounded.json')
    asyncio.run(main(p.parse_args()))
