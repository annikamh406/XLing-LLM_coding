import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'scripts'))
from validation_runtime_compat import compatible_runtime

class RuntimeCompatTests(unittest.TestCase):
    def test_order_only_accepted_values_and_signature_changes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            args=argparse.Namespace(split='dev_check_1',model='qwen3.6:35b-a3b',schema_version='bloom_v5',prompt_version='test',results_dir=root)
            old={'model_parameters':'temperature 1\ntop_k 20','model_digest':'weights','template_sha256':'template','ollama_version':'0.32.14','gpus':[{'name':'NVIDIA L40S'}]}
            old['model_parameters_sha256']=hashlib.sha256(old['model_parameters'].encode()).hexdigest()
            signature={k:v for k,v in old.items() if k not in ['model_parameters','gpus']}
            state={'provenance':{'runtime_signature':signature,'gpu_model':['NVIDIA L40S']},'raw_responses':[{'runtime_provenance':old}]}
            cp=root/'dev_check_1_qwen3.6_35b-a3b_bloom_v5_test_checkpoint.json';cp.write_text(json.dumps(state));original=cp.read_bytes()
            now=copy.deepcopy(old);now['model_parameters']='top_k 20\ntemperature 1'
            path=root/'runtime.json'
            def save():
                now['model_parameters_sha256']=hashlib.sha256(now['model_parameters'].encode()).hexdigest();path.write_text(json.dumps(now))
            save();result=json.loads(compatible_runtime(args,path).read_text())
            self.assertEqual(result['model_parameters'],old['model_parameters'])
            self.assertEqual(result['model_parameters_observed'],now['model_parameters'])
            self.assertEqual(cp.read_bytes(),original)
            self.assertEqual(json.loads(path.read_text()),now)
            now['model_parameters']='top_k 21\ntemperature 1';save()
            with self.assertRaisesRegex(ValueError,'values changed'):compatible_runtime(args,path)
            now['model_parameters']='top_k 20\ntemperature 1';now['model_digest']='different';save()
            with self.assertRaisesRegex(ValueError,'beyond parameter order'):compatible_runtime(args,path)
            now['model_digest']='weights';now['model_parameters']='top_k 20\ntop_k 20\ntemperature 1';save()
            with self.assertRaisesRegex(ValueError,'Ambiguous'):compatible_runtime(args,path)

    def test_downloaded_qwen_checkpoints_have_order_only_differences(self):
        source=BASE/'v5/results/dev_check_1'
        if not source.exists():self.skipTest('Local downloaded results unavailable')
        for code,job in [('en','7399524'),('de','7399526'),('es','7399530')]:
            cps=list(source.glob(f'*qwen*-{code}-*_checkpoint.json'))
            runtime=source/'logs'/f'runtime_{job}_restart-0.json'
            if not cps or not runtime.exists():continue
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);cp=root/cps[0].name;cp.write_bytes(cps[0].read_bytes())
                path=root/runtime.name;path.write_bytes(runtime.read_bytes())
                args=argparse.Namespace(split='dev_check_1',model='qwen3.6:35b-a3b',schema_version='bloom_v5',prompt_version=f'p005v1-{code}-full-b5-t0-s20261009',results_dir=root)
                result=json.loads(compatible_runtime(args,path).read_text())
                self.assertIn('parameter_order_equivalence',result)
                self.assertEqual(cp.read_bytes(),cps[0].read_bytes())
