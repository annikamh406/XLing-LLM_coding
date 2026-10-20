#!/usr/bin/env python3
"""Full dev_train at the validated settings, in a separate output namespace."""
import hashlib
import json
import os
import run_bloom_coding as runner
from check_v5_dev_train_current import BASE, MANIFEST, tag, verify
from run_v5_validation_recovery import Recovery, decorate as decorate_recovery
from run_hebrew_nfc_validation import nfc_record, normalized_hash
from validation_runtime_compat import compatible_runtime


def validate_args(args, frozen):
    languages = [lang for lang in frozen['languages'] if args.split_dir.resolve()==(BASE/'splits'/lang).resolve()]
    if len(languages)!=1 or args.model not in frozen['models']:
        raise ValueError('Use a configured dev_train language and finalist model')
    language=languages[0];condition=frozen['languages'][language]
    expected = frozen['decoding_options']
    if (args.split!='dev_train' or args.schema_version!='bloom_v5'
        or args.prompt_version!=tag(language,args.model,frozen)
        or args.prompt.resolve()!=(BASE/condition['prompt']).resolve()
        or args.results_dir.resolve()!=(BASE/frozen['results_dir']).resolve()
        or args.batch_size!=frozen['models'][args.model]['batch_size']
        or args.limit is not None or not args.resume or args.overwrite
        or args.max_retries!=0 or args.timeout!=1200 or args.reasoning_effort is not None
        or any(getattr(args,k)!=v for k,v in expected.items())):
        raise ValueError('Use the frozen full dev_train launcher without inference overrides')
    return language


def main():
    frozen=verify();args=runner.parse_args();language=validate_args(args,frozen)
    records=runner.read_jsonl(BASE/frozen['languages'][language]['input'])
    by_id={r['record_id']:r for r in records}
    use_nfc=language=='hebrew' and args.model=='qwen3.6:35b-a3b'
    runtime_path=os.environ.get('CODING_RUNTIME_PATH')
    if not runtime_path:
        raise ValueError('Runtime capture required; submit through the full dev_train launcher')
    runtime=json.loads(open(runtime_path).read())
    if (runtime.get('ollama_version')!=frozen['ollama_version']
        or [g['name'] for g in runtime.get('gpus',[])]!=['NVIDIA L40S']
        or frozen['models'][args.model]['weights_blob_sha256'] not in runtime.get('model_modelfile','')):
        raise ValueError('Expected frozen Ollama, model weights and one L40S')
    freeze_hash=hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    original={k:getattr(runner,k) for k in ['prompt_record','ollama_chat','atomic_write','write_jsonl']}
    def decorate(rows):
        if args.model=='qwen3.6:35b-a3b':decorate_recovery(rows)
        for batch in rows:
            batch['dev_train_freeze_sha256']=freeze_hash
            batch['input_normalization']='NFC' if use_nfc else 'none'
            if use_nfc:
                batch['normalized_input_sha256']=normalized_hash([by_id[i] for i in batch['record_ids']])
        return rows
    def atomic_checkpoint(path,text):
        if str(path).endswith('_checkpoint.json'):
            state=json.loads(text);decorate(state['raw_responses'])
            text=json.dumps(state,ensure_ascii=False)+'\n'
        original['atomic_write'](path,text)
    def write_output(path,rows):
        if str(path).endswith('_raw_responses.jsonl'):decorate(rows)
        original['write_jsonl'](path,rows)
    try:
        os.environ['CODING_RUNTIME_PATH']=str(compatible_runtime(args,runtime_path))
        if use_nfc:runner.prompt_record=nfc_record
        if args.model=='qwen3.6:35b-a3b':runner.ollama_chat=Recovery(args,original['ollama_chat'])
        runner.atomic_write=atomic_checkpoint;runner.write_jsonl=write_output
        return runner.main()
    finally:
        for key,value in original.items():setattr(runner,key,value)
        os.environ['CODING_RUNTIME_PATH']=runtime_path


if __name__=='__main__':raise SystemExit(main())
