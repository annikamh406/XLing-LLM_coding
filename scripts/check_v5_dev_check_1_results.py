#!/usr/bin/env python3
"""Validate the ten frozen validation outputs before rendering IRR reports."""
import json
import hashlib
import math
from pathlib import Path
import run_bloom_coding as runner
from check_v5_validation_freeze import BASE, verify

def check(base=BASE, manifest=None):
    manifest = manifest if manifest is not None else verify()
    results = base / manifest['results_dir']
    issues, rows, signatures = [], [], {}
    for language, config in manifest['languages'].items():
        sample = runner.read_jsonl(base / config['input'])
        ids = [r['record_id'] for r in sample]
        for model, model_config in manifest['models'].items():
            batch_size = model_config['batch_size']
            tag = f"p005v1-{config['code']}-full-b{batch_size}-t0-s20261009"
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
                for index, batch in enumerate(raw):
                    if batch['record_ids'] != ids[index*batch_size:(index+1)*batch_size]:
                        raise ValueError('Batch IDs/order differ from full split')
                    expected = dict(manifest['decoding_options'],seed=manifest['decoding_options']['seed']+index)
                    if batch['effective_decoding_options'] != expected or batch['attempt_count'] != 1:
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
                rows.append({'language':language,'model':model,'records':len(predictions),'batches':len(raw)})
            except (ValueError, KeyError, OSError, TypeError) as error:
                issues.append(f'{language} / {model}: {error}')
    for model, values in signatures.items():
        if len(values) != 1:
            issues.append(f'{model}: model/template/default parameters differ across runs')
    return {'expected_runs':len(manifest['languages'])*len(manifest['models']),
            'validated_runs':len(rows),'runs':rows,'issues':issues}

if __name__ == '__main__':
    status = check()
    output = BASE / 'v5/results/dev_check_1/status.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(status,indent=2)+'\n')
    print(json.dumps(status,indent=2))
    raise SystemExit(1 if status['issues'] else 0)
