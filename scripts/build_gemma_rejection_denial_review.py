#!/usr/bin/env python3
"""Build a training-only, scrollable review of Gemma/consensus R↔D cases."""
import collections
import hashlib
import json
from pathlib import Path
from check_v5_dev_train_current import BASE, verify
from coordinate_v5_dev_train import complete, stem
from summarize_v5_nonrepetition import label, read, yes

OUTPUT=BASE/'v5/results/dev_train_rejection_denial_review'
TEMPLATE=BASE/'scripts/templates/gemma_rejection_denial_review.html'


def coder(human,sheet):
    raw=' '.join(str(human.get('coded_by_raw') or '').split())
    name=sheet if not raw else ('LM' if sheet=='LM' and raw.casefold() in {'laurize','lm'} else raw.title())
    return {'name':name,'sheet':sheet,'coded_by_raw':human.get('coded_by_raw'),
            'bloom_label':human.get('bloom_label'),'comments':human.get('comments'),
            'certain':human.get('certain_bloom'),'other_possibility':human.get('other_possibility_bloom'),
            'definitely_one_of_two':human.get('definitely_one_of_two_bloom')}


def build():
    frozen=verify();model='gemma4:31b';languages={};hashes={}
    for language,c in frozen['languages'].items():
        if not complete(language,model,frozen):raise ValueError('Gemma baseline is incomplete: '+language)
        input_path=BASE/c['input'];ref_path=BASE/c['human_reference']
        pred_path=BASE/frozen['results_dir']/(stem(language,model,frozen)+'_predictions.jsonl')
        records=read(input_path);refs={r['record_id']:r for r in read(ref_path)}
        preds={r['record_id']:r for r in read(pred_path)}
        cases=[];counts=collections.Counter()
        for r in records:
            rid=r['record_id'];ref=refs[rid];humans=[ref.get('coder_1') or {},ref.get('coder_2') or {}]
            if any(yes((h.get('flags') or {}).get('repetition')) for h in humans):counts['excluded_repetition']+=1;continue
            a,b=[label(h.get('bloom_label')) for h in humans]
            if a is None or a!=b:continue
            counts['consensus_records']+=1;prediction=preds[rid];p=label(prediction['bloom_label'])
            if {a,p}!={'rejection','denial'}:continue
            direction='over-denial' if a=='rejection' else 'over-rejection';counts[direction]+=1
            cases.append({'record_id':rid,'language':language,'direction':direction,
                'human_consensus':a.title(),'gemma_label':p.title(),'gemma_explanation':prediction.get('comments'),
                'gemma_certain':prediction.get('certain'),'human_coders':[coder(h,ref.get(f'coder_{i}_sheet')) for i,h in enumerate(humans,1)],
                **{k:r.get(k) for k in ['transcript_id','corpus','half','line','speaker','target_negator','target_utterance',
                                       'negator_index_in_utterance','negators_in_utterance','context_before','context_after',
                                       'child_age_raw','child_age_months','source']}})
        def order(r):
            try:line=float(r['line'])
            except (TypeError,ValueError):line=0
            return (str(r['transcript_id']),line,r['record_id'])
        cases.sort(key=order)
        languages[language]={'label':language.title(),'counts':dict(counts),'cases':cases,'prompt':c['prompt']}
        assert len(cases)==counts['over-denial']+counts['over-rejection']
        for p in [input_path,ref_path,pred_path]:hashes[str(p.relative_to(BASE))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return {'date':'2026-10-26','model':model,'split':'dev_train','batch_size':1,
        'selection':'Both human labels available and equal; human consensus and Gemma differ exactly between Rejection and Denial. Exclude rows if either human explicitly marked repetition Yes. No check/lockbox examples included.',
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_sha256':hashes,'languages':languages}


if __name__=='__main__':
    data=build();OUTPUT.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
    (OUTPUT/'review.html').write_text(TEMPLATE.read_text().replace('__REVIEW_DATA__',payload))
    (OUTPUT/'review.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    for lang,d in data['languages'].items():print(lang,len(d['cases']),'Human Rejection → Gemma Denial:',d['counts'].get('over-denial',0),'Human Denial → Gemma Rejection:',d['counts'].get('over-rejection',0))
