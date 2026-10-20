#!/usr/bin/env python3
"""Pairwise validation agreement after the approved human-union repetition filter."""
import collections
import hashlib
import html
import itertools
import json
from pathlib import Path
from check_hebrew_nfc_validation import combined
from check_v5_validation_freeze import BASE

OUTPUT=BASE/'v5/results/dev_check_1_nonrepetition'
CODERS=['human_1','human_2','gemma','qwen']
LANGUAGES={'english':'en','german':'de','hebrew':'he','spanish':'es','tagalog':'tl'}

def read(path):return [json.loads(line) for line in path.read_text().splitlines()]
def yes(value):return str(value or '').strip().lower()=='yes'
def label(value):
    if value is None:return None
    mapping={'Nonpossession':'nonexistence','Nonposession':'nonexistence','Nonexistence':'nonexistence',
             'Rejection':'rejection','Denial':'denial','Uncoded':'uncoded','Excluded':'excluded'}
    if value not in mapping:raise ValueError('Unrecognized label: '+str(value))
    return mapping[value]

def agreement(a,b):
    pairs=[(x,y) for x,y in zip(a,b) if x is not None and y is not None]
    n=len(pairs)
    if not n:return {'n':0,'agree_n':0,'agreement':None,'kappa':None}
    left=collections.Counter(x for x,y in pairs);right=collections.Counter(y for x,y in pairs)
    agreed=sum(x==y for x,y in pairs);chance=sum(left[k]*right[k] for k in left)/n**2
    return {'n':n,'agree_n':agreed,'agreement':agreed/n,
            'kappa':None if chance==1 else (agreed/n-chance)/(1-chance)}

def all_pairs(rows):
    return {left+' vs '+right:agreement([r[left] for r in rows],[r[right] for r in rows])
            for left,right in itertools.combinations(CODERS,2)}

def summarize(rows):
    common=[r for r in rows if r['human_1'] is not None and r['human_2'] is not None]
    consensus=[r for r in common if r['human_1']==r['human_2']]
    matched=all_pairs(common);baseline=matched['human_1 vs human_2']['agreement']
    relative={}
    for model in ['gemma','qwen']:
        metrics=[matched[f'{human} vs {model}'] for human in ['human_1','human_2']]
        relative[model]={'minus_human_human_pp':[(m['agreement']-baseline)*100 if baseline is not None else None for m in metrics],
                         'mean_human_agreement':sum(m['agreement'] for m in metrics)/2 if common else None}
    return {'records':len(rows),'common_double_coded_n':len(common),'matched_pairs':matched,
            'all_available_pairs':all_pairs(rows),'relative_to_humans':relative,
            'consensus':{model:agreement([r['human_1'] for r in consensus],[r[model] for r in consensus]) for model in ['gemma','qwen']}}

def calculate():
    validation=combined()
    if validation['issues'] or validation['validated_runs']!=10:
        raise ValueError('All selected validation conditions must pass provenance and completeness checks')
    result={'date':'2026-10-20','analysis_policy':'dev-check-1-human-union-nonrepetition-v1',
        'analysis_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'policy_note':'Exclude a record from every pair if either human explicitly marked repetition Yes. Model repetition flags do not select the analysis rows. Missing flags are not affirmative repetition judgments; missing Bloom labels remain missing. No source, prediction or old frozen report is modified.',
        'label_mapping':'Collapse Nonpossession/Nonposession into Nonexistence; retain Excluded and Uncoded.',
        'primary_comparison':'Same nonrepetition rows with both human labels available for all six coder pairs. Also report each pair on all its available nonmissing rows.',
        'preprocessing_note':'Qwen Hebrew uses NFC; other selected runs retain their original input representation.',
        'languages':{},'source_sha256':{}}
    for language,code in LANGUAGES.items():
        sample_path=BASE/'splits'/language/'dev_check_1.jsonl';reference_path=sample_path.with_name('dev_check_1_human_reference.jsonl')
        sample=read(sample_path);refs={r['record_id']:r for r in read(reference_path)}
        sources=[sample_path,reference_path];predictions={}
        for model,slug in [('gemma','gemma4_31b'),('qwen','qwen3.6_35b-a3b')]:
            folder=BASE/'v5/results'/('dev_check_1_hebrew_nfc' if language=='hebrew' and model=='qwen' else 'dev_check_1')
            path=next(folder.glob(f'dev_check_1_{slug}_bloom_v5_*-{code}-full-b*-t0-s20261009_predictions.jsonl'))
            predictions[model]={r['record_id']:r for r in read(path)};sources.append(path)
        rows=[];flag_counts=collections.Counter();sheets={k:collections.Counter() for k in ['human_1','human_2']}
        for record in sample:
            ref=refs[record['record_id']];h1=ref.get('coder_1') or {};h2=ref.get('coder_2') or {}
            f1=(h1.get('flags') or {}).get('repetition');f2=(h2.get('flags') or {}).get('repetition')
            a,b=yes(f1),yes(f2)
            flag_counts['human_1_yes']+=a;flag_counts['human_2_yes']+=b;flag_counts['both_yes']+=a and b
            for name,value in [('human_1',f1),('human_2',f2)]:
                if value is None or not str(value).strip():flag_counts[name+'_blank_or_missing']+=1
            sheets['human_1'][ref.get('coder_1_sheet')]+=1;sheets['human_2'][ref.get('coder_2_sheet')]+=1
            row={'record_id':record['record_id'],'corpus':record.get('corpus'),'human_1':label(h1.get('bloom_label')),
                 'human_2':label(h2.get('bloom_label')),'exclude_repetition':a or b}
            for model in ['gemma','qwen']:row[model]=label(predictions[model][row['record_id']]['bloom_label'])
            rows.append(row)
        kept=[r for r in rows if not r['exclude_repetition']]
        output={'input_records':len(rows),'excluded_repetition_records':len(rows)-len(kept),
                'human_sheet_ids':{k:dict(v) for k,v in sheets.items()},'repetition_flag_counts':dict(flag_counts),**summarize(kept)}
        output['included_record_ids']=[r['record_id'] for r in kept]
        output['excluded_record_ids']=[r['record_id'] for r in rows if r['exclude_repetition']]
        output['corpora']={corpus:summarize([r for r in kept if r['corpus']==corpus])
                          for corpus in sorted({r['corpus'] for r in kept if r['corpus'] is not None})}
        result['languages'][language]=output
        for path in sources:result['source_sha256'][str(path.relative_to(BASE))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result

def pct(value):return '—' if value is None else f'{value*100:.1f}%'
def kap(value):return '—' if value is None else f'{value:.3f}'
def esc(value):return html.escape(str(value))
def table(head,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def render(data):
    doc='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nonrepetition pairwise agreement</title><style>body{font:16px system-ui,sans-serif;max-width:1300px;margin:28px auto;padding:0 22px;color:#222;line-height:1.5}h1{font-size:27px}h2{font-size:21px;margin-top:30px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:9px;border-bottom:1px solid #ddd;text-align:left;white-space:nowrap}th{background:#f3f4f5}.scroll{overflow:auto}details{border:1px solid #ddd;margin:14px 0;padding:12px}summary{cursor:pointer;font-weight:600}</style><h1>Nonrepetition pairwise agreement</h1><p>Dev check 1 · October 20, 2026. All ten selected runs passed provenance and coverage checks.</p>'''
    doc+='<p><strong>Exclusion rule:</strong> remove a row from every comparison if either human explicitly marked repetition Yes. Model flags do not decide exclusions. Missing human flags do not count as Yes. Nonpossession is collapsed into Nonexistence; Excluded and Uncoded remain labels. Qwen Hebrew uses the documented NFC amendment.</p>'
    pairs=['human_1 vs human_2','human_1 vs gemma','human_2 vs gemma','human_1 vs qwen','human_2 vs qwen','gemma vs qwen']
    head=['Language','Matched n','Human 1–2','Gemma–H1','Gemma–H2','Qwen–H1','Qwen–H2','Gemma–Qwen']
    summary=[];kappas=[];filterrows=[]
    for lang,d in data['languages'].items():
        summary.append([lang.title(),d['common_double_coded_n']]+[pct(d['matched_pairs'][p]['agreement']) for p in pairs])
        kappas.append([lang.title(),d['common_double_coded_n']]+[kap(d['matched_pairs'][p]['kappa']) for p in pairs])
        filterrows.append([lang.title(),d['input_records'],d['excluded_repetition_records'],d['records'],d['common_double_coded_n'],', '.join(d['human_sheet_ids']['human_1']),', '.join(d['human_sheet_ids']['human_2'])])
    doc+='<h2>Agreement on the same records</h2><p>Every cell within a language uses the identical nonrepetition subset with both human labels available. These percentages are pairwise agreement, not accuracy against a preferred coder.</p>'+table(head,summary)
    doc+='<h2>Cohen’s kappa on the same records</h2>'+table(head,kappas)
    doc+='<h2>Interpretation</h2><ul><li>Read model–human agreement relative to the human–human baseline, rather than expecting perfect consensus-subset agreement. Neither human is designated the correct answer.</li><li>German has substantial human disagreement and coder asymmetry. A model being closer to one coder does not establish which coder is correct.</li><li>Tagalog needs its corpus breakdown: MPI and the new corpus have different annotation coverage and human reliability.</li><li>Agreement between Gemma and Qwen is a useful comparison, not independent evidence that either model’s shared judgment is correct.</li></ul>'
    doc+='<h2>Rows and coder labels</h2>'+table(['Language','Original records','Excluded as repetition','Remaining','Both humans labeled','Human 1 sheet','Human 2 sheet'],filterrows)
    doc+='<p>Sheet IDs identify the workbook coding columns, not guaranteed individual annotators: some records list alternate coders. Repetition marking is incomplete or asymmetric. In particular, German MP and Hebrew YS have no explicit repetition Yes entries; this filter still removes rows marked by the other human. It cannot remove unmarked repetitions.</p>'
    for lang,d in data['languages'].items():
        doc+='<details><summary>'+esc(lang.title()+' — all available pairwise comparisons and corpus details')+'</summary>'
        doc+='<p>Each pair below uses all remaining rows where those two coders have labels. Denominators therefore differ; use the matched table above for direct relative comparisons.</p>'
        doc+=table(['Pair','n','Agreed','Agreement','κ'],[[p,m['n'],m['agree_n'],pct(m['agreement']),kap(m['kappa'])] for p,m in d['all_available_pairs'].items()])
        doc+='<h3>Difference from human–human agreement on the matched subset</h3>'+table(['Model','Against H1','Against H2'],[[model.title()]+['—' if x is None else f'{x:+.1f} percentage points' for x in m['minus_human_human_pp']] for model,m in d['relative_to_humans'].items()])
        for corpus,c in d['corpora'].items():
            doc+='<h3>'+esc(corpus)+f' · {c["records"]} nonrepetition records; {c["common_double_coded_n"]} double-coded</h3>'
            doc+=table(['Pair','Matched n','Agreement','κ'],[[p,m['n'],pct(m['agreement']),kap(m['kappa'])] for p,m in c['matched_pairs'].items()])
            doc+='<p>All available rows:</p>'+table(['Pair','n','Agreement','κ'],[[p,m['n'],pct(m['agreement']),kap(m['kappa'])] for p,m in c['all_available_pairs'].items()])
        doc+='</details>'
    doc+='<h2>Analysis record</h2><p>This repetition exclusion was explicitly requested after the first validation report. Original predictions, references, frozen scoring templates and earlier reports remain unchanged. The machine-readable report contains inclusion/exclusion IDs and source hashes so this amended analysis can be reproduced. No new inference, dev_check_2 or lockbox access occurred.</p><p>Results are descriptive; multiple tokens share transcripts and children. Differences shown are not confidence intervals or independent-token significance claims.</p><p><a href="report.json">Machine-readable results and analysis policy</a></p></html>'
    return doc

if __name__=='__main__':
    result=calculate();OUTPUT.mkdir(exist_ok=True)
    (OUTPUT/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    (OUTPUT/'report.html').write_text(render(result))
    for lang,d in result['languages'].items():
        print(lang,'excluded',d['excluded_repetition_records'],'retained',d['records'],'matched',d['common_double_coded_n'])
        for pair,m in d['matched_pairs'].items():print(' ',pair,m['n'],pct(m['agreement']),kap(m['kappa']))
