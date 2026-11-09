#!/usr/bin/env python3
"""Paired, group-separated v6.3.1 diagnostic report; never score partial conditions."""
import collections
import html
import json

import run_bloom_coding as runner
import v631_diagnostic as config
from summarize_v5_nonrepetition import label


def metrics(rows):
    n=len(rows)
    result={'n':n,'v5_correct':sum(r['v5_correct'] for r in rows),
        'v631_correct':sum(r['v631_correct'] for r in rows),
        'repaired':sum(not r['v5_correct'] and r['v631_correct'] for r in rows),
        'regressed':sum(r['v5_correct'] and not r['v631_correct'] for r in rows),
        'label_changed':sum(r['v5_label']!=r['v631_label'] for r in rows),
        'uncertainty_changed':sum(r['v5_certain']!=r['v631_certain'] for r in rows)}
    for version in ('v5','v631'):
        result[version+'_uncertain']=sum(r[version+'_certain']=='No' for r in rows)
        result[version+'_uncoded']=sum(r[version+'_label']=='uncoded' for r in rows)
        result[version+'_R_to_D']=sum(r['human_consensus']=='rejection' and r[version+'_label']=='denial' for r in rows)
        result[version+'_D_to_R']=sum(r['human_consensus']=='denial' and r[version+'_label']=='rejection' for r in rows)
        result[version+'_confusions']=dict(collections.Counter(r['human_consensus']+' → '+r[version+'_label'] for r in rows))
    result['net_correct_change']=result['repaired']-result['regressed']
    return result


def calculate(base=config.BASE,manifest=config.MANIFEST):
    frozen=config.verify(base,manifest)
    result={'intervention':'6.3.1','manifest_sha256':config.digest(manifest),
        'scope':'Purposively selected training diagnostic: separate targeted repairs from control regressions. No population accuracy or generalization claim. No composite promotion score.',
        'languages':{},'pooled_complete_groups':{},'pooled_against_v63':{},'pooled_against_v62':{},'rows':[]}
    for language,c in frozen['languages'].items():
        paths=config.paths(frozen,language,base)
        checkpoint=json.loads(paths['checkpoint'].read_text()) if paths['checkpoint'].exists() else None
        n=0
        if checkpoint is not None:n=config.check_saved(checkpoint,frozen,c,config.provenance(frozen,c,manifest))
        failure=json.loads(paths['failure'].read_text()) if paths['failure'].exists() else None
        complete=n==c['records'] and paths['predictions'].exists() and paths['raw'].exists() and failure is None
        status={'complete':complete,'saved_records':n,'expected_records':c['records'],'failure':failure,'planned_groups':c['counts']}
        if not complete:
            result['languages'][language]=status
            continue
        predictions=runner.read_jsonl(paths['predictions']);raw=runner.read_jsonl(paths['raw'])
        if predictions!=checkpoint['predictions'] or raw!=checkpoint['raw_responses']:
            raise ValueError('Final outputs differ from validated checkpoint')
        baseline=runner.read_jsonl(base/c['baseline']);refs=runner.read_jsonl(base/c['human_reference'])
        parent=runner.read_jsonl(base/c['comparison_predictions'])
        v62=runner.read_jsonl(base/c['v62_predictions'])
        source=runner.read_jsonl(base/c['input'])
        rows=[]
        for s,p,b,prior,older,ref,r in zip(c['selection'],predictions,baseline,parent,v62,refs,source):
            truth=label(ref['coder_1']['bloom_label'])
            if truth!=label(ref['coder_2']['bloom_label']):raise ValueError('Human consensus changed')
            rows.append({'language':language,'record_id':s['record_id'],'group':s['group'],
                'human_consensus':truth,'v5_label':label(b['bloom_label']),'v631_label':label(p['bloom_label']),
                'v5_correct':label(b['bloom_label'])==truth,'v631_correct':label(p['bloom_label'])==truth,
                'v5_certain':b['certain'],'v631_certain':p['certain'],
                'v5_comments':b['comments'],'v631_comments':p['comments'],
                'v63_label':label(prior['bloom_label']),'v63_correct':label(prior['bloom_label'])==truth,
                'v63_certain':prior['certain'],'v63_comments':prior['comments'],
                'v62_label':label(older['bloom_label']),'v62_correct':label(older['bloom_label'])==truth,
                'v62_certain':older['certain'],'v62_comments':older['comments'],
                'original_seed':s['original_effective_options']['seed'],
                'transcript_id':r['transcript_id'],'half':r.get('half'),'line':r['line'],
                'target_utterance':r['target_utterance'],'context_before':r['context_before'],'context_after':r['context_after'],
                'selection_reason':s['selection_reason']})
        status['groups']={g:metrics([r for r in rows if r['group']==g]) for g in c['counts']}
        status['against_v63']={g:against_parent([r for r in rows if r['group']==g]) for g in c['counts']}
        status['against_v62']={g:against_parent([r for r in rows if r['group']==g], 'v62') for g in c['counts']}
        result['languages'][language]=status;result['rows'].extend(rows)
    for g in ('targeted','relevant_control','broad_control'):
        rows=[r for r in result['rows'] if r['group']==g]
        if rows:
            result['pooled_complete_groups'][g]=metrics(rows)
            result['pooled_against_v63'][g]=against_parent(rows)
            result['pooled_against_v62'][g]=against_parent(rows, 'v62')
    result['all_complete']=all(c['complete'] for c in result['languages'].values())
    return result


def against_parent(rows, version='v63'):
    """Use the same paired scorer with saved 6.3 as the comparator."""
    converted=[{**r,**{'v5_'+field:r[version+'_'+field] for field in ('label','correct','certain')}} for r in rows]
    output=metrics(converted)
    return {key.replace('v5_',version+'_'):value for key,value in output.items()}


def render(data):
    e=html.escape
    s=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V6.3.1 training diagnostic</title><style>body{font:15px system-ui;line-height:1.5;max-width:1200px;margin:24px auto;padding:0 20px;color:#222}h1{font-size:25px}h2{font-size:20px}table{border-collapse:collapse;width:100%;margin:16px 0}td,th{text-align:left;padding:8px;border-bottom:1px solid #ddd;vertical-align:top}summary{cursor:pointer}blockquote{padding:10px;background:#fff2c7}.scroll{overflow:auto}</style><h1>V6.3.1 training diagnostic</h1><p>'+e(data['scope'])+'</p><p>Nonpossession is collapsed into Nonexistence. Both human labels must agree; human-marked repetitions were excluded during selection. Human consensus is not adjudicated truth. Only complete language conditions enter metrics.</p>']
    s.append('<table><tr><th>Language</th><th>Status</th><th>Saved / planned</th></tr>')
    for lang,c in data['languages'].items():
        state='Complete' if c['complete'] else ('Failed — review required' if c['failure'] else 'Pending / incomplete')
        s.append(f'<tr><td>{e(lang)}</td><td>{state}</td><td>{c["saved_records"]} / {c["expected_records"]}</td></tr>')
    s.append('</table><h2>Paired changes by group</h2><div class="scroll"><table><tr><th>Language</th><th>Group</th><th>n</th><th>V5 correct</th><th>6.3.1 correct</th><th>Repaired</th><th>Regressed</th><th>R→D: v5 / 6.3.1</th><th>D→R: v5 / 6.3.1</th><th>Uncertain: v5 / 6.3.1</th></tr>')
    for lang,c in data['languages'].items():
        for group,m in c.get('groups',{}).items():
            values=[lang,group,m['n'],m['v5_correct'],m['v631_correct'],m['repaired'],m['regressed'],f'{m["v5_R_to_D"]} / {m["v631_R_to_D"]}',f'{m["v5_D_to_R"]} / {m["v631_D_to_R"]}',f'{m["v5_uncertain"]} / {m["v631_uncertain"]}']
            s.append('<tr>'+''.join('<td>'+e(str(v))+'</td>' for v in values)+'</tr>')
    s.append('</table></div><h2>Changes from 6.3 to 6.3.1</h2><table><tr><th>Language</th><th>Group</th><th>n</th><th>6.3 correct</th><th>6.3.1 correct</th><th>Repaired</th><th>Regressed</th></tr>')
    for lang,c in data['languages'].items():
        for group,m in c.get('against_v63',{}).items():
            values=[lang,group,m['n'],m['v63_correct'],m['v631_correct'],m['repaired'],m['regressed']]
            s.append('<tr>'+''.join('<td>'+e(str(v))+'</td>' for v in values)+'</tr>')
    s.append('</table><h2>Changes from 6.2 to 6.3.1</h2><table><tr><th>Language</th><th>Group</th><th>n</th><th>6.2 correct</th><th>6.3.1 correct</th><th>Repaired</th><th>Regressed</th></tr>')
    for lang,c in data['languages'].items():
        for group,m in c.get('against_v62',{}).items():
            values=[lang,group,m['n'],m['v62_correct'],m['v631_correct'],m['repaired'],m['regressed']]
            s.append('<tr>'+''.join('<td>'+e(str(v))+'</td>' for v in values)+'</tr>')
    s.append('</table><p>Targeted cases were selected because v5 disagreed with the reference; controls were selected because v5 agreed. Do not interpret their pooled accuracy as a population estimate. Nearby records are correlated. Review policy compliance and reference ambiguity as well as label agreement.</p><h2>Changed cases and targeted examples</h2>')
    for r in data['rows']:
        if r['group']!='targeted' and r['v5_label']==r['v63_label']==r['v631_label'] and r['v5_certain']==r['v63_certain']==r['v631_certain']:continue
        s.append('<details><summary>'+e(r['record_id']+' · '+r['group']+' · '+r['v5_label']+' → '+r['v631_label'])+'</summary><blockquote>'+e(r['target_utterance'])+'</blockquote><p>Human consensus: '+e(r['human_consensus'])+'</p><p>V5: '+e(r['v5_comments'])+'</p><p>6.3.1: '+e(r['v631_comments'])+'</p><table>')
        s.append('<tr><td>6.3 comparison</td><td>'+e(r['v63_label'])+'</td><td>'+e(r['v63_comments'])+'</td></tr>')
        for turn in r['context_before']+[{'line':r['line'],'speaker':'TARGET','utterance':r['target_utterance']}]+r['context_after']:
            s.append('<tr>'+''.join('<td>'+e(str(turn[k]))+'</td>' for k in ('line','speaker','utterance'))+'</tr>')
        s.append('</table></details>')
    s.append('<p>Full group metrics, all label confusions and row audit: <a href="report.json">report.json</a>. Pending conditions are never treated as successful predictions.</p></html>')
    return '\n'.join(s)


def main():
    data=calculate();f=config.verify();out=config.BASE/f['results_dir']/'report';out.mkdir(parents=True,exist_ok=True)
    runner.atomic_write(out/'report.json',json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    runner.atomic_write(out/'report.html',render(data))
    print(json.dumps({l:{k:c[k] for k in ('complete','saved_records','expected_records')} for l,c in data['languages'].items()},indent=2))


if __name__=='__main__':main()
