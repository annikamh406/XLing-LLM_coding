#!/usr/bin/env python3
"""Give condo exclusive priority over opportunistic scavenger work per condition."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from check_v5_dev_train_current import BASE, MANIFEST, tag, verify as verify_training
import run_bloom_coding as runner

AMENDMENT=BASE/'v5/dev_train_coordination.json'


def verify():
    frozen=verify_training()
    amendment=json.loads(AMENDMENT.read_text())
    if hashlib.sha256(MANIFEST.read_bytes()).hexdigest()!=amendment['training_freeze_sha256']:
        raise ValueError('Original full-training freeze changed')
    for name,expected in amendment['files_sha256'].items():
        if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Coordination file changed: '+name)
    return frozen


def stem(language,model,frozen):
    return f'dev_train_{runner.clean_model_name(model)}_bloom_v5_{tag(language,model,frozen)}'


def complete(language,model,frozen):
    """No early skip based merely on the existence of a prediction filename."""
    output=BASE/frozen['results_dir'];prefix=stem(language,model,frozen)
    pred=output/(prefix+'_predictions.jsonl');raw=output/(prefix+'_raw_responses.jsonl')
    checkpoint=output/(prefix+'_checkpoint.json')
    if not (pred.exists() and raw.exists() and checkpoint.exists()):return False
    records=runner.read_jsonl(BASE/frozen['languages'][language]['input'])
    ids=[r['record_id'] for r in records];predictions=runner.read_jsonl(pred);batches=runner.read_jsonl(raw)
    runner.validate_response({'schema_version':'bloom_v5','predictions':predictions},ids,'bloom_v5')
    batch_size=frozen['models'][model]['batch_size']
    expected=[ids[i:i+batch_size] for i in range(0,len(ids),batch_size)]
    if [b['record_ids'] for b in batches]!=expected:raise ValueError('Final raw batches differ from the frozen training input')
    state=json.loads(checkpoint.read_text())
    if state['predictions']!=predictions or state['raw_responses']!=batches:
        raise ValueError('Final outputs differ from their checkpoint')
    expected_provenance={'model':model,'schema_version':'bloom_v5','prompt_version':tag(language,model,frozen),
        'reasoning_effort':None,'batch_size':batch_size,'max_retries':0,'decoding_options':frozen['decoding_options'],
        'records_sha256':hashlib.sha256(json.dumps(records,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        'prompt_sha256':hashlib.sha256((BASE/frozen['languages'][language]['prompt']).read_bytes()).hexdigest(),
        'runner_sha256':hashlib.sha256((BASE/'scripts/run_bloom_coding.py').read_bytes()).hexdigest(),
        'gpu_model':['NVIDIA L40S']}
    if any(state['provenance'].get(k)!=v for k,v in expected_provenance.items()):
        raise ValueError('Final output provenance differs from the frozen baseline')
    for batch in batches:
        runtime=batch.get('runtime_provenance',{})
        if (runtime.get('ollama_version')!=frozen['ollama_version']
            or frozen['models'][model]['weights_blob_sha256'] not in runtime.get('model_modelfile','')
            or batch.get('input_normalization')!=('NFC' if language=='hebrew' and model=='qwen3.6:35b-a3b' else 'none')):
            raise ValueError('Final output runtime or normalization differs from baseline')
    return True


def condo_state(job_id):
    result=subprocess.run(['squeue','--noheader','--jobs',str(job_id),'--format=%T'],capture_output=True,text=True)
    if result.returncode:raise RuntimeError('Cannot establish condo job state: '+result.stderr.strip())
    states=result.stdout.split()
    if len(states)>1:raise RuntimeError('Expected a single paired condo job')
    return states[0] if states else 'FINISHED'


def run_condition(route,language,model,condo_job,command,frozen,poll=2.0,state_fn=condo_state):
    """Hold a separate coordination lock until the entire worker has exited.

    The unchanged inference runner retains its own final-output lock. Condo
    waits here; scavenger observes the exact paired condo job ID and yields.
    Failed Slurm state queries stop scavenger conservatively, not condo.
    """
    directory=BASE/frozen['results_dir']/'coordination';directory.mkdir(parents=True,exist_ok=True)
    name=stem(language,model,frozen);lock=(directory/(name+'.lock')).open('a')
    events=directory/(name+f'_{route}_{os.environ.get("SLURM_JOB_ID","local")}.jsonl')
    def event(kind,**details):
        with events.open('a') as stream:stream.write(json.dumps({'time':time.time(),'route':route,'event':kind,**details})+'\n')
    child=None;interrupted=False
    def signal_handler(signum,frame):
        nonlocal interrupted
        interrupted=True
    handlers={s:signal.signal(s,signal_handler) for s in (signal.SIGTERM,signal.SIGINT)}
    def stop_worker():
        if child is not None and child.poll() is None:
            # Signal the existing worker shell; its trap stops both the
            # inference process group and Ollama before it exits.
            child.terminate()
            try:child.wait(timeout=90)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL);child.wait()
                raise RuntimeError('Worker did not stop cleanly; inspect its checkpoint and processes')
    def should_yield():
        if route!='scavenger':return False
        state=state_fn(condo_job)
        # FINISHED is intentionally terminal: a condo failure is not permission
        # for scavenger to restart after condo has taken precedence.
        return state!='PENDING'
    try:
        event('coordinator_started',paired_condo_job=condo_job)
        while True:
            if interrupted:return 143
            if should_yield():event('yield_before_start');return 0
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if route=='scavenger':event('another_worker_owns_condition');return 0
                time.sleep(poll)
        if should_yield():event('yield_after_lock');return 0
        if complete(language,model,frozen):event('already_complete');return 0
        child=subprocess.Popen(command,cwd=BASE,start_new_session=True)
        event('worker_started',pid=child.pid)
        while child.poll() is None:
            if interrupted:
                event('slurm_interruption');stop_worker();return 143
            try:yield_now=should_yield()
            except Exception:
                event('scheduler_query_failed');stop_worker();raise
            if yield_now:
                event('condo_takeover');stop_worker();event('yielded_to_condo');return 0
            time.sleep(poll)
        event('worker_finished',status=child.returncode)
        return child.returncode
    finally:
        try:stop_worker()
        finally:
            lock.close()
            for sig,handler in handlers.items():signal.signal(sig,handler)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('route',choices=['condo','scavenger']);p.add_argument('model');p.add_argument('language');p.add_argument('variant')
    p.add_argument('runner_args',nargs=argparse.REMAINDER);args=p.parse_args()
    frozen=verify()
    if args.language not in frozen['languages'] or args.model not in frozen['models']:p.error('Unknown condition')
    if not os.environ.get('SLURM_JOB_ID'):p.error('Run through the coordinated Slurm launcher')
    condo_job=os.environ.get('PAIRED_CONDO_JOB_ID')
    if args.route=='scavenger' and not (condo_job and condo_job.isdigit()):p.error('Scavenger requires its exact paired condo job ID')
    return run_condition(args.route,args.language,args.model,condo_job,
        ['bash','scripts/sbatch_v5_dev_train_current.sh',args.model,args.language,args.variant,*args.runner_args],frozen)


if __name__=='__main__':raise SystemExit(main())
