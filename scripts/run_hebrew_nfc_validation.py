#!/usr/bin/env python3
"""Amended Hebrew-only NFC validation, with separate provenance and output IDs."""
import hashlib
import json
from pathlib import Path
import unicodedata
import run_bloom_coding as runner
import run_v5_validation_recovery as recovery
from check_v5_validation_freeze import BASE
from check_v5_recovery_freeze import check as verify_recovery
from run_hebrew_nfc_dev import verify_dev

AMENDMENT = BASE/'v5/dev_check_1_hebrew_nfc_amendment.json'
TAG = 'p005v1nfc-he-full-b5-t0-s20261009'
ORIGINAL_PROMPT_RECORD = runner.prompt_record


def nfc_record(record):
    def normalize(value):
        if isinstance(value,str):return unicodedata.normalize('NFC',value)
        if isinstance(value,list):return [normalize(v) for v in value]
        if isinstance(value,dict):return {k:normalize(v) for k,v in value.items()}
        return value
    return normalize(ORIGINAL_PROMPT_RECORD(record))


def normalized_hash(records):
    return hashlib.sha256(json.dumps([nfc_record(r) for r in records],sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def verify_nfc():
    verify_recovery();verify_dev()
    amendment=json.loads(AMENDMENT.read_text())
    for name,expected in amendment['files_sha256'].items():
        if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('NFC validation amendment file changed: '+name)
    return amendment


def annotate(rows,by_id,amendment_hash,decorate=recovery.decorate):
    decorate(rows)
    for batch in rows:
        batch['input_normalization']='NFC'
        batch['normalized_input_sha256']=normalized_hash([by_id[i] for i in batch['record_ids']])
        batch['preprocessing_amendment_sha256']=amendment_hash
    return rows


def main():
    amendment=verify_nfc();args=runner.parse_args()
    if (args.split!='dev_check_1' or args.model!='qwen3.6:35b-a3b' or args.prompt_version!=TAG
        or args.split_dir.resolve()!=(BASE/'splits/hebrew').resolve()
        or args.prompt.resolve()!=(BASE/amendment['prompt']).resolve()
        or args.results_dir.resolve()!=(BASE/amendment['results_dir']).resolve()
        or args.schema_version!='bloom_v5' or args.num_ctx!=32768 or args.reasoning_effort is not None
        or any(v is not None for v in [args.top_p,args.top_k,args.min_p])):
        raise SystemExit('Use the frozen Hebrew NFC validation launcher without overrides')
    records=runner.read_jsonl(BASE/amendment['input'])
    if len(records)!=1199:raise ValueError('Expected the full 1,199-record Hebrew validation split')
    by_id={r['record_id']:r for r in records}
    amendment_hash=hashlib.sha256(AMENDMENT.read_bytes()).hexdigest()
    runner.prompt_record=nfc_record
    # Existing recovery remains bounded, deterministic and fully audited.
    recovery.decorate=lambda rows:annotate(rows,by_id,amendment_hash)
    return recovery.main()

if __name__=='__main__':raise SystemExit(main())
