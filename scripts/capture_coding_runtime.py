#!/usr/bin/env python3
"""Record actual model/template digest and GPU/runtime for a coding job."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True);p.add_argument('--ollama-url',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); base=a.ollama_url.rsplit('/api/',1)[0]
    def request(endpoint,payload=None):
        data=json.dumps(payload).encode() if payload is not None else None
        req=urllib.request.Request(base+'/api/'+endpoint,data=data,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
    version=request('version')['version'];tags=request('tags')['models']
    model=next((m for m in tags if m.get('name')==a.model or m.get('model')==a.model),None)
    if model is None:raise RuntimeError('Model digest unavailable')
    details=request('show',{'model':a.model})
    gpu_text=subprocess.check_output(['nvidia-smi','--id='+os.environ['CUDA_VISIBLE_DEVICES'],
        '--query-gpu=name,uuid,driver_version,memory.total','--format=csv,noheader,nounits'],text=True)
    gpus=[]
    for line in gpu_text.strip().splitlines():
        name,uuid,driver,memory=[v.strip() for v in line.split(',')]
        gpus.append({'name':name,'uuid':uuid,'driver_version':driver,'memory_mib':int(memory)})
    result={'model':a.model,'model_digest':model['digest'],'ollama_version':version,
        'template_sha256':hashlib.sha256(details.get('template','').encode()).hexdigest(),
        'model_parameters_sha256':hashlib.sha256(details.get('parameters','').encode()).hexdigest(),
        'model_details':details.get('details',{}),'gpus':gpus,
        'slurm_job_id':os.environ.get('SLURM_JOB_ID'),'restart_count':os.environ.get('SLURM_RESTART_COUNT','0')}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
