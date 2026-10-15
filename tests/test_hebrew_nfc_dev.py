"""Test sample-wide NFC reliability accounting and resume without new inference."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'scripts'))
import run_hebrew_nfc_dev as dev
import run_bloom_coding as runner

class NFCDevTests(unittest.TestCase):
    def inputs(self,root):
        args=argparse.Namespace(results_dir=root/'results',resume=True,ollama_url='fake',timeout=1200,
            model='qwen3.6:35b-a3b',split='dev_train_promptpair_v5',prompt_version='test',prompt=Path('prompt'))
        records=[{'record_id':str(i),'target_utterance':'ʔo\u0304k\u0323el','sampling_label':'Denial'} for i in range(10)]
        runtime={'model_digest':'weights','ollama_version':'0.32.14','template_sha256':'template',
                 'model_parameters':'top_k 20\ntemperature 1','gpus':[{'name':'NVIDIA L40S'}]}
        return args,records,runtime

    def fake(self,fail_first,calls):
        def request(url,payload,directory,timeout):
            directory.mkdir(parents=True)
            rows=json.loads(payload['messages'][1]['content'].split('\n\n',1)[1]);ids=[r['record_id'] for r in rows]
            calls.append(ids)
            self.assertNotIn('sampling_label',payload['messages'][1]['content'])
            self.assertIn('ō',rows[0]['target_utterance'])
            options=payload['options'];self.assertEqual(options['temperature'],0)
            self.assertEqual(options['seed'],20261009+int(ids[0])//5)
            predictions=[dict(record_id=i,bloom_label='Denial',certain='Yes',comments='',flags={k:'No' for k in runner.REQUIRED_FLAGS}) for i in ids]
            result={'outcome':'incomplete_response' if fail_first and ids[0]=='0' else 'valid_complete_response',
                    'request_sha256':hashlib.sha256(json.dumps(payload).encode()).hexdigest()}
            (directory/'result.json').write_text(json.dumps(result))
            event={'done':True,'message':{'content':json.dumps({'schema_version':'bloom_v5','predictions':predictions})}}
            (directory/'events.jsonl').write_text(json.dumps(event)+'\n')
            return result
        return request

    def test_failure_does_not_skip_later_batches_or_publish_partial_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            args,records,runtime=self.inputs(Path(directory));calls=[]
            with patch.object(dev,'run_request',self.fake(True,calls)):
                self.assertEqual(dev.evaluate(records,'prompt',runtime,args,{'records':10}),1)
                self.assertEqual(len(calls),2)
                self.assertEqual(dev.evaluate(records,'prompt',runtime,args,{'records':10}),1)
                self.assertEqual(len(calls),2)
            status=json.loads((args.results_dir/'status.json').read_text())
            self.assertEqual(status['tested_batches'],2)
            self.assertEqual(status['successful_records'],5)
            self.assertEqual(len(status['failures']),1)
            self.assertFalse(list(args.results_dir.glob('*_predictions.jsonl')))

    def test_complete_output_and_frozen_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            args,records,runtime=self.inputs(Path(directory));calls=[]
            with patch.object(dev,'run_request',self.fake(False,calls)):
                self.assertEqual(dev.evaluate(records,'prompt',runtime,args,{'records':10}),0)
                self.assertEqual(dev.evaluate(records,'prompt',runtime,args,{'records':10}),0)
            self.assertEqual(len(calls),2)
            predictions=runner.read_jsonl(next(args.results_dir.glob('*_predictions.jsonl')))
            self.assertEqual(len(predictions),10)
            runtime['model_digest']='changed'
            with self.assertRaisesRegex(ValueError,'differs from this manifest'):
                dev.evaluate(records,'prompt',runtime,args,{'records':10})

if __name__=='__main__':unittest.main()
