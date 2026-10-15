#!/usr/bin/env python3
"""Isolated 2x2x2 Hebrew parser diagnostic; never writes validation predictions."""
import argparse
import codecs
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
import unicodedata
import run_bloom_coding as runner
from check_v5_validation_freeze import BASE, verify

MODEL = 'qwen3.6:35b-a3b'
CELLS = [(f't{label}-{transport}-r{repeat}',temp,transport=='stream')
         for label,temp in [('0',0.0),('04',0.4)]
         for transport in ['buffered','stream'] for repeat in [1,2]]

INPUT_VARIANTS = ('original','compose-o-macron','nfc')

def normalize_records(records,variant):
    """Transform only allowlisted model input; never mutate source records."""
    if variant not in INPUT_VARIANTS:raise ValueError('Unknown input variant')
    def transform(value):
        if isinstance(value,str):
            if variant=='compose-o-macron':return value.replace('o\u0304','\u014d')
            if variant=='nfc':return unicodedata.normalize('NFC',value)
            return value
        if isinstance(value,list):return [transform(v) for v in value]
        if isinstance(value,dict):return {k:transform(v) for k,v in value.items()}
        return value
    return [transform(runner.prompt_record(r)) for r in records]

def request_payload(records,prompt,temperature,stream,input_variant='original'):
    return {'model':MODEL,'messages':[{'role':'system','content':prompt},
      {'role':'user','content':'Code the following batch. Return only the JSON output object.\n\n'+
       json.dumps(normalize_records(records,input_variant),ensure_ascii=False,indent=2)}],
      'stream':stream,'format':runner.build_output_schema([r['record_id'] for r in records],'bloom_v5'),
      'options':{'temperature':temperature,'seed':20261009,'num_ctx':32768,'num_predict':8000}}

def collect(response,directory,stream,started,deadline):
    """Retain exact response bytes and chunk timing; decode UTF-8 incrementally."""
    events=[];pending='';decoder=codecs.getincrementaldecoder('utf-8')('strict');offset=0
    with (directory/'response-body.bin').open('wb') as raw, \
         (directory/'chunks.jsonl').open('w') as timing, \
         (directory/'events.jsonl').open('w') as parsed:
        def event(line):
            if not line.strip():return
            item=json.loads(line)
            events.append(item)
            parsed.write(json.dumps(item,ensure_ascii=False)+'\n');parsed.flush()
        while True:
            if time.monotonic()>deadline:raise TimeoutError('Overall request deadline exceeded')
            data=response.read1(65536)
            if not data:break
            raw.write(data);raw.flush()
            timing.write(json.dumps({'elapsed_seconds':time.monotonic()-started,'byte_offset':offset,'bytes':len(data)})+'\n');timing.flush()
            offset+=len(data)
            pending+=decoder.decode(data)
            if stream:
                while '\n' in pending:
                    line,pending=pending.split('\n',1);event(line)
        pending+=decoder.decode(b'',final=True)
        if pending.strip():event(pending)
    return events

def summarize(events,ids,stream):
    errors=[e['error'] for e in events if e.get('error')]
    final=[e for e in events if e.get('done') is True]
    content=''.join(e.get('message',{}).get('content','') for e in events)
    thinking=''.join(e.get('message',{}).get('thinking','') for e in events)
    result={'events':len(events),'final_events':len(final),'server_errors':errors,
            'content_characters':len(content),'thinking_characters':len(thinking),
            'thinking_sha256':hashlib.sha256(thinking.encode()).hexdigest(),
            'content_sha256':hashlib.sha256(content.encode()).hexdigest(),
            'done_reason':final[-1].get('done_reason') if final else None,
            'generation_tokens':final[-1].get('eval_count') if final else None}
    if errors:result['outcome']='server_error'
    elif len(final)!=1:result['outcome']='incomplete_response'
    else:
        try:
            runner.validate_response(runner.extract_json_object(content),ids,'bloom_v5')
            result['outcome']='valid_complete_response'
        except (runner.ValidationError,ValueError,KeyError,TypeError) as error:
            result.update(outcome='invalid_final_answer',validation_error=str(error))
    return result

def run_request(url,payload,directory,timeout):
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'request.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    request_bytes=json.dumps(payload).encode()
    (directory/'request-body.bin').write_bytes(request_bytes)
    started=time.monotonic();result={}
    ids=[r['record_id'] for r in json.loads(payload['messages'][1]['content'].split('\n\n',1)[1])]
    try:
        req=urllib.request.Request(url,data=request_bytes,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=timeout) as response:
            result['http_status']=response.status
            events=collect(response,directory,payload['stream'],started,started+timeout)
        result.update(summarize(events,ids,payload['stream']))
    except urllib.error.HTTPError as error:
        (directory/'response-body.bin').write_bytes(error.read())
        result.update(http_status=error.code,outcome='server_http_error',error=str(error))
    except Exception as error:
        result.update(outcome='transport_or_protocol_error',exception_type=type(error).__name__,error=str(error))
    result['elapsed_seconds']=time.monotonic()-started
    result['request_sha256']=hashlib.sha256(request_bytes).hexdigest()
    (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cells',nargs='+',choices=[r[0] for r in CELLS])
    parser.add_argument('--timeout',type=int,default=1200)
    parser.add_argument('--input-variant',choices=INPUT_VARIANTS,default='original')
    args=parser.parse_args()
    if args.timeout<=0:parser.error('timeout must be positive')
    frozen=verify()
    rows=runner.read_jsonl(BASE/frozen['languages']['hebrew']['input'])[:5]
    if [r['record_id'] for r in rows]!=[f'heb_{i:06d}' for i in range(1,6)]:
        raise SystemExit('Frozen first Hebrew batch does not match the failing batch')
    prompt=(BASE/frozen['languages']['hebrew']['prompt']).read_text()
    # Refuse reuse: reruns get their own diagnostic directory and evidence.
    args.output.mkdir(parents=True,exist_ok=False)
    settings={k:os.environ.get(k) for k in ['CUDA_VISIBLE_DEVICES','OLLAMA_MODELS','OLLAMA_FLASH_ATTENTION','OLLAMA_NUM_PARALLEL','OLLAMA_KV_CACHE_TYPE']}
    manifest={'purpose':'Infrastructure diagnostic only; not validation predictions or accuracy evaluation',
              'record_ids':[r['record_id'] for r in rows],'settings':settings,'input_variant':args.input_variant,
              'normalization_scope':'Allowlisted input record string values only; system prompt and source files unchanged',
              'freeze_sha256':hashlib.sha256((BASE/'v5/dev_check_1_freeze.json').read_bytes()).hexdigest(),
              'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'design':'Two temperatures (0,0.4), two transports, two repeats; same seed/prompt/schema/batch/context/budget; fresh server per cell.'}
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    results=[]
    for name,temp,stream in CELLS:
        if args.cells and name not in args.cells:continue
        directory=args.output/name;directory.mkdir()
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        env={**os.environ,'OLLAMA_HOST':f'127.0.0.1:{port}'}
        server=None
        try:
            with (directory/'ollama-serve.log').open('wb') as log:
                server=subprocess.Popen(['ollama','serve'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:
                    for _ in range(90):
                        if server.poll() is not None:raise RuntimeError('Ollama exited before readiness')
                        try:
                            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/version',timeout=2) as response:
                                json.load(response)
                            break
                        except OSError:time.sleep(1)
                    else:raise RuntimeError('Ollama readiness timed out')
                    subprocess.run([sys.executable,str(BASE/'scripts/capture_coding_runtime.py'),
                        '--model',MODEL,'--ollama-url',f'http://127.0.0.1:{port}/api/chat',
                        '--output',str(directory/'runtime.json')],env=env,check=True)
                    result=run_request(f'http://127.0.0.1:{port}/api/chat',request_payload(rows,prompt,temp,stream,args.input_variant),directory,args.timeout)
                finally:
                    if server.poll() is None:
                        os.killpg(server.pid,signal.SIGTERM)
                        try:server.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            os.killpg(server.pid,signal.SIGKILL);server.wait()
        except Exception as error:
            result={'outcome':'setup_error','exception_type':type(error).__name__,'error':str(error)}
        result.update(cell=name,temperature=temp,stream=stream,input_variant=args.input_variant)
        log_text=(directory/'ollama-serve.log').read_text(errors='replace')
        result['parser_error_count']=log_text.count('unparsed Content-only output')
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        results.append(result)
        (args.output/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    # A parser failure is diagnostic evidence; setup/transport errors need attention.
    return int(any(r['outcome'] in ('setup_error','transport_or_protocol_error') for r in results))

if __name__=='__main__':
    def interrupted(signum,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,interrupted)
    signal.signal(signal.SIGINT,interrupted)
    try:raise SystemExit(main())
    except KeyboardInterrupt:raise SystemExit(143)
