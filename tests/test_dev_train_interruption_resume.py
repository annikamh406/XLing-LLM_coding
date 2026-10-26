"""Preserve checkpoints/audits and keep genuine model failures bounded."""
import argparse
import hashlib
import gc
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'scripts'))
import run_bloom_coding as runner
import run_v5_dev_train_interruption_resume as fix
from run_v5_validation_recovery import Recovery, RecoveryExhausted


def payload(records):
    return {'schema_version':'bloom_v5','predictions':[dict(record_id=r['record_id'],bloom_label='Denial',certain='Yes',comments='',flags={k:'No' for k in runner.REQUIRED_FLAGS}) for r in records]}


class InterruptionTests(unittest.TestCase):
    def setup_call(self,root):
        args=argparse.Namespace(split='dev_train',model='qwen3.6:35b-a3b',schema_version='bloom_v5',prompt_version='test',results_dir=root/'results',seed=20261009)
        call=dict(records=[{'record_id':'a'},{'record_id':'b'}],prompt='frozen',seed=20261009,temperature=0.,top_p=None,top_k=None,min_p=None,num_ctx=32768,num_predict=8000,timeout=1200,model=args.model,output_schema={},url='fake',validation_feedback=None)
        amendment=root/'amendment.json';amendment.write_text(json.dumps({'legacy_interrupted_batches':{}}))
        return args,call,amendment

    def authorize(self,root,amendment,path):
        d=json.loads(amendment.read_text());d['legacy_interrupted_batches'][str(path.resolve().relative_to(root.resolve()))]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest()};amendment.write_text(json.dumps(d))

    def test_three_legacy_interruptions_do_not_spend_model_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,call,amendment=self.setup_call(root)
            def interrupted(**kw):raise SystemExit(143)
            old=Recovery(args,interrupted)
            for _ in range(3):
                with self.assertRaises(SystemExit):old(**call)
            legacy=next(old.directory.glob('batch-*.json'));before=legacy.read_bytes();self.authorize(root,amendment,legacy)
            calls=[]
            def chat(**kw):calls.append(kw);return payload(kw['records']),{'done':True}
            with patch.object(fix,'BASE',root),patch.object(fix,'AMENDMENT',amendment):
                wrapped=fix.InterruptionRecovery(args,chat);answer,raw=wrapped(**call);wrapped(**call)
            self.assertEqual(len(calls),1);self.assertEqual(calls[0]['num_predict'],8000)
            rows=fix.decorate([{'raw_response':raw}]);self.assertEqual(rows[0]['model_attempt_count'],1)
            self.assertEqual(rows[0]['interruption_count'],3);self.assertEqual(rows[0]['attempt_count'],4)
            self.assertEqual(legacy.read_bytes(),before)
            self.assertEqual([p['record_id'] for p in answer['predictions']],['a','b'])

    def test_genuine_failures_stay_bounded_across_resubmissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,call,amendment=self.setup_call(root);calls=[]
            def fail(**kw):calls.append(kw);raise runner.RetryableBatchError('empty content')
            with patch.object(fix,'BASE',root),patch.object(fix,'AMENDMENT',amendment):
                wrapped=fix.InterruptionRecovery(args,fail)
                for _ in range(2):
                    with self.assertRaises(RecoveryExhausted):wrapped(**call)
            self.assertEqual(len(calls),3);self.assertEqual([c['num_predict'] for c in calls],[8000,8000,16000])
            self.assertTrue(all(c['temperature']==0 and c['seed']==20261009 for c in calls))

    def test_recorded_condo_signal_can_resume_but_unknown_crash_cannot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,call,amendment=self.setup_call(root)
            def interrupted(**kw):os.kill(os.getpid(),signal.SIGTERM)
            with patch.object(fix,'BASE',root),patch.object(fix,'AMENDMENT',amendment):
                wrapped=fix.InterruptionRecovery(args,interrupted)
                with self.assertRaises(SystemExit):wrapped(**call)
                wrapped.chat=lambda **kw:(payload(kw['records']),{'done':True})
                _,raw=wrapped(**call)
                self.assertEqual([a['status'] for a in raw['validation_recovery']['attempts']],['interrupted','success'])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,call,amendment=self.setup_call(root)
            def crash(**kw):raise RuntimeError('unknown crash')
            with patch.object(fix,'BASE',root),patch.object(fix,'AMENDMENT',amendment):
                wrapped=fix.InterruptionRecovery(args,crash)
                with self.assertRaises(RuntimeError):wrapped(**call)
                with self.assertRaisesRegex(RecoveryExhausted,'without a recorded termination'):wrapped(**call)

    def test_real_checkpoint_resumes_without_repeating_successful_batches(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);split=root/'split';split.mkdir();records=[{'record_id':str(i)} for i in range(10)]
            (split/'dev_train.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records));prompt=root/'prompt';prompt.write_text('frozen')
            argv=['runner','--split','dev_train','--split-dir',str(split),'--results-dir',str(root/'results'),'--prompt',str(prompt),'--prompt-version','test','--model','qwen3.6:35b-a3b','--batch-size','5','--temperature','0','--seed','20261009','--num-ctx','32768','--max-retries','0','--resume']
            amendment=root/'amendment.json';amendment.write_text(json.dumps({'legacy_interrupted_batches':{}}))
            with patch.object(sys,'argv',argv):args=runner.parse_args()
            def old_chat(**kw):
                if kw['records'][0]['record_id']=='5':raise SystemExit(143)
                return payload(kw['records']),{'done':True}
            old=Recovery(args,old_chat)
            with patch.object(sys,'argv',argv),patch.object(runner,'ollama_chat',old):
                for _ in range(3):
                    with self.assertRaises(SystemExit):runner.main()
            cp=next((root/'results').glob('*_checkpoint.json'));before=json.loads(cp.read_text())
            legacy=old.directory/'batch-2.json';old_bytes=legacy.read_bytes();self.authorize(root,amendment,legacy)
            calls=[]
            def chat(**kw):calls.append([r['record_id'] for r in kw['records']]);return payload(kw['records']),{'done':True}
            with patch.object(fix,'BASE',root),patch.object(fix,'AMENDMENT',amendment),patch.object(sys,'argv',argv),patch.object(runner,'ollama_chat',fix.InterruptionRecovery(args,chat)):
                gc.collect()  # Simulated separate jobs must release exception-held locks.
                self.assertEqual(runner.main(),0)
                gc.collect()
                self.assertEqual(runner.main(),0)
            after=json.loads(cp.read_text());self.assertEqual(calls,[['5','6','7','8','9']])
            self.assertEqual(after['provenance'],before['provenance'])
            self.assertEqual(after['predictions'][:5],before['predictions']);self.assertEqual(after['raw_responses'][:1],before['raw_responses'])
            self.assertEqual(legacy.read_bytes(),old_bytes)

    def test_relative_oscar_output_paths_migrate_the_authorized_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,call,amendment=self.setup_call(root);args.results_dir=Path('results')
            previous=Path.cwd()
            try:
                os.chdir(root)
                def interrupted(**kw):raise SystemExit(143)
                old=Recovery(args,interrupted)
                for _ in range(3):
                    with self.assertRaises(SystemExit):old(**call)
                legacy=next(old.directory.glob('batch-*.json'));before=legacy.read_bytes()
                self.authorize(root,amendment,legacy.resolve())
                with patch.object(fix,'BASE',root),patch.object(fix,'AMENDMENT',amendment):
                    answer,_=fix.InterruptionRecovery(args,lambda **kw:(payload(kw['records']),{'done':True}))(**call)
                self.assertEqual(len(answer['predictions']),2);self.assertEqual(legacy.read_bytes(),before)
            finally:os.chdir(previous)

    def test_legacy_genuine_failures_are_not_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,call,amendment=self.setup_call(root)
            def fail(**kw):raise runner.RetryableBatchError('empty response')
            old=Recovery(args,fail)
            with self.assertRaises(RecoveryExhausted):old(**call)
            calls=[]
            def chat(**kw):calls.append(kw);return payload(kw['records']),{'done':True}
            with patch.object(fix,'BASE',root),patch.object(fix,'AMENDMENT',amendment):
                with self.assertRaisesRegex(RecoveryExhausted,'Three completed'):
                    fix.InterruptionRecovery(args,chat)(**call)
            self.assertEqual(calls,[])

    def test_three_new_interruptions_are_also_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,call,amendment=self.setup_call(root)
            def interrupted(**kw):os.kill(os.getpid(),signal.SIGTERM)
            with patch.object(fix,'BASE',root),patch.object(fix,'AMENDMENT',amendment):
                wrapped=fix.InterruptionRecovery(args,interrupted)
                for _ in range(3):
                    with self.assertRaises(SystemExit):wrapped(**call)
                with self.assertRaisesRegex(RecoveryExhausted,'Three additional condo interruptions'):wrapped(**call)

    def test_format_repair_keeps_original_temperature_and_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,call,amendment=self.setup_call(root);calls=[]
            def chat(**kw):
                calls.append(kw)
                return payload(kw['records'] if kw['validation_feedback'] else [kw['records'][0]]*2),{'done':True}
            with patch.object(fix,'BASE',root),patch.object(fix,'AMENDMENT',amendment):
                fix.InterruptionRecovery(args,chat)(**call)
            self.assertEqual(len(calls),3)
            self.assertTrue(all(c['temperature']==0 and c['num_predict']==8000 for c in calls))
            self.assertIn('a, b',calls[-1]['validation_feedback'])

    def test_existing_success_is_reused_without_reclassifying_earlier_interruptions(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,call,amendment=self.setup_call(root)
            def interrupted(**kw):raise SystemExit(143)
            old=Recovery(args,interrupted)
            with self.assertRaises(SystemExit):old(**call)
            old.chat=lambda **kw:(payload(kw['records']),{'done':True})
            old(**call);path=next(old.directory.glob('batch-*.json'));before=path.read_bytes()
            def unexpected(**kw):raise AssertionError('Should reuse saved successful response')
            with patch.object(fix,'BASE',root),patch.object(fix,'AMENDMENT',amendment):
                _,raw=fix.InterruptionRecovery(args,unexpected)(**call)
            self.assertEqual(raw['validation_recovery']['policy'],'validation-recovery-v1')
            self.assertEqual(path.read_bytes(),before)

    def test_scavenger_route_is_rejected(self):
        with patch.object(fix,'verify',return_value=({}, {'languages':['hebrew']})),patch.object(runner,'parse_args',return_value=argparse.Namespace(model='qwen3.6:35b-a3b')),patch.object(fix.baseline,'validate_args',return_value='hebrew'),patch.object(fix.baseline,'main') as main,patch.dict(os.environ,{'SLURM_JOB_PARTITION':'gpu-scavenger'}):
            with self.assertRaisesRegex(ValueError,'must run on condo'):fix.main()
            main.assert_not_called()

    def test_only_three_qwen_condo_jobs_with_shared_checkpoint_tags(self):
        result=subprocess.run(['bash','scripts/submit_v5_dev_train_interruption_resume.sh'],cwd=BASE,env={**os.environ,'DRY_RUN':'1','LIMIT':'10','SPLIT':'test_lockbox','LANGUAGES':'hebrew spanish tagalog','MODELS':'qwen3.6:35b-a3b'},capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        jobs=[line for line in result.stdout.splitlines() if line.startswith('DRY:')];self.assertEqual(len(jobs),3)
        self.assertTrue(all('--partition=l40s-gcondo' in j and '--qos=copsy-l40s-gcondo' in j and 'gpu-scavenger' not in j for j in jobs))
        self.assertTrue(all('SPLIT=dev_train' in j and 'BATCH_SIZE=5' in j and 'interruption_resume_logs' in j for j in jobs))
        self.assertEqual(sum('p005dt1nfc-he' in j for j in jobs),1)


if __name__=='__main__':unittest.main()
