"""Exercise frozen validation routing, provenance and complete-output checks."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'scripts'))
import capture_coding_runtime as capture
import check_v5_validation_freeze as freeze
import check_v5_dev_check_1_results as results
import run_bloom_coding as runner

class ValidationTests(unittest.TestCase):
    def test_manifest_tampering_and_launcher_full_split(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); artifact=root/'prompt'; artifact.write_text('frozen')
            manifest=root/'freeze.json'
            manifest.write_text(json.dumps({'split':'dev_check_1','files_sha256':{'prompt':hashlib.sha256(b'frozen').hexdigest()}}))
            freeze.verify(root,manifest)
            artifact.write_text('changed')
            with self.assertRaisesRegex(ValueError,'Frozen file changed'):
                freeze.verify(root,manifest)
        completed=subprocess.run(['bash','scripts/submit_v5_dev_check_1.sh'],cwd=BASE,
            env={**os.environ,'DRY_RUN':'1','LIMIT':'10','SPLIT':'test_lockbox','RUN_SETS':'masked',
                 'LANGUAGES':'english german hebrew spanish tagalog','MODELS':'gemma4:31b qwen3.6:35b-a3b'},
            capture_output=True,text=True)
        self.assertEqual(completed.returncode,0,completed.stderr)
        jobs=[line.replace('\\,',',') for line in completed.stdout.splitlines() if line.startswith('DRY:')]
        self.assertEqual(len(jobs),10)
        for job in jobs:
            self.assertIn('--partition=l40s-gcondo',job)
            self.assertIn('--qos=copsy-l40s-gcondo',job)
            self.assertIn('LIMIT=,SPLIT=dev_check_1,RUN_SETS=unmasked',job)
            self.assertIn('--max-retries 0 --resume',job)
            self.assertNotIn('test_lockbox',job)
        self.assertEqual(sum('BATCH_SIZE=1,' in j for j in jobs),5)
        self.assertEqual(sum('BATCH_SIZE=5,' in j for j in jobs),5)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);log=root/'calls.jsonl';fake=root/'sbatch'
            fake.write_text('#!'+sys.executable+'\nimport os,json\nfrom pathlib import Path\n'
                            'with Path(os.environ["FAKE_SUBMIT_LOG"]).open("a") as f:\n'
                            ' f.write(json.dumps({k:os.environ[k] for k in ["LIMIT","SPLIT","RUN_SETS","BATCH_SIZE","PROMPT_OVERRIDE"]})+"\\n")\n')
            fake.chmod(0o755)
            completed=subprocess.run(['bash','scripts/submit_v5_dev_check_1.sh'],cwd=BASE,
                env={**os.environ,'PATH':str(root)+os.pathsep+os.environ['PATH'],'DRY_RUN':'',
                     'FAKE_SUBMIT_LOG':str(log),'LIMIT':'10','SPLIT':'test_lockbox','RUN_SETS':'masked',
                     'LANGUAGES':'english','MODELS':'gemma4:31b qwen3.6:35b-a3b'},capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            captured=[json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(len(captured),2)
            for env in captured:
                self.assertEqual(env['LIMIT'],'')
                self.assertEqual(env['SPLIT'],'dev_check_1')
                self.assertEqual(env['RUN_SETS'],'unmasked')

    def test_complete_results_and_sampled_retry_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'results';out.mkdir();sample=[{'record_id':str(i)} for i in range(3)]
            (root/'input.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in sample))
            opts={'temperature':0.0,'seed':20261009,'top_p':None,'top_k':None,'min_p':None,'num_ctx':32768,'num_predict':8000}
            manifest={'results_dir':'results','ollama_version':'0.32.14','decoding_options':opts,
                'files_sha256':{'prompt':'prompt-hash','scripts/run_bloom_coding.py':'runner-hash'},
                'languages':{'english':{'code':'en','input':'input.jsonl','prompt':'prompt'}},
                'models':{'qwen3.6:35b-a3b':{'batch_size':5,'weights_blob_sha256':'weights'}}}
            stem='dev_check_1_qwen3.6_35b-a3b_bloom_v5_p005v1-en-full-b5-t0-s20261009'
            predictions=[dict(record_id=r['record_id'],bloom_label='Denial',certain='Yes',comments='',
                              flags={k:'No' for k in runner.REQUIRED_FLAGS}) for r in sample]
            runtime={'gpus':[{'name':'NVIDIA L40S'}],'ollama_version':'0.32.14','model_modelfile':'FROM weights',
                     'model_digest':'digest','template_sha256':'template','model_parameters':'temperature 1\ntop_k 64'}
            raw=[{'record_ids':[r['record_id'] for r in sample],'effective_decoding_options':dict(opts),'attempt_count':1,
                  'model':'qwen3.6:35b-a3b','prompt_version':'p005v1-en-full-b5-t0-s20261009','runtime_provenance':runtime}]
            provenance={'prompt_sha256':'prompt-hash','runner_sha256':'runner-hash','batch_size':5,'max_retries':0,
                        'records_sha256':hashlib.sha256(json.dumps(sample,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
            for suffix,rows in [('predictions',predictions),('raw_responses',raw)]:
                (out/(stem+'_'+suffix+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
            (out/(stem+'_checkpoint.json')).write_text(json.dumps({'provenance':provenance}))
            self.assertEqual(results.check(root,manifest)['issues'],[])
            raw[0]['attempt_count']=2;raw[0]['effective_decoding_options']['temperature']=0.2
            (out/(stem+'_raw_responses.jsonl')).write_text(json.dumps(raw[0])+'\n')
            self.assertIn('Decoding/retry',results.check(root,manifest)['issues'][0])
            (out/(stem+'_predictions.jsonl')).unlink()
            self.assertEqual(results.check(root,manifest)['validated_runs'],0)

    def test_runtime_saves_parameters_and_rejects_changed_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'runtime.json'
            responses={'version':{'version':'0.32.14'},'tags':{'models':[{'name':'gemma4:31b','digest':'digest'}]},
                       'show':{'parameters':'top_k 64\ntemperature 1','modelfile':'FROM /models/sha256-weights','template':'template'}}
            def request(req,timeout):
                return io.BytesIO(json.dumps(responses[req.full_url.rsplit('/',1)[1]]).encode())
            argv=['capture','--model','gemma4:31b','--ollama-url','http://localhost/api/chat','--output',str(output)]
            with patch.object(sys,'argv',argv),patch.dict(os.environ,{'CUDA_VISIBLE_DEVICES':'0','EXPECTED_OLLAMA_VERSION':'0.32.14','EXPECTED_MODEL_BLOB_SHA256':'weights'}),\
                 patch.object(capture.urllib.request,'urlopen',request),\
                 patch.object(capture.subprocess,'check_output',return_value='NVIDIA L40S, uuid, 575.57.08, 46068\n'):
                capture.main()
                runtime=json.loads(output.read_text())
                self.assertEqual(runtime['model_parameters'],responses['show']['parameters'])
                self.assertEqual(runtime['model_parameters_sha256'],hashlib.sha256(runtime['model_parameters'].encode()).hexdigest())
                responses['show']['modelfile']='FROM changed-weights'
                # Require the full frozen hash, not a generic substring.
                with patch.dict(os.environ,{'EXPECTED_MODEL_BLOB_SHA256':'absent'}):
                    with self.assertRaisesRegex(RuntimeError,'Model weights differ'):
                        capture.main()

if __name__=='__main__':unittest.main()
