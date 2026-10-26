#!/usr/bin/env python3
"""Audited condo-only continuation: interruptions do not spend response retries."""
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import run_bloom_coding as runner
import run_v5_dev_train_current as baseline
from check_v5_dev_train_current import BASE, MANIFEST, verify as verify_training
from run_v5_validation_recovery import Recovery as OriginalRecovery, RecoveryExhausted, decorate as original_decorate

AMENDMENT=BASE/'v5/dev_train_interruption_recovery.json'
POLICY='dev-train-interruption-recovery-v1'


def verify():
    frozen=verify_training();amendment=json.loads(AMENDMENT.read_text())
    if hashlib.sha256(MANIFEST.read_bytes()).hexdigest()!=amendment['training_freeze_sha256']:
        raise ValueError('Original training freeze changed')
    for name,expected in amendment['files_sha256'].items():
        if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=expected:raise ValueError('Interruption amendment file changed: '+name)
    for name,evidence in amendment['legacy_interrupted_batches'].items():
        if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=evidence['sha256']:
            raise ValueError('Historical interruption audit changed; review before continuing: '+name)
    return frozen,amendment


class InterruptionRecovery(OriginalRecovery):
    def __init__(self,args,chat):
        super().__init__(args,chat)
        self.legacy_directory=self.directory
        self.directory=args.results_dir/'recovery_interruption_resume'/self.prefix

    def __call__(self,**kwargs):
        ids=[r['record_id'] for r in kwargs['records']];batch=kwargs['seed']-self.args.seed+1
        options={k:kwargs[k] for k in ('temperature','seed','top_p','top_k','min_p','num_ctx','num_predict')}
        fingerprint=hashlib.sha256(json.dumps({'ids':ids,'records':kwargs['records'],'prompt':kwargs['prompt'],'options':options},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        self.directory.mkdir(parents=True,exist_ok=True);path=self.directory/f'batch-{batch}.json'
        amendment=json.loads(AMENDMENT.read_text())
        amendment_hash=hashlib.sha256(AMENDMENT.read_bytes()).hexdigest()
        state={'policy':POLICY,'batch_number':batch,'record_ids':ids,'fingerprint':fingerprint,
               'amendment_sha256':amendment_hash,'attempts':[]}
        def save():runner.atomic_write(path,json.dumps(state,ensure_ascii=False)+'\n')
        if path.exists():
            state=json.loads(path.read_text())
            if state['policy']!=POLICY or state['fingerprint']!=fingerprint or state['amendment_sha256']!=amendment_hash:
                raise RecoveryExhausted('Amended ledger differs from this request or amendment')
        else:
            legacy=self.legacy_directory/f'batch-{batch}.json'
            if legacy.exists():
                old=json.loads(legacy.read_text())
                if old['fingerprint']!=fingerprint or old['policy']!='validation-recovery-v1':
                    raise RecoveryExhausted('Legacy request fingerprint or policy differs')
                if old['attempts'] and old['attempts'][-1]['status']=='success':
                    return OriginalRecovery.success(self,old)
                relative=str(legacy.resolve().relative_to(BASE.resolve()));evidence=amendment['legacy_interrupted_batches'].get(relative)
                for number,a in enumerate(old['attempts']):
                    attempt=copy.deepcopy(a);attempt['source']='legacy';attempt['legacy_attempt_index']=number
                    if attempt['status']=='started':
                        if (not evidence or hashlib.sha256(legacy.read_bytes()).hexdigest()!=evidence['sha256']
                            or attempt.get('raw_response') is not None or attempt.get('parsed_payload') is not None or attempt.get('error')):
                            raise RecoveryExhausted('Unresolved legacy request has no authorized interruption evidence')
                        attempt.update(original_status='started',status='interrupted',classification='authorized_legacy_scheduler_interruption')
                    state['attempts'].append(attempt)
                state['legacy_audit']={'path':relative,'sha256':hashlib.sha256(legacy.read_bytes()).hexdigest()}
            save()
        if state['attempts'] and state['attempts'][-1]['status']=='success':return self.success(state)
        if any(a['status']=='started' for a in state['attempts']):
            raise RecoveryExhausted('Unreturned request without a recorded termination signal requires review; not silently retried')
        while True:
            finished=[a for a in state['attempts'] if a['status'] in ('failed','success')]
            interruptions=[a for a in state['attempts'] if a['status']=='interrupted' and a.get('source')!='legacy']
            if len(finished)>=3:raise RecoveryExhausted('Three completed response/failure attempts exhausted; no reset on resubmission')
            if len(interruptions)>=3:raise RecoveryExhausted('Three additional condo interruptions exhausted; manual review required')
            stage=len(finished);call=dict(kwargs);call['validation_feedback']=None
            if stage==2:
                last=finished[-1]
                if last.get('error_kind')=='format':
                    call['validation_feedback']='Return exactly one prediction for each of these record IDs, with no missing or duplicate IDs: '+', '.join(ids)+'. Validation error: '+last['error']
                else:call['num_predict']=16000;call['timeout']=2400
            attempt={'stage':stage,'source':'amended_condo','status':'started','effective_decoding_options':{k:call[k] for k in options},
                     'timeout':call['timeout'],'validation_feedback':call['validation_feedback'],'slurm_job_id':os.environ.get('SLURM_JOB_ID')}
            state['attempts'].append(attempt);save()
            def interrupted(signum,frame):
                if attempt['status']=='started':
                    attempt.update(status='interrupted',classification='recorded_termination_signal',signal=signum)
                save();raise SystemExit(128+signum)
            handlers={s:signal.signal(s,interrupted) for s in (signal.SIGTERM,signal.SIGINT)}
            payload=raw=None
            try:
                payload,raw=self.chat(**call)
                runner.validate_response(payload,ids,self.args.schema_version)
                attempt.update(status='success',parsed_payload=payload,raw_response=raw)
            except (runner.ValidationError,runner.RetryableBatchError) as error:
                attempt.update(status='failed',error=str(error),error_kind='format' if isinstance(error,runner.ValidationError) else 'inference',parsed_payload=payload,raw_response=raw)
            finally:
                # Persist the outcome before restoring termination handlers.
                save()
                for sig,handler in handlers.items():signal.signal(sig,handler)
            if attempt['status']=='success':return self.success(state)

    def success(self,state):
        last=state['attempts'][-1];raw=dict(last['raw_response'])
        raw['validation_recovery']={k:state[k] for k in ('policy','batch_number','record_ids','fingerprint','amendment_sha256')}
        raw['validation_recovery']['attempts']=[{k:v for k,v in a.items() if k not in ('parsed_payload','raw_response')} for a in state['attempts']]
        if state.get('legacy_audit'):raw['validation_recovery']['legacy_audit']=state['legacy_audit']
        return last['parsed_payload'],raw


def decorate(rows):
    for batch in rows:
        recovery=batch.get('raw_response',{}).get('validation_recovery')
        if not recovery:continue
        if recovery['policy']=='validation-recovery-v1':original_decorate([batch]);continue
        if recovery['policy']!=POLICY:raise ValueError('Unknown recovery policy in saved batch')
        attempts=recovery['attempts']
        batch.update(recovery_policy=POLICY,attempt_count=len(attempts),
            model_attempt_count=sum(a['status'] in ('failed','success') for a in attempts),
            interruption_count=sum(a['status']=='interrupted' for a in attempts),recovered=len(attempts)>1,
            effective_decoding_options=attempts[-1]['effective_decoding_options'],
            interruption_recovery_amendment_sha256=recovery['amendment_sha256'])
    return rows


def main():
    frozen,amendment=verify();args=runner.parse_args();language=baseline.validate_args(args,frozen)
    if args.model!='qwen3.6:35b-a3b' or language not in amendment['languages']:
        raise ValueError('Interruption continuation is restricted to Qwen Hebrew, Spanish and Tagalog')
    if os.environ.get('SLURM_JOB_PARTITION')!='l40s-gcondo':
        raise ValueError('This recovery amendment must run on condo, never scavenger')
    original_class,original_decorator=baseline.Recovery,baseline.decorate_recovery
    try:
        baseline.Recovery=InterruptionRecovery;baseline.decorate_recovery=decorate
        return baseline.main()
    finally:baseline.Recovery=original_class;baseline.decorate_recovery=original_decorator


if __name__=='__main__':
    if sys.argv[1:]==['--verify']:verify();print('Training freeze and interruption recovery amendment verified.')
    else:raise SystemExit(main())
