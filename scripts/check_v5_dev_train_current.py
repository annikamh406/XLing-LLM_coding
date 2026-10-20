#!/usr/bin/env python3
"""Verify the full dev_train baseline against its independent freeze."""
import hashlib
import json
from pathlib import Path
from run_hebrew_nfc_validation import verify_nfc

BASE = Path(__file__).resolve().parents[1]
MANIFEST = BASE/'v5/dev_train_current_freeze.json'


def verify(base=BASE, manifest_path=MANIFEST):
    verify_nfc()  # Preserve and verify all existing validation/recovery/NFC freezes.
    frozen = json.loads(manifest_path.read_text())
    if frozen['split'] != 'dev_train':
        raise ValueError('Full training baseline must use dev_train')
    for name, expected in frozen['files_sha256'].items():
        if hashlib.sha256((base/name).read_bytes()).hexdigest() != expected:
            raise ValueError('Full training baseline file changed: '+name)
    for lang, condition in frozen['languages'].items():
        records = [json.loads(line) for line in (base/condition['input']).read_text().splitlines()]
        ids = [r['record_id'] for r in records]
        if len(ids) != condition['records'] or len(set(ids)) != len(ids):
            raise ValueError('Unexpected full training size or duplicate IDs: '+lang)
    return frozen


def tag(language, model, frozen):
    condition = frozen['languages'][language]
    batch = frozen['models'][model]['batch_size']
    nfc = 'nfc' if language=='hebrew' and model=='qwen3.6:35b-a3b' else ''
    return f'p005dt1{nfc}-{condition["code"]}-full-b{batch}-t0-s20261009'


if __name__ == '__main__':
    frozen = verify()
    print('Full dev_train baseline verified: '+str(sum(c['records'] for c in frozen['languages'].values()))+' records per model; ten conditions.')
