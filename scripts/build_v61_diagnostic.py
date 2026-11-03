#!/usr/bin/env python3
"""Freeze the 40 targeted / 80 relevant-control / 80 broad-control diagnostic."""
import collections
import hashlib
import json
import re
from pathlib import Path

import run_bloom_coding as runner
from summarize_v5_nonrepetition import label, yes
from validation_runtime_compat import parameter_values

BASE = Path(__file__).resolve().parents[1]
STEM = 'dev_train_diagnostic_6_1'
SELECTION_SEED = 'v6.1-diagnostic-2026-11-03'
# Deliberate training selection, not a random sample of errors or a gold adjudication.
# One target per utterance; at most two selected targets within 20 transcript turns.
TARGETS = {
    'english': 'eng_005376 eng_003888 eng_000451 eng_004782 eng_001992 eng_004032 eng_001714 eng_004765 eng_004742 eng_004152 eng_004261 eng_003909'.split(),
    'german': 'ger_006436 ger_007308 ger_009563 ger_009661 ger_008178 ger_011694 ger_000104 ger_000139 ger_004508 ger_009525'.split(),
    'hebrew': 'heb_000444 heb_004714 heb_001450 heb_001889 heb_001891 heb_002065 heb_004511 heb_001853 heb_001868 heb_002732'.split(),
    'spanish': 'spa_000188 spa_002529 spa_002611 spa_002669 spa_002717 spa_011109 spa_001274'.split(),
    'tagalog': ['tgm_000496'],
}
MOTIFS = {
    'english': r'\b(mine|my|this|that|here|there|want|like|put|give|take|help|try|eat|draw)\b',
    'german': r'\b(mein\w*|dein\w*|das|die|da|hier|will\w*|möcht\w*|geb\w*|gib\w*|mach\w*|rein|hin)\b',
    'hebrew': r'(šeli|šel|roce|roca|po\b|ze\b|ten\b|tiq|laqa|taʕaz|lišo|laga|ef.*tax)',
    'spanish': r'\b(m[ií]o\w*|esto|esta|ésta|este|éste|aquí|ahí|quier\w*|gusta|pon\w*|dame|toma|yo|dar|ver)\b',
    'tagalog': r'(akin|ako|ito|iyan|diyan|gusto|ayaw|laro|bigay|lagay|kuha|tayo)',
}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def frozen_write(path, text):
    if path.exists() and path.read_text() != text:
        raise ValueError('Refusing to replace frozen diagnostic: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def lines(rows):
    return ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)


def features(record, language):
    target = record['target_utterance']
    hits = []
    if len(target.split()) >= 3:
        hits.append('multiword_target')
    if re.search(MOTIFS[language], target, re.I):
        hits.append('target_ownership_deixis_preference_or_action_word')
    context = record.get('context_before', [])[-3:] + record.get('context_after', [])[:3]
    if any(re.search(MOTIFS[language], x['utterance'], re.I) for x in context):
        hits.append('nearby_ownership_deixis_preference_or_action_word')
    return hits


def main():
    freeze_path = BASE/'v6'/f'{STEM}_freeze.json'
    if freeze_path.exists():
        from v61_diagnostic import verify
        verify()
        print('Existing 200-record diagnostic verified; selection was not regenerated.')
        return
    old = json.loads((BASE/'v5/dev_train_current_freeze.json').read_text())
    output = {'date': '2026-11-03', 'intervention': '6.1', 'model': 'gemma4:31b',
        'schema_version': 'bloom_v6', 'batch_size': 1, 'max_retries': 0,
        'timeout': old['timeout'], 'decoding_options': old['decoding_options'],
        'ollama_version': old['ollama_version'],
        'weights_blob_sha256': old['models']['gemma4:31b']['weights_blob_sha256'],
        'resources': old['resources'], 'results_dir': 'v6/results/'+STEM,
        'selection_seed': SELECTION_SEED,
        'selection_policy': {
            'targeted': '40 manually selected v5 R-to-D mismatches plausibly relevant to negation target, accompanying explanation, action inference or uptake. Ambiguous and parsing-confounded cases are diagnostic candidates, not adjudicated errors.',
            'relevant_control': '80 previously consensus-correct R/D records: 8 per label per language, enriched for multiword negation plus ownership/deixis/preference/action words in the target or nearest three turns. Features are candidate retrieval, not semantic adjudication.',
            'broad_control': '80 other consensus-correct records: 16 per language. Quotas per language: 4 R, 4 D, 4 Nonexistence (including Nonpossession), 2 Excluded, 2 Uncoded. Sparse classes are filled deterministically from remaining classes and documented.',
            'eligibility': 'dev_train only, both human labels present and equal after Nonpossession collapse, neither human repetition Yes.',
            'dependence': 'One record per target utterance; at most two selected records in any 20-observed-turn window within a transcript/half. Turn ranks come from the union of all dev_train context windows and targets, not global numeric line gaps. Missing intervening turns make this cap conservative. This caps clustering, not a claim of independence.',
            'limitations': 'Training-only, purposively enriched diagnostic. No population accuracy, causal prevalence or held-out generalization estimate. No composite-score promotion threshold.'},
        'languages': {}, 'files_sha256': {}, 'baseline_sources': {}}
    for language, condition in old['languages'].items():
        records = runner.read_jsonl(BASE/condition['input'])
        refs = {r['record_id']:r for r in runner.read_jsonl(BASE/condition['human_reference'])}
        prefix = f'dev_train_gemma4_31b_bloom_v5_p005dt1-{condition["code"]}-full-b1-t0-s20261009'
        prediction_path = BASE/old['results_dir']/(prefix+'_predictions.jsonl')
        raw_path = BASE/old['results_dir']/(prefix+'_raw_responses.jsonl')
        predictions = {r['record_id']:r for r in runner.read_jsonl(prediction_path)}
        assert len(records) == len(predictions) == condition['records']
        # Build observed main-tier turn ranks; numeric worksheet line gaps are
        # not numbers of conversational turns. Unobserved gaps only tighten the cap.
        observed = collections.defaultdict(set)
        for r in records:
            key = (r['transcript_id'], r.get('half'))
            for turn in [r] + r.get('context_before', []) + r.get('context_after', []):
                observed[key].add(int(turn['line']))
        ranks = {key:{line:i for i,line in enumerate(sorted(values))} for key,values in observed.items()}
        positions = {r['record_id']:((r['transcript_id'], r.get('half')),
            ranks[(r['transcript_id'], r.get('half'))][int(r['line'])]) for r in records}
        selected = []; occupied = set(); turns = collections.defaultdict(list)
        by_id = {r['record_id']:r for r in records}
        def add(r, group, reason):
            key, turn = positions[r['record_id']]
            utterance = (key, r['line'])
            proposed = sorted(turns[key] + [turn])
            if utterance in occupied or any(proposed[i+2]-proposed[i] <= 20 for i in range(len(proposed)-2)):
                return False
            occupied.add(utterance); turns[key].append(turn)
            selected.append({'record_id': r['record_id'], 'group': group, 'selection_reason': reason})
            return True
        eligible = []
        for r in records:
            humans = [refs[r['record_id']].get(f'coder_{i}') or {} for i in (1,2)]
            truth = [label(h.get('bloom_label')) for h in humans]
            if truth[0] is None or truth[0] != truth[1] or any(yes((h.get('flags') or {}).get('repetition')) for h in humans):
                continue
            eligible.append((r, truth[0], label(predictions[r['record_id']]['bloom_label'])))
        eligible_map = {r['record_id']:(t,p) for r,t,p in eligible}
        for rid in TARGETS[language]:
            if eligible_map.get(rid) != ('rejection','denial'):
                raise ValueError('Target must be an eligible v5 mismatch: '+rid)
            if not add(by_id[rid], 'targeted', 'Manual mechanism-relevant training mismatch; interpretation remains a hypothesis.'):
                raise ValueError('Targeted records violate episode cap: '+rid)
        def rank(r, category):
            return hashlib.sha256((SELECTION_SEED+language+category+r['record_id']).encode()).hexdigest()
        correct = [(r,t) for r,t,p in eligible if t == p]
        for truth in ('rejection','denial'):
            pool = [(r,features(r,language)) for r,t in correct if t == truth]
            pool = [(r,f) for r,f in pool if len(f) >= 2]
            pool.sort(key=lambda z: (-len(z[1]), rank(z[0],'relevant')))
            n=0
            for r, feat in pool:
                if add(r,'relevant_control',', '.join(feat)):
                    n+=1
                    if n==8:break
            if n!=8:raise ValueError(f'Insufficient {language} {truth} relevant controls: {n}')
        quotas={'rejection':4,'denial':4,'nonexistence':4,'excluded':2,'uncoded':2}
        achieved=collections.Counter()
        for truth,wanted in quotas.items():
            for r,t in sorted(correct,key=lambda z:rank(z[0],'broad')):
                if t==truth and add(r,'broad_control','Class-stratified, hash-ranked broader control.'):
                    achieved[truth]+=1
                    if achieved[truth]==wanted:break
        missing=16-sum(achieved.values())
        if missing:
            for r,t in sorted(correct,key=lambda z:rank(z[0],'broad-fallback')):
                if add(r,'broad_control','Sparse broad-control class fallback; hash-ranked remaining correct record.'):
                    achieved[t]+=1;missing-=1
                    if not missing:break
        if missing:raise ValueError('Insufficient broad controls')
        selected_by_id={s['record_id']:s for s in selected}
        selected=[selected_by_id[r['record_id']] for r in records if r['record_id'] in selected_by_id]
        assert len(selected)==len(TARGETS[language])+32
        selected_ids=set(selected_by_id)
        baseline_batches={}
        with raw_path.open() as handle:
            for line in handle:
                batch=json.loads(line)
                if len(batch['record_ids'])!=1:raise ValueError('Gemma baseline must be singleton')
                rid=batch['record_ids'][0]
                if rid in selected_ids:
                    index=next(i for i,r in enumerate(records) if r['record_id']==rid)
                    options={**old['decoding_options'],'seed':old['decoding_options']['seed']+index}
                    if batch['effective_decoding_options']!=options or batch['attempt_count']!=1 or batch['batch_number']!=index+1:
                        raise ValueError('Baseline seed/options mismatch: '+rid)
                    runtime=batch['runtime_provenance']
                    signature={k:runtime[k] for k in ['model_digest','ollama_version','template_sha256']}
                    signature['model_parameters']=parameter_values(runtime['model_parameters'])
                    if baseline_batches and signature!=next(iter(baseline_batches.values()))['runtime_signature']:
                        raise ValueError('Baseline runtime differs within language')
                    baseline_batches[rid]={'original_batch_number':batch['batch_number'],
                        'original_effective_options':options,'runtime_signature':signature}
        if set(baseline_batches)!=selected_ids:raise ValueError('Missing baseline batch')
        for s in selected:s.update(baseline_batches[s['record_id']])
        folder=BASE/'splits'/language
        artifacts={
            folder/(STEM+'.jsonl'):lines([by_id[s['record_id']] for s in selected]),
            folder/(STEM+'_human_reference.jsonl'):lines([refs[s['record_id']] for s in selected]),
            folder/(STEM+'_baseline.jsonl'):lines([predictions[s['record_id']] for s in selected]),
        }
        prompt='v6/bloom_v6_'+language+'_prompt'+('' if language=='english' else '_english_examples')+'.md'
        for path,text in artifacts.items():
            frozen_write(path,text);output['files_sha256'][str(path.relative_to(BASE))]=sha(path)
        for name in [condition['input'],condition['human_reference'],prompt]:output['files_sha256'][name]=sha(BASE/name)
        output['languages'][language]={'code':condition['code'],'prompt':prompt,'prompt_version':'p0061-'+condition['code']+'-diagnostic',
            'input':str((folder/(STEM+'.jsonl')).relative_to(BASE)),
            'human_reference':str((folder/(STEM+'_human_reference.jsonl')).relative_to(BASE)),
            'baseline':str((folder/(STEM+'_baseline.jsonl')).relative_to(BASE)),
            'records':len(selected),'selection':selected,
            'counts':dict(collections.Counter(s['group'] for s in selected)),
            'broad_requested_quotas':quotas,'broad_actual_class_counts':dict(achieved)}
        for path in [prediction_path,raw_path,BASE/'v5/dev_train_current_freeze.json']:
            output['baseline_sources'][str(path.relative_to(BASE))]=sha(path)
    assert sum(c['records'] for c in output['languages'].values())==200
    for name in ['scripts/build_v61_diagnostic.py','scripts/v61_diagnostic.py','scripts/run_v61_diagnostic.py',
                 'scripts/summarize_v61_diagnostic.py','scripts/submit_v61_diagnostic.sh','scripts/sbatch_v61_diagnostic.sh',
                 'scripts/run_bloom_coding.py','scripts/capture_coding_runtime.py','scripts/validation_runtime_compat.py',
                 'scripts/summarize_v5_nonrepetition.py','v6/bloom_v6_output.schema.json','v6/Bloom_coding_policy_v6.md',
                 'v6/make_v6_prompts.py']:
        output['files_sha256'][name]=sha(BASE/name)
    frozen_write(freeze_path,json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({lang:c['counts'] for lang,c in output['languages'].items()},indent=2))


if __name__=='__main__':main()
