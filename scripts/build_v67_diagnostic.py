#!/usr/bin/env python3
"""Freeze v6.7 on the unchanged 200-record diagnostic; no new data selection."""
import copy
import json
from pathlib import Path
import v64_diagnostic as previous

BASE=Path(__file__).resolve().parents[1]
MANIFEST=BASE/'v6/dev_train_diagnostic_6_7_freeze.json'


def main():
    if MANIFEST.exists():
        import v67_diagnostic
        v67_diagnostic.verify();print('Existing 6.7 freeze verified; no resampling.');return
    previous_frozen=previous.verify()
    frozen=copy.deepcopy(previous_frozen)
    frozen.update(date='2026-11-11',intervention='6.7',results_dir='v6/results/dev_train_diagnostic_6_7',
        purpose='Test deletion of worked examples J, K, T, U and X from V6.4; keep the basic examples and contrast section.',
        prior_prompt_freeze_sha256=previous.digest(previous.MANIFEST),excluded_node='gpu3001')
    frozen['excluded_gpu_uuid']=json.loads((BASE/'v6/dev_train_diagnostic_6_1_1_ecc_recovery.json').read_text())['excluded_gpu_uuid']
    for lang,c in frozen['languages'].items():
        c['prompt']='v6/6.7/'+Path(c['prompt']).name
        c['prompt_version']='p0067-'+c['code']+'-diagnostic'
        frozen['files_sha256'][c['prompt']]=previous.digest(BASE/c['prompt'])
    # Carry a portable, validated V6.4 comparator; scoring needs no old result directory.
    for lang, c in frozen['languages'].items():
        files = previous.paths(previous_frozen, lang)
        state = json.loads(files['checkpoint'].read_text())
        original = previous_frozen['languages'][lang]
        n = previous.check_saved(state, previous_frozen, original,
                                 previous.provenance(previous_frozen, original))
        predictions = previous.runner.read_jsonl(files['predictions'])
        raw = previous.runner.read_jsonl(files['raw'])
        if n != c['records'] or files['failure'].exists() or predictions != state['predictions'] or raw != state['raw_responses']:
            raise ValueError('Complete validated V6.4 comparator required: ' + lang)
        target = BASE / 'v6/6.7/baselines' / (lang + '_v64_predictions.jsonl')
        target.parent.mkdir(parents=True, exist_ok=True)
        previous.runner.write_jsonl(target, predictions)
        c['comparison_predictions'] = str(target.relative_to(BASE))
        frozen['files_sha256'][c['comparison_predictions']] = previous.digest(target)
        for key in ('checkpoint', 'predictions', 'raw'):
            frozen.setdefault('v64_comparator_sources_sha256', {})[str(files[key].relative_to(BASE))] = previous.digest(files[key])
    for name in ['scripts/build_v67_diagnostic.py','scripts/v67_diagnostic.py','scripts/run_v67_diagnostic.py',
        'scripts/submit_v67_diagnostic.sh','scripts/sbatch_v67_diagnostic.sh','scripts/summarize_v67_diagnostic.py',
        'v6/6.7/make_prompts.py','v6/6.7/rejection_denial_section.md','v6/6.7/Bloom_coding_policy_v6.md']:
        frozen['files_sha256'][name]=previous.digest(BASE/name)
    MANIFEST.write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n')
    print('Frozen 6.7: all five languages, unchanged 200 IDs/groups/contexts/seeds/settings; separate outputs.')


if __name__=='__main__':main()
