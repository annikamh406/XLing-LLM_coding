"""Full-training routing, strict settings, NFC, and checkpoint reuse without GPU inference."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import unicodedata
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'scripts'))
import run_bloom_coding as runner
import run_v5_dev_train_current as current
import check_v5_dev_train_current as checker
import coordinate_v5_dev_train as coordinator


def payload(records):
    return {'schema_version':'bloom_v5','predictions':[dict(record_id=r['record_id'],bloom_label='Denial',certain='Yes',comments='',flags={k:'No' for k in runner.REQUIRED_FLAGS}) for r in records]}


class CurrentTrainingTests(unittest.TestCase):
    def test_all_ten_routes_and_inherited_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);fake=root/'sbatch';log=root/'calls.jsonl'
            fake.write_text('#!'+sys.executable+'\nimport json,os,sys\nwith open(os.environ["FAKE_LOG"],"a") as f: f.write(json.dumps({"argv":sys.argv[1:],"env":{k:os.environ[k] for k in ["LIMIT","SPLIT","RUN_SETS","BATCH_SIZE","PROMPT_VERSION_OVERRIDE","RESULTS_DIR"]}})+"\\n")\n')
            fake.chmod(0o755)
            env={**os.environ,'PATH':str(root)+os.pathsep+os.environ['PATH'],'FAKE_LOG':str(log),
                 'DRY_RUN':'','LANGUAGES':'english german hebrew spanish tagalog','MODELS':'gemma4:31b qwen3.6:35b-a3b',
                 'LIMIT':'10','SPLIT':'test_lockbox','RUN_SETS':'masked'}
            result=subprocess.run(['bash','scripts/submit_v5_dev_train_current.sh'],cwd=BASE,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            jobs=[json.loads(line) for line in log.read_text().splitlines()];self.assertEqual(len(jobs),10)
            self.assertEqual(sum(j['env']['BATCH_SIZE']=='1' for j in jobs),5)
            self.assertEqual(sum(j['env']['BATCH_SIZE']=='5' for j in jobs),5)
            self.assertEqual(sum('nfc' in j['env']['PROMPT_VERSION_OVERRIDE'] for j in jobs),1)
            for j in jobs:
                self.assertEqual(j['env']['LIMIT'],'');self.assertEqual(j['env']['SPLIT'],'dev_train')
                self.assertEqual(j['env']['RUN_SETS'],'unmasked');self.assertEqual(j['env']['RESULTS_DIR'],'v5/results/dev_train_current')
                self.assertIn('--constraint=l40s',j['argv']);self.assertIn('--qos=copsy-l40s-gcondo',j['argv'])
                self.assertIn('--requeue',j['argv']);self.assertNotIn('--overwrite',j['argv'])
                self.assertNotIn('test_lockbox',' '.join(j['argv']))

    def test_freeze_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'input').write_text('{"record_id":"a"}\n')
            (root/'prompt').write_text('frozen')
            manifest={'split':'dev_train','files_sha256':{'prompt':hashlib.sha256(b'frozen').hexdigest()},'languages':{'english':{'input':'input','records':1}}}
            path=root/'freeze.json';path.write_text(json.dumps(manifest))
            with patch.object(checker,'verify_nfc'):
                checker.verify(root,path)
                (root/'prompt').write_text('changed')
                with self.assertRaisesRegex(ValueError,'file changed'):checker.verify(root,path)

    def exercise(self,language,model,batch):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);split=root/'splits'/language;split.mkdir(parents=True)
            records=[{'record_id':str(i),'target_utterance':'ש\u05c1\u05b8','coder_1_bloom':'Rejection'} for i in range(6)]
            source=split/'dev_train.jsonl';source.write_text(''.join(json.dumps(r)+'\n' for r in records));before=source.read_bytes()
            prompt=root/'prompt.md';prompt.write_text('original system prompt')
            freeze_path=root/'freeze.json';freeze_path.write_text('{}')
            runtime=root/'runtime.json';runtime.write_text(json.dumps({'ollama_version':'0.32.14','model_modelfile':'FROM weights',
                'gpus':[{'name':'NVIDIA L40S'}],'model_digest':'digest','template_sha256':'template',
                'model_parameters':'top_k 64','model_parameters_sha256':hashlib.sha256(b'top_k 64').hexdigest()}))
            frozen={'languages':{language:{'code':'he' if language=='hebrew' else 'en','prompt':'prompt.md','input':str(source)}},
                    'models':{model:{'batch_size':batch,'weights_blob_sha256':'weights'}},'ollama_version':'0.32.14',
                    'results_dir':'results','decoding_options':{'temperature':0.0,'seed':20261009,'top_p':None,'top_k':None,'min_p':None,'num_ctx':32768,'num_predict':8000}}
            tag=checker.tag(language,model,frozen)
            argv=['runner','--split','dev_train','--split-dir',str(split),'--results-dir',str(root/'results'),
                  '--prompt',str(prompt),'--prompt-version',tag,'--model',model,'--batch-size',str(batch),
                  '--temperature','0','--seed','20261009','--num-ctx','32768','--max-retries','0','--resume']
            calls=[]
            def chat(**kw):
                calls.append(kw)
                self.assertTrue(all('coder_1_bloom' not in r for r in kw['records']))
                expected=unicodedata.normalize('NFC',records[0]['target_utterance']) if language=='hebrew' and model.startswith('qwen') else records[0]['target_utterance']
                self.assertEqual(kw['records'][0]['target_utterance'],expected)
                self.assertEqual(kw['prompt'],'original system prompt')
                self.assertEqual(kw['temperature'],0)
                return payload(kw['records']),{'done':True}
            with patch.object(current,'BASE',root),patch.object(current,'MANIFEST',freeze_path),patch.object(current,'verify',return_value=frozen),\
                 patch.dict(os.environ,{'CODING_RUNTIME_PATH':str(runtime)}),patch.object(sys,'argv',argv),patch.object(runner,'ollama_chat',chat):
                self.assertEqual(current.main(),0)
                n=len(calls);self.assertEqual(n,(len(records)+batch-1)//batch)
                self.assertEqual(current.main(),0);self.assertEqual(len(calls),n)
                # Reject a limit, different seed, or validation split before inference.
                for option,value in [('--limit','1'),('--seed','1'),('--split','dev_check_1')]:
                    with patch.object(sys,'argv',argv+[option,value]):
                        with self.assertRaisesRegex(ValueError,'frozen full dev_train'):current.main()
                self.assertEqual(len(calls),n)
            self.assertEqual(source.read_bytes(),before)
            raw=runner.read_jsonl(next((root/'results').glob('*_raw_responses.jsonl')))
            self.assertTrue(all(r['dev_train_freeze_sha256']==hashlib.sha256(b'{}').hexdigest() for r in raw))
            self.assertTrue(all(r['input_normalization']==('NFC' if language=='hebrew' and model.startswith('qwen') else 'none') for r in raw))
            if model.startswith('qwen'):
                self.assertTrue(all(r['attempt_count']==1 for r in raw))
            if language=='hebrew' and model.startswith('qwen'):
                self.assertTrue(all('normalized_input_sha256' in r for r in raw))
            # Early completion checks must accept only exact baseline provenance.
            (root/'scripts').mkdir()
            (root/'scripts/run_bloom_coding.py').write_bytes(Path(runner.__file__).read_bytes())
            with patch.object(coordinator,'BASE',root):
                self.assertTrue(coordinator.complete(language,model,frozen))
                checkpoint=next((root/'results').glob('*_checkpoint.json'))
                state=json.loads(checkpoint.read_text())
                state['provenance']['decoding_options']['seed']=1
                checkpoint.write_text(json.dumps(state))
                with self.assertRaisesRegex(ValueError,'provenance differs'):
                    coordinator.complete(language,model,frozen)

    def test_hebrew_qwen_nfc_and_resume(self):self.exercise('hebrew','qwen3.6:35b-a3b',5)
    def test_gemma_unchanged_singletons_and_resume(self):self.exercise('english','gemma4:31b',1)
    def test_nonhebrew_qwen_unchanged_input(self):self.exercise('english','qwen3.6:35b-a3b',5)


if __name__=='__main__':unittest.main()
