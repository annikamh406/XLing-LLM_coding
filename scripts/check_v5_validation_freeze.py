#!/usr/bin/env python3
"""Check the committed validation manifest without inspecting reference labels."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
MANIFEST = BASE / 'v5/dev_check_1_freeze.json'

def verify(base=BASE, manifest_path=MANIFEST):
    manifest = json.loads(manifest_path.read_text())
    if manifest['split'] != 'dev_check_1':
        raise ValueError('Validation manifest must use dev_check_1')
    for relative, expected in manifest['files_sha256'].items():
        path = base / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen file changed: {relative}')
    return manifest

if __name__ == '__main__':
    try:
        frozen = verify()
        print(f"Freeze verified: {len(frozen['languages'])} languages, "
              f"{sum(r['records'] for r in frozen['languages'].values())} records per model.")
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(str(error))
