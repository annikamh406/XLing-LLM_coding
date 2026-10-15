#!/usr/bin/env python3
"""Bounded recovery around the unchanged frozen runner; preserve checkpoint identity."""
import hashlib
import json
import os
import sys
from pathlib import Path
import run_bloom_coding as runner
from check_v5_recovery_freeze import check as verify
from validation_runtime_compat import compatible_runtime

POLICY = 'validation-recovery-v1'

class RecoveryExhausted(RuntimeError):
    pass

class Recovery:
    def __init__(self, args, chat):
        self.args, self.chat = args, chat
        self.prefix = f'{args.split}_{runner.clean_model_name(args.model)}_{args.schema_version}_{args.prompt_version}'
        self.directory = args.results_dir / 'recovery' / self.prefix

    def __call__(self, **kwargs):
        ids = [r['record_id'] for r in kwargs['records']]
        batch = kwargs['seed'] - self.args.seed + 1
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f'batch-{batch}.json'
        original_options = {k:kwargs[k] for k in ('temperature','seed','top_p','top_k','min_p','num_ctx','num_predict')}
        fingerprint = hashlib.sha256(json.dumps({'ids':ids,'records':kwargs['records'],
            'prompt':kwargs['prompt'],'options':original_options},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        state = {'policy':POLICY,'batch_number':batch,'record_ids':ids,'fingerprint':fingerprint,'attempts':[]}
        if path.exists():
            state = json.loads(path.read_text())
            if state['policy'] != POLICY or state['fingerprint'] != fingerprint:
                raise RecoveryExhausted('Recovery log differs from frozen batch; refusing to resume')
        else:
            historical = self.args.results_dir / f'{self.prefix}_failed_batch-{batch}.json'
            if historical.exists():
                failure = json.loads(historical.read_text())
                if failure['record_ids'] != ids or failure['model'] != self.args.model or failure['prompt_version'] != self.args.prompt_version:
                    raise RecoveryExhausted('Historical failure does not match this condition')
                state['attempts'].append({'stage':0,'status':'failed','historical_failure':str(historical),
                    'error':failure['validation_error'],
                    'error_kind':'format' if failure.get('parsed_payload') else 'inference',
                    'effective_decoding_options':original_options,'timeout':kwargs['timeout']})
                runner.atomic_write(path,json.dumps(state,ensure_ascii=False)+'\n')
        # A successful response is persisted before checkpoint publication, so
        # interruption between the two writes does not consume another attempt.
        if state['attempts'] and state['attempts'][-1]['status'] == 'success':
            return self.success(state)
        for stage in range(len(state['attempts']),3):
            call = dict(kwargs)
            call['validation_feedback'] = None
            if stage == 2:
                last = state['attempts'][-1]
                if last.get('error_kind') == 'format':
                    call['validation_feedback'] = ('Return exactly one prediction for each of these record IDs, '
                        'with no missing or duplicate IDs: '+', '.join(ids)+'. Validation error: '+last['error'])
                else:
                    call['num_predict'] = 16000
                    call['timeout'] = 2400
            options = {k:call[k] for k in original_options}
            attempt = {'stage':stage,'status':'started','effective_decoding_options':options,
                       'timeout':call['timeout'],'validation_feedback':call['validation_feedback']}
            state['attempts'].append(attempt)
            runner.atomic_write(path,json.dumps(state,ensure_ascii=False)+'\n')
            print(f'Recovery policy {POLICY}: batch {batch}, stage {stage}, temperature {call["temperature"]}',file=sys.stderr)
            payload = raw = None
            try:
                payload, raw = self.chat(**call)
                runner.validate_response(payload,ids,self.args.schema_version)
                attempt.update(status='success',parsed_payload=payload,raw_response=raw)
            except (runner.ValidationError,runner.RetryableBatchError) as error:
                attempt.update(status='failed',error=str(error),
                    error_kind='format' if isinstance(error,runner.ValidationError) else 'inference',
                    parsed_payload=payload,raw_response=raw)
            runner.atomic_write(path,json.dumps(state,ensure_ascii=False)+'\n')
            if attempt['status'] == 'success':
                return self.success(state)
        raise RecoveryExhausted(f'Batch {batch}: bounded recovery exhausted; condition remains incomplete. Audit: {path}')

    def success(self,state):
        last = state['attempts'][-1]
        raw = dict(last['raw_response'])
        # Full failed responses remain in the persistent recovery audit file.
        raw['validation_recovery'] = {'policy':POLICY,'batch_number':state['batch_number'],
            'record_ids':state['record_ids'],'fingerprint':state['fingerprint'],
            'attempts':[{k:v for k,v in a.items() if k not in ('parsed_payload','raw_response')}
                        for a in state['attempts']]}
        return last['parsed_payload'], raw

def decorate(rows):
    for batch in rows:
        recovery = batch.get('raw_response',{}).get('validation_recovery')
        if recovery:
            batch['recovery_policy'] = POLICY
            batch['recovered'] = len(recovery['attempts']) > 1
            batch['attempt_count'] = len(recovery['attempts'])
            batch['effective_decoding_options'] = recovery['attempts'][-1]['effective_decoding_options']
    return rows

def main():
    verify()  # The original freeze and runner hashes remain unchanged.
    args = runner.parse_args()
    if (args.split != 'dev_check_1' or args.model != 'qwen3.6:35b-a3b' or args.batch_size != 5
        or args.temperature != 0 or args.seed != 20261009 or args.max_retries != 0
        or args.num_predict != 8000 or args.timeout != 1200 or not args.resume or args.limit is not None):
        raise SystemExit('Recovery requires the original full Qwen validation configuration')
    runtime_path = os.environ.get('CODING_RUNTIME_PATH')
    if runtime_path:
        os.environ['CODING_RUNTIME_PATH'] = str(compatible_runtime(args,runtime_path))
    runner.ollama_chat = Recovery(args,runner.ollama_chat)
    atomic, write = runner.atomic_write, runner.write_jsonl
    def atomic_checkpoint(path,text):
        if str(path).endswith('_checkpoint.json'):
            state = json.loads(text)
            decorate(state['raw_responses'])
            text = json.dumps(state,ensure_ascii=False)+'\n'
        atomic(path,text)
    def write_output(path,rows):
        if str(path).endswith('_raw_responses.jsonl'):
            decorate(rows)
        write(path,rows)
    runner.atomic_write = atomic_checkpoint
    runner.write_jsonl = write_output
    return runner.main()

if __name__ == '__main__':
    raise SystemExit(main())
