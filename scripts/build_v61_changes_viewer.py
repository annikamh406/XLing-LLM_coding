#!/usr/bin/env python3
"""Build a self-contained case viewer from the validated v6.1 paired report."""
import collections
import hashlib
import json
from pathlib import Path

import run_bloom_coding as runner
import summarize_v61_diagnostic as scorer
import v61_diagnostic as config

BASE=Path(__file__).resolve().parents[1]
TEMPLATE=BASE/'scripts/templates/v61_changes_viewer.html'


def build():
    report=scorer.calculate();frozen=config.verify()
    if not report['all_complete']:raise ValueError('All five language conditions must be complete')
    rows=[]
    for language,c in frozen['languages'].items():
        references={r['record_id']:r for r in runner.read_jsonl(BASE/c['human_reference'])}
        inputs={r['record_id']:r for r in runner.read_jsonl(BASE/c['input'])}
        for row in report['rows']:
            if row['language']!=language:continue
            changed=row['v5_label']!=row['v61_label']
            if not changed and row['v5_certain']==row['v61_certain']:continue
            kind='repair' if changed and row['v61_correct'] else 'control_disagreement' if changed else 'certainty_only'
            ref=references[row['record_id']];record=inputs[row['record_id']]
            humans=[]
            for i in (1,2):
                h=ref[f'coder_{i}'] or {}
                humans.append({'sheet':ref.get(f'coder_{i}_sheet'),
                    'coded_by':h.get('coded_by_raw'),'label':h.get('bloom_label'),
                    'certain':h.get('certain_bloom'),'comments':h.get('comments'),
                    'alternative':h.get('other_possibility_bloom')})
            rows.append({**row,'kind':kind,'label_changed':changed,'humans':humans,
                'speaker':record.get('speaker'),'target_negator':record.get('target_negator'),
                'negator_index':record.get('negator_index_in_utterance'),
                'negator_count':record.get('negators_in_utterance')})
    counts=collections.Counter(r['kind'] for r in rows)
    expected=report['pooled_complete_groups']
    assert counts['repair']==expected['targeted']['repaired']
    assert counts['control_disagreement']==sum(expected[g]['regressed'] for g in ['relevant_control','broad_control'])
    payload={'intervention':'6.1','manifest_sha256':report['manifest_sha256'],
        'counts':dict(counts),'rows':rows,'source_report':'report/report.html'}
    folder=BASE/frozen['results_dir'];out=folder/'changes_viewer.html'
    encoded=json.dumps(payload,ensure_ascii=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    template=TEMPLATE.read_text()
    if template.count('__VIEWER_DATA__')!=1:raise ValueError('Expected one payload insertion point')
    runner.atomic_write(out,template.replace('__VIEWER_DATA__',encoded))
    audit={'rows':len(rows),'label_changes':sum(r['label_changed'] for r in rows),
        'counts':dict(counts),'record_ids':[r['record_id'] for r in rows],
        'manifest_sha256':report['manifest_sha256'],
        'viewer_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
    runner.atomic_write(folder/'changes_viewer_audit.json',json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit,indent=2))
    return out


if __name__=='__main__':build()
