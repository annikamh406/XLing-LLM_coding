#!/usr/bin/env python3
"""Evaluate NFC reliability on the frozen 250-record Hebrew development sample.

Every batch gets one temperature-zero attempt. Failures remain explicit and do
not prevent testing later batches. No validation/check/lockbox data are used.
"""
import hashlib
import json
import os
from pathlib import Path
import run_bloom_coding as runner
from check_v5_validation_freeze import BASE, verify
from diagnose_qwen_hebrew import request_payload, run_request
from validation_runtime_compat import parameter_values

FREEZE = BASE/'v5/hebrew_nfc_dev_freeze.json'

def verify_dev():
    verify()
    frozen=json.loads(FREEZE.read_text())
    for name,expected in frozen['files_sha256'].items():
        if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('NFC development freeze changed: '+name)
    return frozen

def evaluate(records,prompt,runtime,args,frozen):
    output=args.results_dir
    output.mkdir(parents=True,exist_ok=True)
    lock=(output/'nfc-dev.lock').open('a')
    try:runner.fcntl.flock(lock,runner.fcntl.LOCK_EX|runner.fcntl.LOCK_NB)
    except BlockingIOError:raise RuntimeError('Another NFC development job is writing this output')
    # Keep the lock alive for the full run.
    try:
        expected_ids=[r['record_id'] for r in records]
        if len(records)!=frozen['records'] or len(set(expected_ids))!=len(records):
            raise ValueError('Unexpected sample size or duplicate input IDs')
        signature={k:runtime[k] for k in ['model_digest','ollama_version','template_sha256']}
        signature['parameters']=parameter_values(runtime['model_parameters'])
        signature['gpu_model']=sorted(g['name'] for g in runtime['gpus'])
        if signature['ollama_version']!='0.32.14' or signature['gpu_model']!=['NVIDIA L40S']:
            raise ValueError('Expected frozen Ollama version and one L40S')
        manifest={'freeze':frozen,'runtime_signature':signature,'input_variant':'nfc',
                  'temperature':0,'batch_size':5,'base_seed':20261009,'retry_policy':'none; exactly one attempt per batch'}
        path=output/'manifest.json'
        if path.exists():
            if not args.resume or json.loads(path.read_text())!=manifest:
                raise ValueError('Existing NFC run differs from this manifest; refusing to overwrite')
        else:runner.atomic_write(path,json.dumps(manifest,indent=2)+'\n')
        all_predictions=[];raw=[];summary=[]
        for index in range(0,len(records),5):
            number=index//5+1;batch=records[index:index+5];ids=[r['record_id'] for r in batch]
            directory=output/f'batch-{number:03d}'
            payload=request_payload(batch,prompt,0.0,False,'nfc')
            payload['options']['seed']=20261009+number-1
            request_hash=hashlib.sha256(json.dumps(payload).encode()).hexdigest()
            if (directory/'result.json').exists():
                result=json.loads((directory/'result.json').read_text())
                if not args.resume or result['request_sha256']!=request_hash:
                    raise ValueError('Saved batch request differs; refusing reuse')
                print(f'Batch {number}: reusing recorded outcome {result["outcome"]}',flush=True)
            else:
                # A directory without a result means interruption during a request.
                # Keep its bytes and mark it interrupted rather than silently rerun.
                if directory.exists():
                    result={'outcome':'interrupted_request','request_sha256':request_hash}
                    runner.atomic_write(directory/'result.json',json.dumps(result,indent=2)+'\n')
                else:
                    print(f'Batch {number}: one NFC temperature-zero request ({len(ids)} records)',flush=True)
                    result=run_request(args.ollama_url,payload,directory,args.timeout)
            result=dict(result,batch_number=number,record_ids=ids)
            if result['outcome']=='valid_complete_response':
                events=runner.read_jsonl(directory/'events.jsonl')
                content=''.join(e.get('message',{}).get('content','') for e in events)
                predictions=runner.validate_response(runner.extract_json_object(content),ids,'bloom_v5')
                if sum(e.get('done') is True for e in events)!=1:
                    raise ValueError('Saved successful response lacks one completion event')
                all_predictions.extend(predictions)
                raw.append({'batch_number':number,'record_ids':ids,'model':args.model,
                    'schema_version':'bloom_v5','prompt_version':args.prompt_version,'prompt_path':str(args.prompt),
                    'input_normalization':'NFC (allowlisted record strings only)',
                    'effective_decoding_options':payload['options'],'attempt_count':1,
                    'runtime_provenance':runtime,'raw_response':events[-1]})
            summary.append(result)
            status={'expected_records':len(records),'expected_batches':(len(records)+4)//5,
                    'tested_batches':len(summary),'successful_batches':len(raw),
                    'successful_records':len(all_predictions),'failures':[r for r in summary if r['outcome']!='valid_complete_response'],
                    'complete':len(summary)==(len(records)+4)//5 and len(all_predictions)==len(records),
                    'batches':summary}
            runner.atomic_write(output/'status.json',json.dumps(status,indent=2)+'\n')
        if status['complete']:
            runner.validate_response({'schema_version':'bloom_v5','predictions':all_predictions},expected_ids,'bloom_v5')
            stem=f'{args.split}_{runner.clean_model_name(args.model)}_bloom_v5_{args.prompt_version}'
            runner.write_jsonl(output/(stem+'_predictions.jsonl'),all_predictions)
            runner.write_jsonl(output/(stem+'_raw_responses.jsonl'),raw)
        print(json.dumps({k:v for k,v in status.items() if k not in ['batches','failures']},indent=2))
        return 0 if status['complete'] else 1
    finally:lock.close()

def main():
    frozen=verify_dev();args=runner.parse_args()
    if (args.model!='qwen3.6:35b-a3b' or args.split!='dev_train_promptpair_v5' or args.batch_size!=5
        or args.limit is not None or args.temperature!=0 or args.seed!=20261009 or args.max_retries!=0
        or args.num_ctx!=32768 or args.num_predict!=8000 or args.timeout!=1200
        or args.schema_version!='bloom_v5' or args.prompt_version!='p005nfc-he-full-b5-t0-s20261009'
        or args.prompt.resolve()!=(BASE/frozen['prompt']).resolve()
        or args.split_dir.resolve()!=(BASE/'splits/hebrew').resolve()
        or args.results_dir.resolve()!=(BASE/frozen['results_dir']).resolve()
        or args.reasoning_effort is not None or any(v is not None for v in [args.top_p,args.top_k,args.min_p])):
        raise SystemExit('Use the frozen NFC development launcher without inference overrides')
    records=runner.read_jsonl(BASE/frozen['input'])
    runtime=json.loads(Path(os.environ['CODING_RUNTIME_PATH']).read_text())
    return evaluate(records,args.prompt.read_text(),runtime,args,frozen)

if __name__=='__main__':raise SystemExit(main())
