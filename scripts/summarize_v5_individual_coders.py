#!/usr/bin/env python3
"""Attribute blank coder names to the sheet’s main coder, per user clarification."""
import collections
import hashlib
import json
from pathlib import Path
from summarize_v5_nonrepetition import BASE, LANGUAGES, agreement, calculate, esc, kap, label, pct, read, table

OUTPUT = BASE/'v5/results/dev_check_1_individual_coders'


def identity(human, sheet, slot):
    raw = human.get('coded_by_raw')
    name = ' '.join(str(raw or '').split()).casefold()
    # User-confirmed identity: Laurize is the main Tagalog coder LM.
    if name in {'laurize', 'lm'} and sheet == 'LM':
        return 'main:LM', None
    # User-confirmed convention: blanks mean the main coder associated with the sheet.
    if not name and not sheet:
        raise ValueError("Blank attribution requires a main-coder sheet ID")
    return ('named:' + name if name else f'main:{sheet}'), name or None


def metrics(rows):
    result = {'judgments': len(rows), 'record_ids': [r['record_id'] for r in rows]}
    for model in ['gemma', 'qwen']:
        result[model] = agreement([r['label'] for r in rows], [r[model] for r in rows])
    matched = [r for r in rows if r['other_label'] is not None]
    result['matched'] = {'n': len(matched)}
    for partner in ['other_label', 'gemma', 'qwen']:
        result['matched'][partner] = agreement([r['label'] for r in matched], [r[partner] for r in matched])
    result['counterparts'] = {}
    for key in sorted({r['other_identity'] for r in matched}):
        subset = [r for r in matched if r['other_identity'] == key]
        result['counterparts'][key] = {partner: agreement([r['label'] for r in subset], [r[partner] for r in subset])
                                      for partner in ['other_label', 'gemma', 'qwen']}
    return result


def calculate_individuals():
    baseline = calculate()
    result = {'date': baseline['date'], 'analysis_policy': 'sheet-main-coder-attribution-nonrepetition-v3',
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'source_sha256': baseline['source_sha256'], 'repetition_policy': baseline['policy_note'],
              'attribution_policy': 'User clarification: blank coded_by_raw means the main coder associated with the sheet (e.g. EB). Explicit names identify alternate coders, normalized for whitespace and case. Confirmed alias: Laurize = LM on the Tagalog LM sheet. Main coders retain sheet initials; other identities are not linked across languages or between initials and full names without a confirmed mapping.',
              'languages': {}}
    for language, code in LANGUAGES.items():
        base = baseline['languages'][language]
        included = set(base['included_record_ids'])
        refs = {r['record_id']: r for r in read(BASE/'splits'/language/'dev_check_1_human_reference.jsonl')}
        predictions = {}
        for model, slug in [('gemma', 'gemma4_31b'), ('qwen', 'qwen3.6_35b-a3b')]:
            folder = BASE/'v5/results'/('dev_check_1_hebrew_nfc' if language == 'hebrew' and model == 'qwen' else 'dev_check_1')
            paths = list(folder.glob(f'dev_check_1_{slug}_bloom_v5_*-{code}-full-b*-t0-s20261009_predictions.jsonl'))
            assert len(paths) == 1, paths
            predictions[model] = {r['record_id']: label(r['bloom_label']) for r in read(paths[0])}
        judgments = []
        pair_groups = collections.defaultdict(list)
        for record in read(BASE/'splits'/language/'dev_check_1.jsonl'):
            rid = record['record_id']
            if rid not in included:
                continue
            ref = refs[rid]
            humans = [ref.get(f'coder_{slot}') or {} for slot in [1, 2]]
            identities = [identity(h, ref.get(f'coder_{slot}_sheet'), slot) for slot, h in enumerate(humans, 1)]
            labels = [label(h.get('bloom_label')) for h in humans]
            for index, human in enumerate(humans):
                if labels[index] is None:
                    continue
                judgments.append({'record_id': rid, 'corpus': record.get('corpus'),
                                  'identity': identities[index][0], 'name': identities[index][1],
                                  'coded_by_raw': human.get('coded_by_raw'), 'slot': index+1,
                                  'sheet': ref.get(f'coder_{index+1}_sheet'), 'label': labels[index],
                                  'other_identity': identities[1-index][0], 'other_label': labels[1-index],
                                  **{m: predictions[m][rid] for m in predictions}})
            if all(x is not None for x in labels):
                pair_groups[(identities[0][0], identities[1][0])].append((rid, *labels))
        groups = {}
        for key in sorted({r['identity'] for r in judgments}):
            rows = [r for r in judgments if r['identity'] == key]
            groups[key] = {**metrics(rows), 'explicit_name': rows[0]['name'] is not None,
                           'display': rows[0]['name'].title() if rows[0]['name'] else f'{rows[0]["sheet"]} (main coder)',
                           'raw_names': sorted({str(r['coded_by_raw']) for r in rows if r['coded_by_raw'] is not None}),
                           'sheets': sorted({r['sheet'] for r in rows}),
                           'corpora': {c: metrics([r for r in rows if r['corpus'] == c]) for c in sorted({r['corpus'] for r in rows if r['corpus'] is not None})}}
        pairs = [{'left': left, 'right': right, 'record_ids': [r[0] for r in rows],
                  **agreement([r[1] for r in rows], [r[2] for r in rows])}
                 for (left, right), rows in sorted(pair_groups.items())]
        assert sum(g['judgments'] for g in groups.values()) == len(judgments)
        assert sum(p['n'] for p in pairs) == base['common_double_coded_n']
        for model in predictions:
            assert sum(g[model]['n'] for g in groups.values()) == len(judgments)
        result['languages'][language] = {'remaining_records': len(included), 'excluded_records': base['excluded_repetition_records'],
            'alternate_coder_judgments': sum(r['name'] is not None for r in judgments),
            'main_coder_judgments': sum(r['name'] is None for r in judgments),
            'groups': groups, 'human_pairs': pairs, 'judgment_audit': judgments}
    return result


def render(data):
    doc = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Agreement by individual coder</title><style>body{font:16px system-ui;max-width:1350px;margin:28px auto;padding:0 22px;line-height:1.5;color:#222}h1{font-size:27px}h2{font-size:22px;margin-top:32px}h3{font-size:18px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:8px;border-bottom:1px solid #ddd;text-align:left;white-space:nowrap}th{background:#f3f4f5}.scroll{overflow:auto}details{margin:16px 0}summary{cursor:pointer;font-weight:600}</style><h1>Agreement by individual coder</h1><p>Dev check 1 · October 20, 2026</p>'''
    doc += '<p>Per the user-confirmed annotation convention, blank <code>coded_by_raw</code> values belong to the main coder associated with the sheet (e.g. EB). Explicit names identify alternate coders, except the user-confirmed alias Laurize = LM, which is merged with LM. Main coders are displayed using sheet initials; alternate names are grouped within language after normalizing case and whitespace. Other initials and full names are not merged without a confirmed mapping.</p><p>Exclude a record from all comparisons if either human marked repetition Yes (779 records removed). Nonpossession is collapsed into Nonexistence; Excluded and Uncoded remain labels. All ten model runs passed completeness and provenance checks. No adjudicated gold standard is assumed.</p>'
    doc += '<p><a href="plots.html">Agreement plots: human baselines and model comparisons</a></p><h2>Attribution coverage</h2><p>Counts are labeled human judgments, so one record may contribute two judgments.</p>' + table(['Language', 'Alternate-coder judgments', 'Main-coder judgments'], [[lang.title(), d['alternate_coder_judgments'], d['main_coder_judgments']] for lang,d in data['languages'].items()])
    for lang, d in data['languages'].items():
        doc += '<h2>'+esc(lang.title())+'</h2>'
        for explicit in [False, True]:
            doc += '<h3>'+('Alternate coders' if explicit else 'Main coders')+'</h3>'
            groups = [g for g in d['groups'].values() if g['explicit_name'] == explicit]
            if not groups:
                doc += '<p>No labeled nonrepetition rows in this category.</p>'
                continue
            doc += '<p>All available labeled rows for each coder. Agreement and Cohen’s κ are shown; sample sizes differ.</p>'
            doc += table(['Coder / source', 'n', 'Gemma agreement', 'κ', 'Qwen agreement', 'κ'], [[g['display'],g['judgments'],pct(g['gemma']['agreement']),kap(g['gemma']['kappa']),pct(g['qwen']['agreement']),kap(g['qwen']['kappa'])] for g in groups])
            doc += '<details><summary>Same-record comparison with the other human judgment</summary><p>Within each row, both models and the other human are compared against this coder on identical records. The other human can include main and alternate coders; see the pair breakdown below.</p>'
            doc += table(['Coder / source','Matched n','Other human','κ','Gemma','κ','Qwen','κ'],[[g['display'],g['matched']['n']]+[f(x) for partner in ['other_label','gemma','qwen'] for x,f in [(g['matched'][partner]['agreement'],pct),(g['matched'][partner]['kappa'],kap)]] for g in groups])+'</details>'
        def display(key):
            return d['groups'][key]['display']
        doc += '<h3>Human–human pairs by recorded attribution</h3><p>Each row uses overlapping labeled records for those two individuals. Main coders are identified by their sheet initials.</p>'
        doc += table(['First source / person','Second source / person','n','Agreement','κ'],[[display(p['left']),display(p['right']),p['n'],pct(p['agreement']),kap(p['kappa'])] for p in d['human_pairs']])
        doc += '<details><summary>Model comparisons within each human pair</summary><p>Every row uses the same records for the human baseline and both model comparisons.</p>'
        rows=[]
        for key,g in d['groups'].items():
            for partner,m in g['counterparts'].items():
                rows.append([g['display'],display(partner),m['other_label']['n']]+[f(m[p][k]) for p in ['other_label','gemma','qwen'] for k,f in [('agreement',pct),('kappa',kap)]])
        doc += table(['Target coder','Other source / person','n','Human–human','κ','Gemma–target','κ','Qwen–target','κ'],rows)+'</details>'
        if lang == 'tagalog':
            doc += '<h3>Tagalog by corpus</h3>'+table(['Coder / source','Corpus','n','Gemma','κ','Qwen','κ'],[[g['display'],c,m['judgments'],pct(m['gemma']['agreement']),kap(m['gemma']['kappa']),pct(m['qwen']['agreement']),kap(m['qwen']['kappa'])] for g in d['groups'].values() for c,m in g['corpora'].items()])
    doc += '<h2>Reading these results</h2><p>These are descriptive agreement measures, not individual coder accuracy scores. People coded different records and some named subsets are tiny. Differences may reflect label mix, corpus or item difficulty. Tokens share transcripts and children; no independent-token significance claims are made. κ is undefined when marginal agreement is necessarily perfect.</p><p>The JSON includes row-level attribution, labels, comparison record IDs, source hashes and the analysis policy. Sources and frozen inference/scoring files remain unchanged. No dev check 2 or lockbox records were accessed.</p><p><a href="report.json">Machine-readable results and attribution audit</a></p></html>'
    return doc


if __name__ == '__main__':
    data = calculate_individuals()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT/'report.json').write_text(json.dumps(data, indent=2)+'\n')
    (OUTPUT/'report.html').write_text(render(data))
    for lang,d in data['languages'].items():
        print(lang, 'alternate',d['alternate_coder_judgments'],'main',d['main_coder_judgments'])
        for g in d['groups'].values():
            print(' ',g['display'],g['judgments'],pct(g['gemma']['agreement']),pct(g['qwen']['agreement']))
