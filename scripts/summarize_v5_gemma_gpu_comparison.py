#!/usr/bin/env python3
"""Validate all Gemma GPU attempts and compare labels within and across GPUs."""
import csv
import itertools
import json
import re
from pathlib import Path
from collections import Counter
import run_bloom_coding as runner

BASE=Path(__file__).resolve().parents[1]
RESULTS=BASE/'v5/results/gemma_gpu_comparison'
LANGUAGES={'en':'english','de':'german','he':'hebrew','es':'spanish','tl':'tagalog'}
def collapse(label):return 'Nonexistence' if label=='Nonpossession' else label

def write_csv(path,rows):
    with path.open('w',newline='') as f:
        if rows:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def main():
    RESULTS.mkdir(parents=True,exist_ok=True)
    maps={};summary=[];issues=[];signatures=set()
    for p in sorted(RESULTS.glob('*_predictions.jsonl')):
        m=re.search(r'p005g-(en|de|he|es|tl)-(l40s|a6000)-r([12])-full-b1-t0',p.name)
        if not m:continue
        code,gpu,repeat=m.groups();lang=LANGUAGES[code]
        try:
            sample=runner.read_jsonl(BASE/'splits'/lang/'dev_train_gemma_gpu_v5.jsonl')
            ids=[r['record_id'] for r in sample];gold={r['record_id']:r['sampling_label'] for r in sample}
            preds=runner.read_jsonl(p);by_id={r['record_id']:r for r in preds}
            runner.validate_response({'schema_version':'bloom_v5','predictions':preds},ids,'bloom_v5')
            raw=runner.read_jsonl(p.with_name(p.name.replace('_predictions','_raw_responses')))
            if [i for r in raw for i in r['record_ids']]!=ids:raise ValueError('Raw coverage or order mismatch')
            if len(ids)!=40 or len(raw)!=40:raise ValueError('Expected 40 singleton batches')
            for index,batch in enumerate(raw):
                opts=batch['effective_decoding_options'];runtime=batch['runtime_provenance']
                if batch['model']!='gemma4:31b' or batch['attempt_count']!=1:raise ValueError('Model/retry mismatch')
                if opts['temperature']!=0 or opts['seed']!=20261009+index or opts['num_ctx']!=32768:raise ValueError('Decoding mismatch')
                names=[g['name'] for g in runtime['gpus']]
                expected_name='L40S' if gpu=='l40s' else 'A6000'
                if not names or any(expected_name not in n for n in names):raise ValueError('Wrong GPU hardware')
                signatures.add((runtime['model_digest'],runtime['ollama_version'],runtime['template_sha256'],runtime['model_parameters_sha256']))
            maps[(lang,gpu,repeat)]=by_id
            summary.append({'language':lang,'gpu':gpu,'repeat':repeat,'n':40,
                'exact_correct':sum(by_id[i]['bloom_label']==gold[i] for i in ids),
                'collapsed_correct':sum(collapse(by_id[i]['bloom_label'])==collapse(gold[i]) for i in ids),
                'certain_yes':sum(by_id[i]['certain']=='Yes' for i in ids),
                'model_digest':raw[0]['runtime_provenance']['model_digest'],
                'ollama_version':raw[0]['runtime_provenance']['ollama_version']})
        except (ValueError,KeyError,OSError) as e:issues.append(f'{p.name}: {e}')
    if len(signatures)>1:issues.append('Different model/template/runtime signatures; hardware comparison is confounded.')
    expected=set(itertools.product(LANGUAGES.values(),('l40s','a6000'),('1','2')))
    for key in sorted(expected-set(maps)):issues.append('Missing validated run: '+' / '.join(key))
    comparisons=[]
    for lang in LANGUAGES.values():
        available=[k for k in sorted(maps) if k[0]==lang]
        for left,right in itertools.combinations(available,2):
            a,z=maps[left],maps[right];ids=list(a)
            comparisons.append({'language':lang,'left_gpu':left[1],'left_repeat':left[2],
                'right_gpu':right[1],'right_repeat':right[2],
                'comparison':'within_gpu' if left[1]==right[1] else 'across_gpu','n':len(ids),
                'exact_label_differences':sum(a[i]['bloom_label']!=z[i]['bloom_label'] for i in ids),
                'collapsed_label_differences':sum(collapse(a[i]['bloom_label'])!=collapse(z[i]['bloom_label']) for i in ids),
                'flag_differences':sum(a[i]['flags']!=z[i]['flags'] for i in ids),
                'certainty_differences':sum(a[i]['certain']!=z[i]['certain'] for i in ids)})
    write_csv(RESULTS/'summary.csv',summary);write_csv(RESULTS/'repeatability.csv',comparisons)
    status={'expected_runs':20,'validated_runs':len(maps),'issues':issues}
    (RESULTS/'status.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status,indent=2))
    return 1 if issues else 0

if __name__=='__main__':raise SystemExit(main())
