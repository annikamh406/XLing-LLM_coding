#!/usr/bin/env python3
"""Freeze 6.1.1 on the exact 6.1 subset, retaining both saved comparators."""
import copy
import json
from pathlib import Path

import run_bloom_coding as runner
import summarize_v61_diagnostic as previous_report
import v61_diagnostic as previous

BASE=Path(__file__).resolve().parents[1]
MANIFEST=BASE/'v6/dev_train_diagnostic_6_1_1_freeze.json'


def frozen_write(path,text):
    if path.exists() and path.read_text()!=text:raise ValueError('Refusing to overwrite frozen artifact: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)


def main():
    if MANIFEST.exists():
        import v611_diagnostic
        v611_diagnostic.verify();print('Existing 6.1.1 freeze verified; no resampling or replacement.')
        return
    parent=previous.verify();report=previous_report.calculate()
    if not report['all_complete']:raise ValueError('Complete validated 6.1 outputs required to freeze the comparator')
    frozen=copy.deepcopy(parent)
    frozen.update(date='2026-11-04',intervention='6.1.1',results_dir='v6/results/dev_train_diagnostic_6_1_1',
        parent_manifest_sha256=previous.digest(previous.MANIFEST),
        purpose='Test the utterance-as-evidence clarification on exactly the 6.1 training diagnostic; compare saved v5 and 6.1 predictions.')
    frozen['comparator_sources_sha256']={}
    for lang,c in frozen['languages'].items():
        c['prompt']='v6/6.1.1/'+Path(c['prompt']).name
        c['prompt_version']='p00611-'+c['code']+'-diagnostic'
        source=previous.paths(parent,lang)['predictions']
        destination=BASE/'v6/6.1.1/baselines'/(lang+'_v61_predictions.jsonl')
        frozen_write(destination,source.read_text())
        c['parent_predictions']=str(destination.relative_to(BASE))
        for name in [c['prompt'],c['parent_predictions']]:
            frozen['files_sha256'][name]=previous.digest(BASE/name)
        for key in ('predictions','raw','checkpoint'):
            p=previous.paths(parent,lang)[key]
            frozen['comparator_sources_sha256'][str(p.relative_to(BASE))]=previous.digest(p)
    for name in ['scripts/build_v611_diagnostic.py','scripts/v611_diagnostic.py','scripts/run_v611_diagnostic.py',
        'scripts/submit_v611_diagnostic.sh','scripts/sbatch_v611_diagnostic.sh','scripts/summarize_v611_diagnostic.py',
        'v6/6.1.1/make_prompts.py','v6/6.1.1/Bloom_coding_policy_v6.md']:
        frozen['files_sha256'][name]=previous.digest(BASE/name)
    frozen_write(MANIFEST,json.dumps(frozen,ensure_ascii=False,indent=2)+'\n')
    print('Frozen 6.1.1: same 200 IDs, order, groups, original seeds, settings and runtime; five new prompts.')


if __name__=='__main__':main()
