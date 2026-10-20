#!/usr/bin/env python3
"""Submit condo-priority jobs and interruptible scavenger helpers on L40S."""
import argparse
import getpass
import os
import re
import shlex
import shutil
import subprocess
import sys
from coordinate_v5_dev_train import BASE, complete, tag, verify


def queue(dry=False):
    if dry and not shutil.which('squeue'):return []
    result=subprocess.run(['squeue','--user',getpass.getuser(),'--noheader','--format=%i|%j|%T'],capture_output=True,text=True,check=True)
    jobs=[]
    for line in result.stdout.splitlines():
        fields=line.strip().split('|')
        if len(fields)!=3:raise ValueError('Unexpected squeue output')
        jobs.append(dict(zip(['id','name','state'],fields)))
    return jobs


def time_seconds(value):
    value=value.strip()
    if value.upper() in {'UNLIMITED','INFINITE'}:return float('inf')
    if not re.fullmatch(r'(\d+-)?\d+(:\d+){0,2}',value):raise ValueError('Invalid Slurm walltime: '+value)
    days=0
    if '-' in value:
        day_text,value=value.split('-',1);days=int(day_text)
        parts=[int(x) for x in value.split(':')]
        seconds=days*86400+sum(v*m for v,m in zip(parts,[3600,60,1]))
    else:
        parts=[int(x) for x in value.split(':')]
        multipliers={1:[60],2:[60,1],3:[3600,60,1]}[len(parts)]
        seconds=sum(v*m for v,m in zip(parts,multipliers))
    return seconds if seconds else float('inf')


def walltimes(dry=False):
    condo=os.environ.get('CONDO_WALLTIME',os.environ.get('WALLTIME','4-00:00:00'))
    requested=os.environ.get('SCAVENGER_WALLTIME',os.environ.get('WALLTIME','4-00:00:00'))
    time_seconds(condo);requested_seconds=time_seconds(requested)
    if dry and not shutil.which('scontrol'):
        if not os.environ.get('SCAVENGER_WALLTIME'):
            raise ValueError('Local dry run needs SCAVENGER_WALLTIME; live submissions query the partition MaxTime automatically')
        print('Local dry run: partition maximum not queried; using explicit SCAVENGER_WALLTIME')
        return {'condo':condo,'scavenger':requested}
    result=subprocess.run(['scontrol','--oneliner','show','partition','gpu-scavenger'],capture_output=True,text=True,check=True)
    match=re.search(r'(?:^|\s)MaxTime=(\S+)',result.stdout)
    if not match:raise ValueError('Cannot determine gpu-scavenger MaxTime; no jobs submitted')
    maximum=match.group(1);maximum_seconds=time_seconds(maximum)
    scavenger=maximum if maximum_seconds<requested_seconds else requested
    print(f'Walltimes: condo={condo}; scavenger={scavenger} (partition maximum {maximum})')
    return {'condo':condo,'scavenger':scavenger}


def job_command(route,model,language,frozen,condo_job=None,walltime=None):
    if walltime is None:raise ValueError('Resolve route-specific partition time limits before building jobs')
    condition=frozen['languages'][language];short='gemma' if model=='gemma4:31b' else 'qwen'
    output=frozen['results_dir'];logs=output+'/logs';name=f'v5dt-{route}-{short}-{condition["code"]}'
    args=['sbatch','--parsable','--partition='+('gpu-scavenger' if route=='scavenger' else 'l40s-gcondo'),
          '--constraint=l40s','--gres=gpu:1','--ntasks=1','--cpus-per-task=4','--mem=48g',
          '--time='+walltime,'--requeue','--signal=B:TERM@60','--open-mode=append',
          '--job-name='+name,'--output='+logs+'/sbatch_%x_%j.out','--export=ALL']
    if route=='scavenger':args+=['--account=gpu-scavenger']
    else:
        args+=['--qos=copsy-l40s-gcondo']
        if os.environ.get('CONDO_ACCOUNT'):args+=['--account='+os.environ['CONDO_ACCOUNT']]
    args+=['scripts/sbatch_v5_dev_train_coordinated.sh',route,model,language,'en' if language=='english' else 'engex',
           '--num-ctx','32768','--num-predict','8000','--temperature','0','--seed','20261009','--max-retries','0','--resume']
    env={k:v for k,v in os.environ.items() if not k.startswith('SBATCH_') and k!='PAIRED_CONDO_JOB_ID'}
    env.update(LIMIT='',SPLIT='dev_train',RUN_SETS='unmasked',BATCH_SIZE=str(frozen['models'][model]['batch_size']),
       RESULTS_DIR=output,LOG_DIR=logs,PROMPT_OVERRIDE=condition['prompt'],PROMPT_VERSION_OVERRIDE=tag(language,model,frozen),
       MIN_GPU_MEMORY_MIB='45000',CAPTURE_RUNTIME='1',EXPECTED_OLLAMA_VERSION=frozen['ollama_version'],
       EXPECTED_MODEL_BLOB_SHA256=frozen['models'][model]['weights_blob_sha256'],OLLAMA_NUM_PARALLEL='1',
       OLLAMA_FLASH_ATTENTION='false',OLLAMA_KV_CACHE_TYPE='f16')
    if condo_job:env['PAIRED_CONDO_JOB_ID']=str(condo_job)
    return args,env


def launch(args,env,dry,number):
    if dry:
        print('DRY:',shlex.join(args),'PAIRED_CONDO_JOB_ID='+env.get('PAIRED_CONDO_JOB_ID','(self)'))
        return str(900000000+number)
    result=subprocess.run(args,cwd=BASE,env=env,capture_output=True,text=True,check=True)
    answer=result.stdout.strip()
    if not re.fullmatch(r'\d+(;[^\s]+)?',answer):raise RuntimeError('Unexpected sbatch response; check queue before retrying: '+answer)
    job_id=answer.split(';')[0];print('Submitted',job_id,args[args.index('--export=ALL')+2:][:4],flush=True)
    return job_id


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dry-run',action='store_true')
    p.add_argument('--replace-pending-condo',action='store_true',help='Cancel only selected pending v5-train-* jobs, replacing them with coordinated versions; running jobs stay untouched.')
    args=p.parse_args();dry=args.dry_run or bool(os.environ.get('DRY_RUN'));frozen=verify()
    languages=os.environ.get('LANGUAGES','english german hebrew spanish tagalog').split()
    models=os.environ.get('MODELS','gemma4:31b qwen3.6:35b-a3b').split()
    if len(set(languages))!=len(languages) or any(x not in frozen['languages'] for x in languages):p.error('Invalid LANGUAGES')
    if len(set(models))!=len(models) or any(x not in frozen['models'] for x in models):p.error('Invalid MODELS')
    times=walltimes(dry)  # Preflight before any cancellation or submission.
    jobs=queue(dry);plans=[];cancel=[]
    for language in languages:
        for model in models:
            if complete(language,model,frozen):print('Complete; skipping',language,model);continue
            short='gemma' if model=='gemma4:31b' else 'qwen';code=frozen['languages'][language]['code']
            legacy=[j for j in jobs if j['name']==f'v5-train-{short}-{code}']
            coordinated=[j for j in jobs if j['name'] in {f'v5dt-condo-{short}-{code}',f'v5dt-scavenger-{short}-{code}'}]
            if coordinated:p.error('Coordinated jobs already queued/running for '+language+' / '+model+'; do not submit duplicates')
            if any(j['state']!='PENDING' for j in legacy):print('Existing condo has started; leaving it alone:',language,model);continue
            if legacy and not args.replace_pending_condo:p.error('Pending old condo jobs require --replace-pending-condo so their worker can wait safely during takeover')
            cancel.extend(j['id'] for j in legacy);plans.append((language,model))
    if cancel:
        command=['scancel','--state=PENDING',*cancel]
        if dry:print('DRY:',shlex.join(command))
        else:
            subprocess.run(command,check=True)
            # A job may have started between inventory and cancellation.
            remaining=queue()
            safe=[]
            for language,model in plans:
                short='gemma' if model=='gemma4:31b' else 'qwen';code=frozen['languages'][language]['code']
                if any(j['name']==f'v5-train-{short}-{code}' for j in remaining):
                    print('Original condo still present (possibly just started); leaving condition alone:',language,model)
                else:safe.append((language,model))
            plans=safe
    (BASE/frozen['results_dir']/'logs').mkdir(parents=True,exist_ok=True)
    for number,(language,model) in enumerate(plans):
        command,env=job_command('condo',model,language,frozen,walltime=times['condo'])
        condo=launch(command,env,dry,2*number)
        command,env=job_command('scavenger',model,language,frozen,condo,walltime=times['scavenger'])
        launch(command,env,dry,2*number+1)
    return 0


if __name__=='__main__':raise SystemExit(main())
