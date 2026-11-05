"""Hardware exception preserves validated work and does not reset failure budgets."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import resume_v611_tagalog_ecc as recovery
import run_bloom_coding as runner
import v611_diagnostic as config
from test_v611_diagnostic import DiagnosticTests, payload


class ECCRecoveryTests(unittest.TestCase):
    def fixture(self,root):
        f,rt,manifest=DiagnosticTests().fixture(root)
        c=f['languages'].pop('english');f['languages']['tagalog']=c
        runtime=json.loads(rt.read_text());runtime['gpus'][0]['uuid']='healthy';rt.write_text(json.dumps(runtime))
        files=config.paths(f,'tagalog',root);files['checkpoint'].parent.mkdir(parents=True)
        state={'provenance':config.provenance(f,c,manifest),'predictions':[payload('1')['predictions'][0]],
            'raw_responses':[{'record_ids':['1'],'original_batch_number':1,'effective_decoding_options':c['selection'][0]['original_effective_options'],
                'attempt_count':1,'intervention':'6.1.1','prompt_version':c['prompt_version'],'runtime_provenance':runtime,'raw_response':{'done':True}}]}
        runner.atomic_write(files['checkpoint'],json.dumps(state)+'\n')
        failure={'record_id':'19','effective_decoding_options':c['selection'][1]['original_effective_options'],
                 'parsed_payload':None,'raw_response':None,'error':'HTTP 500'}
        runner.atomic_write(files['failure'],json.dumps(failure)+'\n')
        (root/'server.log').write_text('CUDA error: uncorrectable ECC error encountered')
        (root/'job.log').write_text('Nodelist gpu3001')
        a={'language':'tagalog','freeze_sha256':config.digest(manifest),'files_sha256':{},
            'evidence_sha256':{p:config.digest(root/p) for p in ('server.log','job.log')},
            'server_log':'server.log','job_log':'job.log','excluded_node':'gpu3001','excluded_gpu_uuid':'faulty',
            'initial_saved_records':1,'initial_prefix_sha256':recovery.prefix_hash(state,1),
            'archive_failure':'results/ecc_recovery/original.json','recovery_dir':'results/ecc_recovery',
            'original_failure_sha256':config.digest(files['failure']),'failed_record_id':'19'}
        amendment=root/'amendment.json';amendment.write_text(json.dumps(a))
        return f,rt,manifest,amendment,files,state

    def test_resume_only_remaining_and_preserve_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);f,rt,m,a,files,old=self.fixture(root);original_failure=files['failure'].read_bytes();calls=[]
            def chat(**kw):
                calls.append(kw);return payload(kw['records'][0]['record_id'],'Rejection'),{'done':True}
            with patch.object(config,'verify',return_value=f),patch.object(runner,'ollama_chat',chat):
                recovery.run('test',rt,root,m,a)
                recovery.run('test',rt,root,m,a)
            self.assertEqual([c['seed'] for c in calls],[1018,1044])
            saved=json.loads(files['checkpoint'].read_text())
            self.assertEqual(saved['predictions'][:1],old['predictions'])
            self.assertEqual(saved['raw_responses'][:1],old['raw_responses'])
            self.assertFalse(files['failure'].exists())
            self.assertEqual((root/'results/ecc_recovery/original.json').read_bytes(),original_failure)
            self.assertEqual(len(runner.read_jsonl(files['predictions'])),3)
            self.assertTrue(json.loads((root/'results/ecc_recovery/ledger.json').read_text())['complete'])
            for call in calls:self.assertNotIn('coder_1_bloom',call['records'][0])

    def test_new_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);f,rt,m,a,files,_=self.fixture(root)
            with patch.object(config,'verify',return_value=f),patch.object(runner,'ollama_chat',side_effect=runner.ValidationError('malformed')) as chat:
                with self.assertRaises(runner.ValidationError):recovery.run('test',rt,root,m,a)
                with self.assertRaisesRegex(ValueError,'new failure'):recovery.run('test',rt,root,m,a)
                self.assertEqual(chat.call_count,1)

    def test_unresolved_new_request_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);f,rt,m,a,_,_=self.fixture(root)
            with patch.object(config,'verify',return_value=f),patch.object(runner,'ollama_chat',side_effect=KeyboardInterrupt()) as chat:
                with self.assertRaises(KeyboardInterrupt):recovery.run('test',rt,root,m,a)
                with self.assertRaisesRegex(ValueError,'unresolved request'):recovery.run('test',rt,root,m,a)
                self.assertEqual(chat.call_count,1)

    def test_bad_gpu_and_changed_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);f,rt,m,a,_,_=self.fixture(root)
            runtime=json.loads(rt.read_text());runtime['gpus'][0]['uuid']='faulty';rt.write_text(json.dumps(runtime))
            with patch.object(config,'verify',return_value=f),patch.object(runner,'ollama_chat') as chat:
                with self.assertRaisesRegex(ValueError,'faulty GPU'):recovery.run('test',rt,root,m,a)
                self.assertFalse(chat.called)
                (root/'server.log').write_text('different error')
                with self.assertRaisesRegex(ValueError,'evidence changed'):recovery.verify(root,m,a)

    def test_real_amendment_is_read_only_and_launcher_is_tagalog_only(self):
        f=config.verify();files=config.paths(f,'tagalog');before={k:config.digest(files[k]) for k in ('failure','checkpoint')}
        _,_,_,saved=recovery.verify();self.assertEqual(saved,10)
        self.assertEqual(before,{k:config.digest(files[k]) for k in ('failure','checkpoint')})
        env={**os.environ,'DRY_RUN':'1','LANGUAGES':'english','SPLIT':'test_lockbox'}
        p=subprocess.run(['bash','scripts/submit_v611_tagalog_ecc_resume.sh'],cwd=config.BASE,env=env,text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)
        commands=[s for s in p.stdout.splitlines() if s.startswith('DRY:')]
        self.assertEqual(len(commands),1);self.assertIn('--exclude=gpu3001',commands[0]);self.assertNotIn('test_lockbox',commands[0])


if __name__=='__main__':unittest.main()
