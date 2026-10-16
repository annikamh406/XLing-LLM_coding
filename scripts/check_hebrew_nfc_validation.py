#!/usr/bin/env python3
"""Validate the ten frozen validation outputs before rendering IRR reports."""
import json
import hashlib
import math
from pathlib import Path
import run_bloom_coding as runner
from check_v5_validation_freeze import BASE
from check_v5_recovery_freeze import check as verify_amendment
from run_v5_validation_recovery import POLICY
from run_hebrew_nfc_validation import verify_nfc, normalized_hash, AMENDMENT, TAG
from check_v5_recovered_results import check as check_original

def check(base=BASE, manifest=None, amendment_hash=None):
    if manifest is None:
        amendment=verify_nfc()
        original=verify_amendment()[0]
        manifest={**original,'results_dir':amendment['results_dir'],
                  'languages':{'hebrew':original['languages']['hebrew']},
                  'models':{'qwen3.6:35b-a3b':original['models']['qwen3.6:35b-a3b']}}
    if amendment_hash is None:
        amendment_hash=hashlib.sha256(AMENDMENT.read_bytes()).hexdigest()
    results = base / manifest['results_dir']
    issues, rows, signatures = [], [], {}
    for language, config in manifest['languages'].items():
        sample = runner.read_jsonl(base / config['input'])
        ids = [r['record_id'] for r in sample]
        for model, model_config in manifest['models'].items():
            batch_size = model_config['batch_size']
            tag = TAG
            stem = f"dev_check_1_{model.replace(':','_').replace('/','_')}_bloom_v5_{tag}"
            try:
                predictions = runner.read_jsonl(results / (stem + '_predictions.jsonl'))
                runner.validate_response({'schema_version':'bloom_v5','predictions':predictions}, ids, 'bloom_v5')
                raw = runner.read_jsonl(results / (stem + '_raw_responses.jsonl'))
                if len(raw) != math.ceil(len(ids)/batch_size):
                    raise ValueError('Wrong batch count')
                checkpoint = json.loads((results / (stem + '_checkpoint.json')).read_text())
                provenance = checkpoint['provenance']
                if provenance['prompt_sha256'] != manifest['files_sha256'][config['prompt']]:
                    raise ValueError('Prompt differs from freeze')
                if provenance['runner_sha256'] != manifest['files_sha256']['scripts/run_bloom_coding.py']:
                    raise ValueError('Runner differs from freeze')
                if provenance['records_sha256'] != hashlib.sha256(json.dumps(sample,sort_keys=True,ensure_ascii=False).encode()).hexdigest():
                    raise ValueError('Inputs differ from freeze')
                if provenance['batch_size'] != batch_size or provenance['max_retries'] != 0:
                    raise ValueError('Batch/retry settings differ from freeze')
                recovered_batches = 0
                recovered_ids = []
                for index, batch in enumerate(raw):
                    if batch['record_ids'] != ids[index*batch_size:(index+1)*batch_size]:
                        raise ValueError('Batch IDs/order differ from full split')
                    if batch.get('input_normalization')!='NFC' or batch.get('preprocessing_amendment_sha256')!=amendment_hash:
                        raise ValueError('NFC preprocessing amendment metadata missing or changed')
                    if batch.get('normalized_input_sha256')!=normalized_hash(sample[index*batch_size:(index+1)*batch_size]):
                        raise ValueError('Normalized input hash differs from source and NFC rule')
                    expected = dict(manifest['decoding_options'],seed=manifest['decoding_options']['seed']+index)
                    recovery = batch['raw_response'].get('validation_recovery')
                    if recovery:
                        if model != 'qwen3.6:35b-a3b' or recovery['policy'] != POLICY:
                            raise ValueError('Unexpected recovery policy')
                        attempts = recovery['attempts']
                        if not 1 <= len(attempts) <= 3 or attempts[-1]['status'] != 'success':
                            raise ValueError('Invalid recovery attempt count or result')
                        if [a['stage'] for a in attempts] != list(range(len(attempts))):
                            raise ValueError('Recovery stages out of order')
                        for stage,a in enumerate(attempts):
                            options = dict(expected)
                            inference_repair = stage == 2 and attempts[stage-1].get('error_kind') != 'format'
                            if inference_repair:
                                options['num_predict'] = 16000
                            if a['effective_decoding_options'] != options:
                                raise ValueError('Recovery changed unapproved decoding settings')
                            if a['timeout'] != (2400 if inference_repair else 1200):
                                raise ValueError('Unapproved recovery timeout')
                            if stage < len(attempts)-1 and a['status'] not in ('failed','started'):
                                raise ValueError('Recovery has an invalid preceding outcome')
                        if batch['effective_decoding_options'] != attempts[-1]['effective_decoding_options'] or batch['attempt_count'] != len(attempts):
                            raise ValueError('Recovery metadata mismatch')
                        audit_path = results/'recovery'/stem/f'batch-{index+1}.json'
                        audit = json.loads(audit_path.read_text())
                        if audit['fingerprint'] != recovery['fingerprint'] or audit['attempts'][-1]['status'] != 'success':
                            raise ValueError('Missing or inconsistent recovery audit')
                        recovered_batches += len(attempts)>1
                        if len(attempts)>1:
                            recovered_ids.extend(batch['record_ids'])
                    elif batch['effective_decoding_options'] != expected or batch['attempt_count'] != 1:
                        raise ValueError('Decoding/retry settings differ from freeze')
                    if batch['model'] != model or batch['prompt_version'] != tag:
                        raise ValueError('Model or prompt tag mismatch')
                    runtime = batch['runtime_provenance']
                    if not runtime['gpus'] or any('L40S' not in g['name'] for g in runtime['gpus']):
                        raise ValueError('Expected L40S hardware')
                    if runtime['ollama_version'] != manifest['ollama_version']:
                        raise ValueError('Ollama version differs from freeze')
                    if model_config['weights_blob_sha256'] not in runtime['model_modelfile']:
                        raise ValueError('Model weights differ from freeze')
                    # Compare parameter text independent of line ordering.
                    signature = (runtime['model_digest'],runtime['template_sha256'],
                                 tuple(sorted(runtime['model_parameters'].splitlines())))
                    signatures.setdefault(model,set()).add(signature)
                rows.append({'language':language,'model':model,'records':len(predictions),'batches':len(raw),'recovered_batches':recovered_batches,'recovered_record_ids':recovered_ids,'input_normalization':'NFC','source_directory':str(results)})
            except (ValueError, KeyError, OSError, TypeError) as error:
                issues.append(f'{language} / {model}: {error}')
    for model, values in signatures.items():
        if len(values) != 1:
            issues.append(f'{model}: model/template/default parameters differ across runs')
    return {'expected_runs':len(manifest['languages'])*len(manifest['models']),
            'validated_runs':len(rows),'runs':rows,'issues':issues}

def combined():
    nfc=check()
    original=check_original()
    # Select the NFC Hebrew/Qwen configuration explicitly; its old failed
    # configuration remains archived and is not included as an eleventh run.
    keep=lambda r:not (r['language']=='hebrew' and r['model']=='qwen3.6:35b-a3b')
    rows=[r for r in original['runs'] if keep(r)]+nfc['runs']
    issues=[issue for issue in original['issues'] if not issue.startswith('hebrew / qwen3.6:35b-a3b:')]+nfc['issues']
    return {'expected_runs':10,'validated_runs':len(rows),'runs':rows,'issues':issues,
            'configuration_note':'Hebrew Qwen uses the documented NFC amendment; other language/model configurations retain their original preprocessing.'}

if __name__ == '__main__':
    status=combined()
    output=BASE/'v5/results/dev_check_1_hebrew_nfc/combined_status.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(status,indent=2)+'\n')
    print(json.dumps(status,indent=2))
    raise SystemExit(1 if status['issues'] else 0)
