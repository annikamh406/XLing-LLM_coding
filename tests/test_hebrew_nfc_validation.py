"""Exercise all 240 batches of the NFC validation wrapper with a mocked model."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'scripts'))
import run_bloom_coding as runner
import run_v5_validation_recovery as recovery
import run_hebrew_nfc_validation as nfc
import check_hebrew_nfc_validation as checker

class NFCValidationTests(unittest.TestCase):
    def test_full_split_nfc_metadata_resume_and_no_original_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);split=root/'splits/hebrew';split.mkdir(parents=True)
            records=[{'record_id':f'heb_{i:06d}','target_utterance':'ʔo\u0304k\u0323el','sampling_label':'Denial'} for i in range(1,1200)]
            input_path=split/'dev_check_1.jsonl';runner.write_jsonl(input_path,records);source=input_path.read_bytes()
            prompt=root/'prompt.md';prompt.write_text('Frozen English-example prompt')
            amendment=root/'amendment.json';amendment.write_text('{}');amendment_hash=hashlib.sha256(amendment.read_bytes()).hexdigest()
            original=root/'v5/results/dev_check_1/hebrew-failure.json';original.parent.mkdir(parents=True);original.write_text('Original failure remains archived')
            runtime={'model_digest':'weights','ollama_version':'0.32.14','template_sha256':'template',
                'model_parameters':'temperature 1\ntop_k 20','model_parameters_sha256':'hash',
                'model_modelfile':'FROM weights','gpus':[{'name':'NVIDIA L40S'}]}
            runtime_path=root/'runtime.json';runtime_path.write_text(json.dumps(runtime))
            argv=['runner','--split','dev_check_1','--split-dir',str(split),'--results-dir',str(root/'nfc'),
              '--prompt',str(prompt),'--prompt-version',nfc.TAG,'--model','qwen3.6:35b-a3b','--batch-size','5',
              '--temperature','0','--seed','20261009','--num-ctx','32768','--max-retries','0','--resume']
            calls=[]
            def chat(**kw):
                calls.append(kw['records'])
                for r in kw['records']:
                    self.assertEqual(r['target_utterance'],'ʔōḳel');self.assertNotIn('sampling_label',r)
                preds=[dict(record_id=r['record_id'],bloom_label='Denial',certain='Yes',comments='',
                        flags={k:'No' for k in runner.REQUIRED_FLAGS}) for r in kw['records']]
                payload={'schema_version':'bloom_v5','predictions':preds}
                return payload,{'done':True,'message':{'content':json.dumps(payload)}}
            with patch.object(nfc,'BASE',root),patch.object(nfc,'AMENDMENT',amendment),\
                 patch.object(nfc,'verify_nfc',return_value={'prompt':'prompt.md','input':'splits/hebrew/dev_check_1.jsonl','results_dir':'nfc'}),\
                 patch.object(sys,'argv',argv),patch.dict(os.environ,{'CODING_RUNTIME_PATH':str(runtime_path)}),\
                 patch.object(recovery,'verify',return_value={}),patch.object(recovery,'decorate',recovery.decorate),\
                 patch.object(runner,'prompt_record',runner.prompt_record),patch.object(runner,'ollama_chat',chat),\
                 patch.object(runner,'atomic_write',runner.atomic_write),patch.object(runner,'write_jsonl',runner.write_jsonl):
                self.assertEqual(nfc.main(),0)
            self.assertEqual(len(calls),240)
            # A second process-like invocation must skip all successful batches.
            with patch.object(nfc,'BASE',root),patch.object(nfc,'AMENDMENT',amendment),\
                 patch.object(nfc,'verify_nfc',return_value={'prompt':'prompt.md','input':'splits/hebrew/dev_check_1.jsonl','results_dir':'nfc'}),\
                 patch.object(sys,'argv',argv),patch.dict(os.environ,{'CODING_RUNTIME_PATH':str(runtime_path)}),\
                 patch.object(recovery,'verify',return_value={}),patch.object(recovery,'decorate',recovery.decorate),\
                 patch.object(runner,'prompt_record',runner.prompt_record),patch.object(runner,'ollama_chat',chat),\
                 patch.object(runner,'atomic_write',runner.atomic_write),patch.object(runner,'write_jsonl',runner.write_jsonl):
                self.assertEqual(nfc.main(),0)
            self.assertEqual(len(calls),240)
            self.assertEqual(input_path.read_bytes(),source)
            self.assertEqual(original.read_text(),'Original failure remains archived')
            raw=runner.read_jsonl(next((root/'nfc').glob('*_raw_responses.jsonl')))
            self.assertEqual(len(raw),240)
            self.assertEqual(raw[-1]['record_ids'],[f'heb_{i:06d}' for i in range(1196,1200)])
            self.assertTrue(all(b['input_normalization']=='NFC' and b['preprocessing_amendment_sha256']==amendment_hash for b in raw))
            manifest={'results_dir':'nfc','ollama_version':'0.32.14',
                'files_sha256':{'prompt.md':hashlib.sha256(prompt.read_bytes()).hexdigest(),
                               'scripts/run_bloom_coding.py':hashlib.sha256(Path(runner.__file__).read_bytes()).hexdigest()},
                'decoding_options':{'temperature':0.0,'seed':20261009,'num_ctx':32768,'num_predict':8000,'top_p':None,'top_k':None,'min_p':None},
                'languages':{'hebrew':{'input':'splits/hebrew/dev_check_1.jsonl','prompt':'prompt.md'}},
                'models':{'qwen3.6:35b-a3b':{'batch_size':5,'weights_blob_sha256':'weights'}}}
            self.assertEqual(checker.check(root,manifest,amendment_hash)['issues'],[])
            raw[0]['normalized_input_sha256']='wrong';runner.write_jsonl(next((root/'nfc').glob('*_raw_responses.jsonl')),raw)
            self.assertIn('Normalized input hash',checker.check(root,manifest,amendment_hash)['issues'][0])

    def test_launcher_forces_hebrew_full_split_despite_stale_environment(self):
        result=subprocess.run(['bash','scripts/submit_hebrew_nfc_validation.sh'],cwd=BASE,
            env={**os.environ,'DRY_RUN':'1','LIMIT':'10','SPLIT':'test_lockbox','RUN_SETS':'masked'},capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        lines=[l for l in result.stdout.splitlines() if l.startswith('DRY:')]
        self.assertEqual(len(lines),1)
        self.assertIn('qwen3.6:35b-a3b hebrew engex',lines[0])
        self.assertIn('--time=4-00:00:00',lines[0])
        self.assertIn('dev_check_1_hebrew_nfc',lines[0])
        self.assertNotIn('test_lockbox',lines[0])

if __name__=='__main__':unittest.main()
