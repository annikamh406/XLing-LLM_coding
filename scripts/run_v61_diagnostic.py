#!/usr/bin/env python3
"""Run only frozen v6.1 diagnostic records, with each original baseline seed."""
import argparse
import fcntl
import json
import os
from pathlib import Path

import run_bloom_coding as runner
import v61_diagnostic as config


def run(language, url, runtime_path, base=config.BASE, manifest=config.MANIFEST):
    frozen=config.verify(base,manifest);condition=frozen['languages'][language]
    runtime=json.loads(Path(runtime_path).read_text());config.check_runtime(runtime,frozen,condition)
    files=config.paths(frozen,language,base);files['lock'].parent.mkdir(parents=True,exist_ok=True)
    with files['lock'].open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        expected=config.provenance(frozen,condition,manifest)
        state={'provenance':expected,'predictions':[],'raw_responses':[]}
        if files['checkpoint'].exists():state=json.loads(files['checkpoint'].read_text())
        completed=config.check_saved(state,frozen,condition,expected)
        for key,saved in [('predictions',state['predictions']),('raw',state['raw_responses'])]:
            if files[key].exists() and runner.read_jsonl(files[key])!=saved:
                raise ValueError('Final file differs from checkpoint: '+key)
        if files['failure'].exists():raise ValueError('A genuine failure is recorded; review it before a separately amended rerun')
        records=runner.read_jsonl(base/condition['input']);prompt=(base/condition['prompt']).read_text()
        for index in range(completed,len(records)):
            r=records[index];s=condition['selection'][index];rid=r['record_id'];options=s['original_effective_options']
            print(f'{language}: {index+1}/{len(records)} {rid}, original batch {s["original_batch_number"]}, seed {options["seed"]}',flush=True)
            payload=None;raw=None
            try:
                payload,raw=runner.ollama_chat(url=url,model=frozen['model'],prompt=prompt,
                    records=[runner.prompt_record(r)],output_schema=runner.build_output_schema([rid],frozen['schema_version']),
                    **options,timeout=frozen['timeout'],validation_feedback=None)
                prediction=runner.validate_response(payload,[rid],frozen['schema_version'])[0]
            except Exception as exc:
                runner.atomic_write(files['failure'],json.dumps({'record_id':rid,'intervention':'6.1',
                    'provenance':expected,'original_batch_number':s['original_batch_number'],
                    'effective_decoding_options':options,'error':str(exc),'parsed_payload':payload,
                    'raw_response':raw,'runtime_provenance':runtime},ensure_ascii=False,indent=2)+'\n')
                raise
            state['predictions'].append(prediction)
            state['raw_responses'].append({'record_ids':[rid],'original_batch_number':s['original_batch_number'],
                'diagnostic_position':index+1,'effective_decoding_options':options,'attempt_count':1,
                'intervention':'6.1','prompt_version':condition['prompt_version'],
                'runtime_provenance':runtime,'raw_response':raw})
            runner.atomic_write(files['checkpoint'],json.dumps(state,ensure_ascii=False)+'\n')
        runner.write_jsonl(files['predictions'],state['predictions'])
        runner.write_jsonl(files['raw'],state['raw_responses'])
        print(f'{language}: complete, {len(records)} validated predictions; no model retries.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--language',required=True,choices=['english','german','hebrew','spanish','tagalog'])
    p.add_argument('--ollama-url',default=runner.DEFAULT_OLLAMA_URL)
    p.add_argument('--runtime',type=Path,default=os.environ.get('CODING_RUNTIME_PATH'))
    args=p.parse_args()
    if args.runtime is None:p.error('Runtime capture required; use the Slurm launcher')
    run(args.language,args.ollama_url,args.runtime)


if __name__=='__main__':main()
