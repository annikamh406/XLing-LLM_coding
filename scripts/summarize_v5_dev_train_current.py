#!/usr/bin/env python3
"""Completion audit and nonrepetition agreement for the full dev_train baseline."""
import collections
import hashlib
import itertools
import json
from pathlib import Path
from check_v5_dev_train_current import BASE, MANIFEST, tag, verify
from coordinate_v5_dev_train import complete, stem
from summarize_v5_nonrepetition import agreement, esc, kap, label, pct, read, table, yes

OUTPUT=BASE/'v5/results/dev_train_current_report'
LABELS=['rejection','denial','nonexistence','excluded','uncoded']


def analysis(rows,models):
    matched=[r for r in rows if r['human_1'] is not None and r['human_2'] is not None]
    consensus=[r for r in matched if r['human_1']==r['human_2']]
    result={'retained_n':len(rows),'matched_n':len(matched),'consensus_n':len(consensus),
            'matched_pairs':{},'all_available_pairs':{},'consensus':{},'matched_denial_rates':{}}
    for a,b in itertools.combinations(['human_1','human_2',*models],2):
        for subset,key in [(matched,'matched_pairs'),(rows,'all_available_pairs')]:
            result[key][a+' vs '+b]=agreement([r[a] for r in subset],[r[b] for r in subset])
    for coder in ['human_1','human_2',*models]:
        result['matched_denial_rates'][coder]=sum(r[coder]=='denial' for r in matched)/len(matched) if matched else None
    for model in models:
        counts=collections.Counter((r['human_1'],r[model]) for r in consensus)
        cells=[{'human':a,'model_label':b,'n':counts[a,b]} for a in LABELS for b in LABELS]
        support=collections.Counter(r['human_1'] for r in consensus)
        predicted=collections.Counter(r[model] for r in consensus)
        result['consensus'][model]={**agreement([r['human_1'] for r in consensus],[r[model] for r in consensus]),
          'support':dict(support),'predicted':dict(predicted),'cells':cells,
          'humans_rejection_model_denial':counts['rejection','denial'],
          'humans_denial_model_rejection':counts['denial','rejection'],
          'rejection_to_denial_rate':counts['rejection','denial']/support['rejection'] if support['rejection'] else None,
          'denial_to_rejection_rate':counts['denial','rejection']/support['denial'] if support['denial'] else None,
          'net_denial_count':predicted['denial']-support['denial'],
          'human_denial_rate':support['denial']/len(consensus) if consensus else None,
          'model_denial_rate':predicted['denial']/len(consensus) if consensus else None}
    return result


def calculate():
    frozen=verify();out=BASE/frozen['results_dir']
    result={'date':'2026-10-26','freeze_sha256':hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
      'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'policy':'Only complete, provenance-verified conditions enter agreement metrics. Exclude a record if either human marked repetition Yes. Missing flags are not affirmative repetition. Collapse Nonpossession into Nonexistence; retain Excluded and Uncoded. Consensus requires both human labels equal. Human columns can include alternates; no adjudicated gold.',
      'languages':{},'source_sha256':{}}
    for language,condition in frozen['languages'].items():
        records=read(BASE/condition['input']);refs={r['record_id']:r for r in read(BASE/condition['human_reference'])}
        statuses={};predictions={};sources=[BASE/condition['input'],BASE/condition['human_reference']]
        for model,short in [('gemma4:31b','gemma'),('qwen3.6:35b-a3b','qwen')]:
            prefix=stem(language,model,frozen)
            checkpoint=out/(prefix+'_checkpoint.json')
            state=json.loads(checkpoint.read_text()) if checkpoint.exists() else {'predictions':[],'raw_responses':[]}
            good=complete(language,model,frozen)
            recovery_files=sorted((out/'recovery'/prefix).glob('batch-*.json'))
            recovery=[dict(path=str(p.relative_to(BASE)),**json.loads(p.read_text())) for p in recovery_files]
            exhausted=[r for r in recovery if len(r['attempts'])>=3 and r['attempts'][-1]['status']!='success']
            amended_files=sorted((out/'recovery_interruption_resume'/prefix).glob('batch-*.json'))
            amended={p.name:json.loads(p.read_text()) for p in amended_files}
            legacy_exhausted=list(exhausted)
            exhausted=[r for r in exhausted if amended.get('batch-'+str(r['batch_number'])+'.json',{}).get('attempts',[{'status':'missing'}])[-1]['status']!='success']
            sources.extend([*recovery_files,*amended_files])
            coord={}
            for p in sorted((out/'coordination').glob(prefix+'_*.jsonl')):
                events=read(p);coord[p.name]=dict(collections.Counter(e['event'] for e in events));sources.append(p)
            info={'complete':good,'expected_records':len(records),'checkpoint_records':len(state['predictions']),
                  'checkpoint_batches':len(state['raw_responses']),
                  'recovered_batches':sum(b.get('attempt_count',1)>1 for b in state['raw_responses']),
                  'model_retried_batches':sum(sum(a['status'] in ('failed','success') for a in b.get('raw_response',{}).get('validation_recovery',{}).get('attempts',[]))>1 for b in state['raw_responses']),
                  'interrupted_requests_in_saved_batches':sum(sum(a['status'] in ('started','interrupted') for a in b.get('raw_response',{}).get('validation_recovery',{}).get('attempts',[])) for b in state['raw_responses']),
                  'legacy_exhausted_batch_numbers':[r['batch_number'] for r in legacy_exhausted],
                  'exhausted_batches':[{'batch':r['batch_number'],'record_ids':r['record_ids'],
                    'attempt_statuses':[a['status'] for a in r['attempts']], 'audit_path':r['path']} for r in exhausted],
                  'coordination_events':coord}
            for b in state['raw_responses']:
                expected={**frozen['decoding_options'],'seed':frozen['decoding_options']['seed']+b['batch_number']-1}
                actual=b.get('effective_decoding_options',b.get('decoding_options'))
                if model.startswith('qwen'):
                    attempts=b['raw_response']['validation_recovery']['attempts']
                    for a in attempts:
                        options=dict(a['effective_decoding_options']);budget=options.pop('num_predict')
                        if options!={k:v for k,v in expected.items() if k!='num_predict'} or budget not in ([8000,16000] if a['stage']==2 else [8000]):
                            raise ValueError('Unexpected decoding/recovery options')
                elif actual!=expected or b.get('attempt_count',1)!=1:raise ValueError('Unexpected Gemma inference settings')
            if good:
                path=out/(prefix+'_predictions.jsonl');raw=out/(prefix+'_raw_responses.jsonl')
                predictions[short]={r['record_id']:label(r['bloom_label']) for r in read(path)}
                sources.extend([path,raw])
            if checkpoint.exists():sources.append(checkpoint)
            statuses[short]=info
        rows=[];excluded=[]
        for record in records:
            rid=record['record_id'];ref=refs[rid];humans=[ref.get('coder_1') or {},ref.get('coder_2') or {}]
            if any(yes((h.get('flags') or {}).get('repetition')) for h in humans):excluded.append(rid);continue
            rows.append({'record_id':rid,'corpus':record.get('corpus'),
                         'human_1':label(humans[0].get('bloom_label')),'human_2':label(humans[1].get('bloom_label')),
                         **{m:p[rid] for m,p in predictions.items()}})
        result['languages'][language]={'runs':statuses,'input_n':len(records),'excluded_repetition_n':len(excluded),
          'excluded_record_ids':excluded,**analysis(rows,list(predictions)),'audit':rows,
          'human_sheets':[refs[records[0]['record_id']].get('coder_1_sheet'),refs[records[0]['record_id']].get('coder_2_sheet')],
          'corpora':{c:analysis([r for r in rows if r['corpus']==c],list(predictions)) for c in sorted({r['corpus'] for r in rows if r['corpus'] is not None})}}
        for p in sources:result['source_sha256'][str(p.relative_to(BASE))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def render(data):
    s='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Full dev_train baseline results</title><style>body{font:15px system-ui;max-width:1400px;margin:28px auto;padding:0 20px;color:#222;line-height:1.5}h1{font-size:26px}h2{font-size:21px;margin-top:32px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:8px;border-bottom:1px solid #ddd;white-space:nowrap}th{background:#f3f4f5}.scroll{overflow:auto}details{margin:20px 0}summary{cursor:pointer}a{color:#075b99}</style><h1>Full dev_train baseline results</h1><p>October 26, 2026. Current unchanged prompts at the validation settings: Gemma batch 1; Qwen batch 5; NFC on Hebrew Qwen only.</p><p>The first round stopped Qwen Spanish, Hebrew and Tagalog after scheduler preemptions consumed their original recovery slots. The condo-only interruption amendment retains the old audits and counts genuine response failures separately from interruptions. Incomplete conditions are excluded from agreement metrics; current completion is shown below.</p>'''
    s+='<h2>Completion and recovery</h2>'+table(['Language','Model','Status','Saved / expected records','Saved batches','Recovered batches','Model-retried batches','Interruptions in saved batches'],[[lang.title(),model.title(),'Complete' if m['complete'] else 'Incomplete',f'{m["checkpoint_records"]} / {m["expected_records"]}',m['checkpoint_batches'],m['recovered_batches'],m['model_retried_batches'],m['interrupted_requests_in_saved_batches']] for lang,d in data['languages'].items() for model,m in d['runs'].items()])
    s+='<h2>Agreement with human consensus</h2><p>Both humans must agree after label collapse. Repetition exclusion uses either human’s Yes flag. This is a consensus subset, not adjudicated truth.</p>'+table(['Language','Consensus n','Gemma agreement','Qwen agreement'],[[lang.title(),d['consensus_n']]+[pct(d['consensus'].get(model,{}).get('agreement')) for model in ['gemma','qwen']] for lang,d in data['languages'].items()])
    s+='<h2>Denial versus Rejection</h2><p>Read each direction as what the humans agreed on → what the model predicted. Percentages use the corresponding human-consensus class as denominator. Net Denial includes inflows and outflows from all classes.</p>'+table(['Language','Model','Human Rejection → model Denial','% of Rejection','Human Denial → model Rejection','% of Denial','Human Denial share','Model Denial share','Net Denial count'],[[lang.title(),model.title(),c['humans_rejection_model_denial'],pct(c['rejection_to_denial_rate']),c['humans_denial_model_rejection'],pct(c['denial_to_rejection_rate']),pct(c['human_denial_rate']),pct(c['model_denial_rate']),f'{c["net_denial_count"]:+d}'] for lang,d in data['languages'].items() for model,c in d['consensus'].items()])
    s+='<h2>Pairwise agreement on identical double-labeled records</h2><p>Human columns include the main coders and any alternates. Every pair within a language uses the same nonrepetition records. Percentage / Cohen’s κ.</p>'+table(['Language','Matched n','Human–human','Gemma–H1','Gemma–H2','Qwen–H1','Qwen–H2','Gemma–Qwen'],[[lang.title(),d['matched_n']]+[pct(d['matched_pairs'][p]['agreement'])+' / '+kap(d['matched_pairs'][p]['kappa']) if p in d['matched_pairs'] else '—' for p in ['human_1 vs human_2','human_1 vs gemma','human_2 vs gemma','human_1 vs qwen','human_2 vs qwen','gemma vs qwen']] for lang,d in data['languages'].items()])
    for lang,d in data['languages'].items():
        s+='<details><summary>'+lang.title()+' — full counts, directional mismatches, and run diagnostics</summary>'
        s+=f'<p>Original rows: {d["input_n"]}; repetition exclusions: {d["excluded_repetition_n"]}; retained: {d["retained_n"]}. Human sheets: '+esc('/'.join(d['human_sheets']))+'.</p>'
        for model,m in d['consensus'].items():
            s+='<h3>'+model.title()+' consensus confusion counts</h3>'
            cells={(c['human'],c['model_label']):c['n'] for c in m['cells']}
            s+=table(['Human consensus ↓ / model →']+[x.title() for x in LABELS],[[a.title()]+[cells[a,b] for b in LABELS] for a in LABELS])
        s+='<h3>All available pairwise labels</h3>'+table(['Pair','n','Agreement','κ'],[[p,m['n'],pct(m['agreement']),kap(m['kappa'])] for p,m in d['all_available_pairs'].items()])
        for model,m in d['runs'].items():
            if m['exhausted_batches']:
                s+='<h3>'+model.title()+' stopped batches</h3>'+table(['Batch','Attempt statuses','Recovery audit'],[[e['batch'],', '.join(e['attempt_statuses']),e['audit_path']] for e in m['exhausted_batches']])
            s+='<h3>'+model.title()+' scheduling events</h3>'+table(['Job audit','Events'],[[p,', '.join(f'{k}: {v}' for k,v in counts.items())] for p,counts in m['coordination_events'].items()])
        for corpus,c in d['corpora'].items():
            s+='<h3>'+esc(corpus)+f' · {c["matched_n"]} double-labeled; {c["consensus_n"]} consensus</h3>'+table(['Model','Consensus agreement','Rejection → Denial','Denial → Rejection'],[[m.title(),pct(v['agreement']),v['humans_rejection_model_denial'],v['humans_denial_model_rejection']] for m,v in c['consensus'].items()])
        s+='</details>'
    s+='<h2>Next step</h2><p>Finish any incomplete conditions using the condo-only interruption amendment, preserving successful batches and every original audit. The original launcher cannot resolve an exhausted legacy budget. Infrastructure interruptions and completed model-response failures are recorded separately; both have bounded continuation rules. These scheduling interruptions do not justify changing NFC preprocessing.</p><p>Use the complete dev_train baselines to investigate prompt revisions. No prompt was edited, no examples were inspected for tuning, and no check/lockbox inference or scoring occurred in this report. Source hashes and nonrepetition row audits are in <a href="report.json">report.json</a>. No independent-token significance claims are made.</p></html>'
    return s


if __name__=='__main__':
    data=calculate();OUTPUT.mkdir(exist_ok=True)
    (OUTPUT/'report.json').write_text(json.dumps(data,indent=2)+'\n');(OUTPUT/'report.html').write_text(render(data))
    for lang,d in data['languages'].items():
        print(lang,'matched',d['matched_n'],'consensus',d['consensus_n'])
        for model,m in d['consensus'].items():print(model,pct(m['agreement']),'R>D',m['humans_rejection_model_denial'],pct(m['rejection_to_denial_rate']),'D>R',m['humans_denial_model_rejection'],pct(m['denial_to_rejection_rate']),'net denial',m['net_denial_count'])
