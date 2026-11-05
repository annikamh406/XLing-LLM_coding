#!/usr/bin/env python3
"""Freeze v6.2 on the unchanged 200-record diagnostic; no new data selection."""
import copy
import json
from pathlib import Path
import v611_diagnostic as previous

BASE=Path(__file__).resolve().parents[1]
MANIFEST=BASE/'v6/dev_train_diagnostic_6_2_freeze.json'


def main():
    if MANIFEST.exists():
        import v62_diagnostic
        v62_diagnostic.verify();print('Existing 6.2 freeze verified; no resampling.');return
    frozen=copy.deepcopy(previous.verify())
    frozen.update(date='2026-11-05',intervention='6.2',results_dir='v6/results/dev_train_diagnostic_6_2',
        purpose='Test the user-approved conservative-Denial policy and consolidated Rejection/Denial section on the same 200 training records.',
        prior_prompt_freeze_sha256=previous.digest(previous.MANIFEST),excluded_node='gpu3001')
    frozen['excluded_gpu_uuid']=json.loads((BASE/'v6/dev_train_diagnostic_6_1_1_ecc_recovery.json').read_text())['excluded_gpu_uuid']
    for lang,c in frozen['languages'].items():
        c['prompt']='v6/6.2/'+Path(c['prompt']).name
        c['prompt_version']='p0062-'+c['code']+'-diagnostic'
        frozen['files_sha256'][c['prompt']]=previous.digest(BASE/c['prompt'])
    for name in ['scripts/build_v62_diagnostic.py','scripts/v62_diagnostic.py','scripts/run_v62_diagnostic.py',
        'scripts/submit_v62_diagnostic.sh','scripts/sbatch_v62_diagnostic.sh','scripts/summarize_v62_diagnostic.py',
        'v6/6.2/make_prompts.py','v6/6.2/rejection_denial_section.md','v6/6.2/Bloom_coding_policy_v6.md']:
        frozen['files_sha256'][name]=previous.digest(BASE/name)
    MANIFEST.write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n')
    print('Frozen 6.2: all five languages, unchanged 200 IDs/groups/contexts/seeds/settings; separate outputs.')


if __name__=='__main__':main()
