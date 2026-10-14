#!/usr/bin/env python3
"""Verify the original freeze plus the separately recorded recovery amendment."""
import hashlib
import json
from pathlib import Path
from check_v5_validation_freeze import BASE, verify

def check():
    original = verify()
    amendment = json.loads((BASE/'v5/dev_check_1_recovery_amendment.json').read_text())
    if hashlib.sha256((BASE/'v5/dev_check_1_freeze.json').read_bytes()).hexdigest()!=amendment['original_freeze_sha256']:
        raise ValueError('Original validation manifest changed after recovery amendment')
    for name,expected in amendment['files_sha256'].items():
        if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Recovery file changed: '+name)
    return original,amendment

if __name__=='__main__':
    check()
    print('Original validation freeze and recovery amendment verified.')
