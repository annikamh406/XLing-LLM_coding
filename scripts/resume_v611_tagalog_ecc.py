#!/usr/bin/env python3
"""One audited hardware-failure continuation; never retry model failures."""
import argparse
import fcntl
import json
import os
from pathlib import Path

import run_bloom_coding as runner
import v611_diagnostic as config

AMENDMENT=config.BASE/'v6/dev_train_diagnostic_6_1_1_ecc_recovery.json'


def canonical(value):return config.digest_text(json.dumps(value,sort_keys=True,ensure_ascii=False))


def prefix_hash(state,n):
    return canonical({key:state[key][:n] for key in ('predictions','raw_responses')})


def verify(base=config.BASE,manifest=config.MANIFEST,amendment=AMENDMENT):
    frozen=config.verify(base,manifest);a=json.loads(amendment.read_text())
    if config.digest(manifest)!=a['freeze_sha256'] or a['language']!='tagalog':
        raise ValueError('ECC amendment does not match the frozen Tagalog run')
    for name,expected in a['files_sha256'].items():
        if config.digest(base/name)!=expected:raise ValueError('ECC recovery implementation changed: '+name)
    for name,expected in a['evidence_sha256'].items():
        if config.digest(base/name)!=expected:raise ValueError('ECC evidence changed: '+name)
    if 'uncorrectable ECC error encountered' not in (base/a['server_log']).read_text():
        raise ValueError('Missing specific uncorrectable ECC evidence')
    if a['excluded_node'] not in (base/a['job_log']).read_text():
        raise ValueError('Evidence does not name the excluded node')
    files=config.paths(frozen,'tagalog',base)
    state=json.loads(files['checkpoint'].read_text())
    saved=config.check_saved(state,frozen,frozen['languages']['tagalog'],config.provenance(frozen,frozen['languages']['tagalog'],manifest))
    if saved<a['initial_saved_records'] or prefix_hash(state,a['initial_saved_records'])!=a['initial_prefix_sha256']:
        raise ValueError('The original validated checkpoint prefix changed')
    archive=base/a['archive_failure']
    # Original active evidence can move once into the retained recovery archive.
    evidence=archive if archive.exists() else files['failure']
    if config.digest(evidence)!=a['original_failure_sha256']:
        raise ValueError('This is not the allowlisted historical hardware failure')
    failure=json.loads(evidence.read_text());condition=frozen['languages']['tagalog']
    target=condition['selection'][a['initial_saved_records']]
    if failure['record_id']!=a['failed_record_id'] or target['record_id']!=a['failed_record_id'] or failure['effective_decoding_options']!=target['original_effective_options']:
        raise ValueError('Failed request differs from the authorized hardware-failure request')
    if failure['parsed_payload'] is not None or failure['raw_response'] is not None:
        raise ValueError('Historical failure contains a model response; cannot classify as hardware-only')
    if files['failure'].exists() and config.digest(files['failure'])!=a['original_failure_sha256']:
        raise ValueError('A new failure requires review; this amendment cannot clear it')
    return frozen,a,state,saved


def run(url,runtime_path,base=config.BASE,manifest=config.MANIFEST,amendment=AMENDMENT):
    frozen,a,state,saved=verify(base,manifest,amendment)
    c=frozen['languages']['tagalog'];files=config.paths(frozen,'tagalog',base)
    runtime=json.loads(Path(runtime_path).read_text());config.check_runtime(runtime,frozen,c)
    if runtime['gpus'][0].get('uuid')==a['excluded_gpu_uuid'] or os.environ.get('SLURMD_NODENAME')==a['excluded_node'] or os.environ.get('SLURM_JOB_NODELIST')==a['excluded_node']:
        raise ValueError('Recovery may not run on the faulty GPU/node')
    directory=base/a['recovery_dir'];directory.mkdir(parents=True,exist_ok=True)
    with files['lock'].open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        frozen,a,state,saved=verify(base,manifest,amendment)
        ledger_path=directory/'ledger.json';amendment_hash=config.digest(amendment)
        ledger={'amendment_sha256':amendment_hash,'historical_failure_classification':'uncorrectable_GPU_ECC_no_model_response',
                'original_failure_sha256':a['original_failure_sha256'],'initial_saved_records':a['initial_saved_records'],'attempts':[]}
        if ledger_path.exists():ledger=json.loads(ledger_path.read_text())
        if ledger['amendment_sha256']!=amendment_hash:raise ValueError('Recovery ledger amendment changed')
        def save():runner.atomic_write(ledger_path,json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
        # Reconcile a checkpoint published immediately before interruption.
        for attempt in ledger['attempts']:
            position=attempt['diagnostic_position']
            if position<=saved and state['predictions'][position-1]['record_id']==attempt['record_id']:
                if attempt['status']=='failed':raise ValueError('Failure conflicts with checkpoint')
                attempt['status']='success'
            elif attempt['status']!='success':
                raise ValueError('A new failed or unresolved request requires review; no automatic replay')
            else:raise ValueError('Recovery ledger success is absent from checkpoint')
        if len(ledger['attempts'])!=saved-a['initial_saved_records']:
            raise ValueError('Saved recovery records do not match the attempt ledger')
        for key,snapshot in [('predictions',state['predictions']),('raw',state['raw_responses'])]:
            if files[key].exists() and runner.read_jsonl(files[key])!=snapshot:raise ValueError('Final output differs from checkpoint')
        save()
        archive=base/a['archive_failure'];archive.parent.mkdir(parents=True,exist_ok=True)
        if files['failure'].exists():
            if archive.exists():raise ValueError('Duplicate active and archived failure; review required')
            os.replace(files['failure'],archive)
        records=runner.read_jsonl(base/c['input']);prompt=(base/c['prompt']).read_text()
        for index in range(saved,len(records)):
            r=records[index];s=c['selection'][index];rid=r['record_id'];options=s['original_effective_options']
            attempt={'record_id':rid,'diagnostic_position':index+1,'status':'started','seed':options['seed'],
                     'slurm_job_id':os.environ.get('SLURM_JOB_ID')}
            ledger['attempts'].append(attempt);save()
            print(f'Tagalog ECC continuation: {index+1}/{len(records)}, {rid}, original seed {options["seed"]}',flush=True)
            payload=raw=None
            try:
                payload,raw=runner.ollama_chat(url=url,model=frozen['model'],prompt=prompt,
                    records=[runner.prompt_record(r)],output_schema=runner.build_output_schema([rid],frozen['schema_version']),
                    **options,timeout=frozen['timeout'],validation_feedback=None)
                prediction=runner.validate_response(payload,[rid],frozen['schema_version'])[0]
            except Exception as exc:
                attempt.update(status='failed',error=str(exc));save()
                runner.atomic_write(files['failure'],json.dumps({'record_id':rid,'intervention':'6.1.1',
                    'provenance':state['provenance'],'original_batch_number':s['original_batch_number'],
                    'effective_decoding_options':options,'error':str(exc),'parsed_payload':payload,
                    'raw_response':raw,'runtime_provenance':runtime,'ecc_amendment_sha256':amendment_hash},ensure_ascii=False,indent=2)+'\n')
                raise
            state['predictions'].append(prediction)
            state['raw_responses'].append({'record_ids':[rid],'original_batch_number':s['original_batch_number'],
                'diagnostic_position':index+1,'effective_decoding_options':options,'attempt_count':1,
                'intervention':'6.1.1','prompt_version':c['prompt_version'],'runtime_provenance':runtime,
                'raw_response':raw,'ecc_amendment_sha256':amendment_hash})
            runner.atomic_write(files['checkpoint'],json.dumps(state,ensure_ascii=False)+'\n')
            attempt['status']='success';save()
        runner.write_jsonl(files['predictions'],state['predictions']);runner.write_jsonl(files['raw'],state['raw_responses'])
        ledger['complete']=True;save()
        print('Tagalog complete: all 33 records. Original ten predictions and ECC evidence retained.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify',action='store_true')
    p.add_argument('--ollama-url',default=runner.DEFAULT_OLLAMA_URL);p.add_argument('--runtime',type=Path)
    args=p.parse_args()
    if args.verify:
        _,_,_,saved=verify();print(f'Tagalog ECC continuation verified: {saved}/33 records saved; gpu3001 excluded.');return
    if args.runtime is None:p.error('--runtime is required for inference')
    run(args.ollama_url,args.runtime)


if __name__=='__main__':main()
