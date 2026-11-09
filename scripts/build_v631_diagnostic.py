#!/usr/bin/env python3
"""Freeze v6.3.1 on the unchanged 200-record diagnostic; no new data selection."""
import copy
import json
from pathlib import Path
import v63_diagnostic as previous

BASE=Path(__file__).resolve().parents[1]
MANIFEST=BASE/'v6/dev_train_diagnostic_6_3_1_freeze.json'


def main():
    if MANIFEST.exists():
        import v631_diagnostic
        v631_diagnostic.verify();print('Existing 6.3.1 freeze verified; no resampling.');return
    previous_frozen=previous.verify()
    frozen=copy.deepcopy(previous_frozen)
    frozen.update(date='2026-11-09',intervention='6.3.1',results_dir='v6/results/dev_train_diagnostic_6_3_1',
        purpose='Ablate only the scope reminder from V6.3, keeping all example revisions, on the same 200 training records.',
        prior_prompt_freeze_sha256=previous.digest(previous.MANIFEST),excluded_node='gpu3001')
    frozen['excluded_gpu_uuid']=json.loads((BASE/'v6/dev_train_diagnostic_6_1_1_ecc_recovery.json').read_text())['excluded_gpu_uuid']
    for c in frozen['languages'].values():
        c['v62_predictions'] = c['comparison_predictions']
    for lang,c in frozen['languages'].items():
        c['prompt']='v6/6.3.1/'+Path(c['prompt']).name
        c['prompt_version']='p00631-'+c['code']+'-diagnostic'
        frozen['files_sha256'][c['prompt']]=previous.digest(BASE/c['prompt'])
    # Carry a portable, validated V6.3 comparator; scoring needs no old result directory.
    for lang, c in frozen['languages'].items():
        files = previous.paths(previous_frozen, lang)
        state = json.loads(files['checkpoint'].read_text())
        original = previous_frozen['languages'][lang]
        n = previous.check_saved(state, previous_frozen, original,
                                 previous.provenance(previous_frozen, original))
        predictions = previous.runner.read_jsonl(files['predictions'])
        raw = previous.runner.read_jsonl(files['raw'])
        if n != c['records'] or files['failure'].exists() or predictions != state['predictions'] or raw != state['raw_responses']:
            raise ValueError('Complete validated V6.3 comparator required: ' + lang)
        target = BASE / 'v6/6.3.1/baselines' / (lang + '_v63_predictions.jsonl')
        target.parent.mkdir(parents=True, exist_ok=True)
        previous.runner.write_jsonl(target, predictions)
        c['comparison_predictions'] = str(target.relative_to(BASE))
        frozen['files_sha256'][c['comparison_predictions']] = previous.digest(target)
        for key in ('checkpoint', 'predictions', 'raw'):
            frozen.setdefault('v63_comparator_sources_sha256', {})[str(files[key].relative_to(BASE))] = previous.digest(files[key])
    for name in ['scripts/build_v631_diagnostic.py','scripts/v631_diagnostic.py','scripts/run_v631_diagnostic.py',
        'scripts/submit_v631_diagnostic.sh','scripts/sbatch_v631_diagnostic.sh','scripts/summarize_v631_diagnostic.py',
        'v6/6.3.1/make_prompts.py','v6/6.3.1/rejection_denial_section.md','v6/6.3.1/Bloom_coding_policy_v6.md']:
        frozen['files_sha256'][name]=previous.digest(BASE/name)
    MANIFEST.write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n')
    print('Frozen 6.3.1: all five languages, unchanged 200 IDs/groups/contexts/seeds/settings; separate outputs.')


if __name__=='__main__':main()
