#!/usr/bin/env python3
"""Directional model/consensus confusion matrices on nonrepetition dev check 1."""
import collections
import hashlib
import json
from pathlib import Path
from summarize_v5_individual_coders import calculate_individuals
from summarize_v5_nonrepetition import BASE, esc, pct, table

OUTPUT = BASE/'v5/results/dev_check_1_consensus_details'
LABELS = ['rejection', 'denial', 'nonexistence', 'excluded', 'uncoded']


def summarize(rows):
    result = {'n': len(rows), 'support': dict(collections.Counter(r['label'] for r in rows)), 'models': {}}
    for model in ['gemma', 'qwen']:
        counts = collections.Counter((r['label'], r[model]) for r in rows)
        assert all(a in LABELS and b in LABELS for a,b in counts)
        cells = []
        for human in LABELS:
            for predicted in LABELS:
                n = counts[human,predicted]
                human_n = sum(counts[human,p] for p in LABELS)
                predicted_n = sum(counts[h,predicted] for h in LABELS)
                cells.append({'consensus': human, 'model_label': predicted, 'n': n,
                              'consensus_n': human_n, 'predicted_n': predicted_n,
                              'pct_of_consensus': n/human_n if human_n else None,
                              'pct_of_prediction': n/predicted_n if predicted_n else None})
        agreed = sum(counts[k,k] for k in LABELS)
        assert sum(c['n'] for c in cells) == len(rows)
        mismatches = sorted([c for c in cells if c['consensus'] != c['model_label'] and c['n']], key=lambda c: (-c['n'],c['consensus'],c['model_label']))
        result['models'][model] = {'n': len(rows), 'agree_n': agreed, 'agreement': agreed/len(rows) if rows else None,
                                   'disagree_n': len(rows)-agreed, 'cells': cells, 'mismatches': mismatches}
    return result


def calculate():
    source = calculate_individuals()
    result = {'analysis_policy': 'human-consensus-nonrepetition-directional-v1',
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'source_sha256': source['source_sha256'], 'attribution_policy': source['attribution_policy'],
              'definition': 'Both human Bloom labels available and equal after collapsing Nonpossession into Nonexistence. Exclude rows if either human explicitly marked repetition Yes. Retain Excluded and Uncoded as classes. Consensus is agreement between two humans, not adjudicated truth.',
              'labels': LABELS, 'languages': {}}
    for lang,d in source['languages'].items():
        # One row per record: slot 1 avoids counting each agreed judgment twice.
        rows = [r for r in d['judgment_audit'] if r['slot'] == 1 and r['other_label'] is not None and r['label'] == r['other_label']]
        double = sum(r['slot']==1 and r['other_label'] is not None for r in d['judgment_audit'])
        result['languages'][lang] = {**summarize(rows), 'nonrepetition_records': d['remaining_records'],
                                    'double_labeled_n': double, 'humans_disagree_n': double-len(rows),
                                    'audit': rows,
                                    'corpora': {c: summarize([r for r in rows if r['corpus']==c]) for c in sorted({r['corpus'] for r in rows if r['corpus'] is not None})}}
    return result


def heatmap(m):
    cells = {(c['consensus'],c['model_label']):c for c in m['cells']}
    s = '<table class="matrix"><caption>Rows: human consensus · Columns: model output</caption><thead><tr><th>Consensus ↓ / Model →</th>' + ''.join('<th>'+k.title()+'</th>' for k in LABELS) + '</tr></thead><tbody>'
    for h in LABELS:
        support = cells[h,LABELS[0]]['consensus_n']
        s += '<tr><th>'+h.title()+f'<br><span class="support">n={support}</span></th>'
        for predicted in LABELS:
            c = cells[h,predicted];v=c['pct_of_consensus']
            text = f"Model: {predicted.title()}\nHuman consensus: {h.title()}\nCount: {c['n']}\nOf this consensus class: {pct(v)} ({c['n']}/{support})\nOf this model output: {pct(c['pct_of_prediction'])} ({c['n']}/{c['predicted_n']})"
            alpha = 0 if v is None else .65*v
            s += f'<td style="background:rgba(0,114,178,{alpha:.4f})"><button data-detail="{esc(text)}" aria-label="{esc(text)}">{c["n"]}<br><span>{pct(v)}</span></button></td>'
        s += '</tr>'
    return s + '</tbody></table>'


def render(data):
    s = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Agreement with human consensus</title><style>body{font:15px system-ui;max-width:1500px;margin:28px auto;padding:0 20px;color:#222;line-height:1.5}h1{font-size:26px}h2{font-size:22px;margin-top:36px}h3{font-size:18px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:8px;border-bottom:1px solid #ddd}th{background:#f3f4f5}.scroll{overflow:auto}.panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,600px),1fr));gap:28px}.matrix{table-layout:fixed}.matrix th,.matrix td{text-align:center;padding:5px;font-size:12px}.matrix caption{text-align:left;margin-bottom:10px;font-size:13px}.matrix th:first-child{width:120px}.matrix td{border:2px solid white}.matrix button{font:inherit;color:inherit;background:transparent;border:0;width:100%;padding:7px 0;cursor:help}.matrix button span,.support{font-size:12px}.tooltip{position:fixed;z-index:2;pointer-events:none;background:white;border:1px solid #aaa;box-shadow:0 2px 10px #0002;border-radius:4px;padding:10px;white-space:pre-line;font-size:14px;max-width:320px}.tooltip[hidden]{display:none}a{color:#075b99}details{margin:20px 0}</style><h1>Agreement with human consensus</h1><p>Dev check 1 · Repetition rows excluded if either human marked Yes. Consensus requires both humans to give the same label. Nonpossession is collapsed into Nonexistence; Excluded and Uncoded remain classes. Missing labels do not form consensus.</p><p><strong>Rows are what the humans agreed on; columns are what the model said.</strong> Cells show counts and percentages within each human-consensus row. Hover, focus or tap a cell for both directions: percentage of the human class and percentage of that model output. The diagonal represents agreement.</p><p>This subset omits human disagreements and is not an adjudicated gold standard. Its agreement rates should not be compared directly to all-row pairwise rates. <a href="report.json">Data and audit</a> · <a href="confusion_matrices.png">Static figure</a> · <a href="confusion_matrices.pdf">PDF</a></p>'''
    s += table(['Language','Both humans labeled','Humans disagree (omitted)','Consensus n','Gemma agreement','Qwen agreement'], [[lang.title(),d['double_labeled_n'],d['humans_disagree_n'],d['n'],pct(d['models']['gemma']['agreement']),pct(d['models']['qwen']['agreement'])] for lang,d in data['languages'].items()])
    for lang,d in data['languages'].items():
        s += '<h2>'+lang.title()+f' · {d["n"]} consensus records</h2><div class="panels">'
        for model,m in d['models'].items():
            s += '<section><h3>'+model.title()+f' · {pct(m["agreement"])} agreement ({m["agree_n"]}/{m["n"]})</h3><div class="scroll">'+heatmap(m)+'</div></section>'
        s += '</div><h3>Directional disagreements</h3><p>Each row is a specific model output and the different label both humans gave.</p>'
        s += table(['Model','Model said','Humans agreed on','Count','% of that human class','% of that model output'], [[model.title(),c['model_label'].title(),c['consensus'].title(),c['n'],pct(c['pct_of_consensus']),pct(c['pct_of_prediction'])] for model,m in d['models'].items() for c in m['mismatches']])
        s += '<details><summary>Agreement grouped by what the model said</summary>'
        for model,m in d['models'].items():
            diagonal=[c for c in m['cells'] if c['model_label']==c['consensus']]
            s += '<h3>'+model.title()+'</h3>'+table(['Model output','Times output on consensus subset','Humans agreed with output','Agreement given this output'],[[c['model_label'].title(),c['predicted_n'],c['n'],pct(c['pct_of_prediction'])] for c in diagonal])
        s += '</details>'
        if d['corpora']:
            s += '<details><summary>Tagalog corpus breakdown</summary>'
            for corpus,sub in d['corpora'].items():
                s += '<h3>'+esc(corpus)+f' · {sub["n"]} consensus records</h3><div class="panels">'
                for model,m in sub['models'].items():s += '<section><h3>'+model.title()+'</h3><div class="scroll">'+heatmap(m)+'</div></section>'
                s += '</div>'
            s += '</details>'
    return s + '''<p>No new inference or evaluation of dev check 2 or lockbox data. Counts are descriptive; tokens share transcripts and children. The attribution audit uses main sheet coders for blanks and merges Laurize into LM.</p><div id="tooltip" class="tooltip" role="tooltip" hidden></div><script>
const tip=document.getElementById('tooltip');
for(const button of document.querySelectorAll('[data-detail]')){
 const show=e=>{tip.textContent=button.dataset.detail;tip.hidden=false;const b=button.getBoundingClientRect();const x=e.type==='focus'?b.x+b.width/2:e.clientX;const y=e.type==='focus'?b.y+b.height/2:e.clientY;tip.style.left=Math.max(8,Math.min(x+12,innerWidth-tip.offsetWidth-8))+'px';tip.style.top=Math.max(8,Math.min(y+12,innerHeight-tip.offsetHeight-8))+'px';};
 for(const type of ['pointerenter','pointermove','focus','click'])button.addEventListener(type,show);
 for(const type of ['pointerleave','blur'])button.addEventListener(type,()=>tip.hidden=true);
}document.addEventListener('keydown',e=>{if(e.key==='Escape')tip.hidden=true;});
</script></html>'''


if __name__ == '__main__':
    data=calculate();OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'report.json').write_text(json.dumps(data,indent=2)+'\n')
    (OUTPUT/'report.html').write_text(render(data))
    plot=[]
    for lang,d in data['languages'].items():
        print(lang,d['n'])
        for model,m in d['models'].items():
            print(model,pct(m['agreement']),[(c['model_label'],c['consensus'],c['n']) for c in m['mismatches'][:3]])
            plot += [{'language':lang.title(),'model':model.title(),**c} for c in m['cells']]
    (OUTPUT/'plot_data.json').write_text(json.dumps(plot,indent=2)+'\n')
