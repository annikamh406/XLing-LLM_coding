#!/usr/bin/env python3
"""Freeze small, output-independent samples for the Gemma GPU comparison."""
import hashlib
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
STEM = 'dev_train_gemma_gpu_v5'
LANGUAGES = ('english', 'german', 'hebrew', 'spanish', 'tagalog')
SEED = 'gemma-gpu-comparison-2026-10-09'

def read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def frozen_write(path, text):
    if path.exists() and path.read_text() != text:
        raise RuntimeError(f'Refusing to change frozen sample: {path}')
    path.write_text(text)

def main():
    for language in LANGUAGES:
        directory = BASE / 'splits' / language
        source_stem = 'dev_train_prompttest_v5' if language == 'english' else 'dev_train_promptpair_v5'
        source = directory / (source_stem + '.jsonl')
        reference_path = directory / (source_stem + '_human_reference.jsonl')
        references = {r['record_id']: r for r in read(reference_path)}
        inspected_path = directory / 'inspected_rows.txt'
        inspected = {s.strip() for s in inspected_path.read_text().splitlines()
                     if s.strip() and not s.startswith('#')} if inspected_path.exists() else set()
        candidates = []
        for r in read(source):
            label = r.get('sampling_label') or r.get('bloom_1')
            # English's frozen diagnostic preserves the historical spelling.
            if label == 'Nonposession':
                label = 'Nonpossession'
            if r['record_id'] in inspected or r.get('bloom_1') != r.get('bloom_2'):
                continue
            if r.get('evaluation_subset', 'double_coded_consensus') != 'double_coded_consensus':
                continue
            candidates.append({**r, 'sampling_label': label, 'evaluation_subset': 'double_coded_consensus'})
        quotas = {'Rejection':12, 'Denial':12, 'Nonexistence':10, 'Excluded':4, 'Nonpossession':2}
        if language == 'spanish':
            quotas['Nonexistence'] = 12; quotas['Nonpossession'] = 0
        selected = []
        for label, n in quotas.items():
            pool = [r for r in candidates if r['sampling_label'] == label]
            pool.sort(key=lambda r: hashlib.sha256((SEED+language+r['record_id']).encode()).hexdigest())
            if len(pool) < n:
                raise RuntimeError(f'{language}: only {len(pool)} eligible {label} rows, need {n}')
            selected.extend(pool[:n])
        # Preserve source-relative record order, independent of label or output.
        chosen = {r['record_id']: r for r in selected}
        selected = [chosen[r['record_id']] for r in candidates if r['record_id'] in chosen]
        assert len(selected) == len(chosen) == 40
        text = ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in selected)
        ref_text = ''.join(json.dumps(references[r['record_id']],ensure_ascii=False)+'\n' for r in selected)
        manifest = {
            'language':language, 'n':40, 'source':str(source.relative_to(BASE)),
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'sample_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'reference_sha256':hashlib.sha256(ref_text.encode()).hexdigest(),
            'selection_seed':SEED, 'class_counts':dict(Counter(r['sampling_label'] for r in selected)),
            'record_ids':[r['record_id'] for r in selected],
            'purpose':'Hardware repeatability diagnostic; class-enriched development material, not population accuracy.',
        }
        frozen_write(directory/(STEM+'.jsonl'),text)
        frozen_write(directory/(STEM+'_human_reference.jsonl'),ref_text)
        frozen_write(directory/(STEM+'_manifest.json'),json.dumps(manifest,indent=2)+'\n')
        print(language,manifest['class_counts'])

if __name__ == '__main__':main()
