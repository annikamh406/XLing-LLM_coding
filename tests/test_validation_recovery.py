"""Recovery leaves the frozen runner/checkpoints intact and never samples."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'scripts'))
import run_bloom_coding as runner
import run_v5_validation_recovery as recovery
import check_v5_recovered_results as checker


def payload(ids):
    return {'schema_version':'bloom_v5','predictions':[dict(record_id=i,bloom_label='Denial',certain='Yes',comments='',
         flags={k:'No' for k in runner.REQUIRED_FLAGS}) for i in ids]}

class RecoveryTests(unittest.TestCase):
    def setup_call(self,root):
        args=argparse.Namespace(split='dev_check_1',model='qwen3.6:35b-a3b',schema_version='bloom_v5',
          prompt_version='test',results_dir=root,seed=20261009)
        call=dict(records=[{'record_id':'a'},{'record_id':'b'}],prompt='frozen',seed=20261009,
          temperature=0.0,top_p=None,top_k=None,min_p=None,num_ctx=32768,num_predict=8000,
          timeout=1200,model=args.model,output_schema={},url='fake',validation_feedback=None)
        return args,call

    def test_duplicate_repair_bounded_and_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,call=self.setup_call(root);calls=[]
            def chat(**kw):
                calls.append(kw)
                return payload(['a','b'] if kw['validation_feedback'] else ['a','a']),{'done':True}
            wrapped=recovery.Recovery(args,chat)
            answer,raw=wrapped(**call)
            self.assertEqual([p['record_id'] for p in answer['predictions']],['a','b'])
            self.assertEqual(len(calls),3)
            self.assertTrue(all(c['temperature']==0 and c['seed']==20261009 and c['num_predict']==8000 for c in calls))
            self.assertIsNone(calls[1]['validation_feedback'])
            self.assertIn('a, b',calls[2]['validation_feedback'])
            wrapped(**call);self.assertEqual(len(calls),3)
            self.assertEqual(len(raw['validation_recovery']['attempts']),3)
            logs=list(root.rglob('batch-1.json'));state=json.loads(logs[0].read_text())
            self.assertEqual([a['status'] for a in state['attempts']],['failed','failed','success'])

    def test_historical_empty_response_budget_and_failure_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,call=self.setup_call(root);calls=[]
            wrapped=recovery.Recovery(args,lambda **kw:None)
            historical=root/f'{wrapped.prefix}_failed_batch-1.json'
            original={'model':args.model,'prompt_version':args.prompt_version,'record_ids':['a','b'],
                      'validation_error':'empty content','parsed_payload':None}
            historical.write_text(json.dumps(original))
            def chat(**kw):
                calls.append(kw)
                if kw['num_predict']==8000:raise runner.RetryableBatchError('empty content')
                return payload(['a','b']),{'done':True}
            wrapped.chat=chat;wrapped(**call)
            self.assertEqual(len(calls),2)
            self.assertEqual(calls[-1]['num_predict'],16000)
            self.assertEqual(calls[-1]['timeout'],2400)
            self.assertEqual(json.loads(historical.read_text()),original)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);args,call=self.setup_call(root);calls=[]
            def fail(**kw):
                calls.append(kw);raise runner.RetryableBatchError('timeout')
            wrapped=recovery.Recovery(args,fail)
            with self.assertRaises(recovery.RecoveryExhausted):wrapped(**call)
            with self.assertRaises(recovery.RecoveryExhausted):wrapped(**call)
            self.assertEqual(len(calls),3)

    def test_original_checkpoint_resumes_without_repeating_successes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);split=root/'split';split.mkdir();out=root/'results'
            records=[{'record_id':str(i)} for i in range(10)]
            (split/'dev_check_1.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
            prompt=root/'prompt';prompt.write_text('frozen')
            argv=['runner','--split','dev_check_1','--split-dir',str(split),'--results-dir',str(out),
              '--prompt',str(prompt),'--prompt-version','test','--model','qwen3.6:35b-a3b','--batch-size','5',
              '--temperature','0','--seed','20261009','--num-ctx','32768','--max-retries','0','--resume']
            calls=[]
            def original(**kw):
                ids=[r['record_id'] for r in kw['records']];calls.append(ids)
                if ids[0]=='5':return payload(['5']*5),{'done':True}
                return payload(ids),{'done':True}
            with patch.object(sys,'argv',argv),patch.object(runner,'ollama_chat',original):
                with self.assertRaises(runner.ValidationError):runner.main()
            checkpoint=next(out.glob('*_checkpoint.json'));before=json.loads(checkpoint.read_text())
            failure=next(out.glob('*failed_batch*.json'));original_failure=failure.read_bytes()
            calls=[]
            def fixed(**kw):
                ids=[r['record_id'] for r in kw['records']];calls.append(ids)
                return payload(ids if kw['validation_feedback'] else ['5']*5),{'done':True}
            # Restore every patched runner hook after exercising the real main.
            with patch.object(sys,'argv',argv),patch.object(recovery,'verify',return_value={}),\
                 patch.object(runner,'ollama_chat',fixed),patch.object(runner,'atomic_write',runner.atomic_write),\
                 patch.object(runner,'write_jsonl',runner.write_jsonl):
                self.assertEqual(recovery.main(),0)
            after=json.loads(checkpoint.read_text())
            self.assertEqual(before['provenance'],after['provenance'])
            self.assertEqual(before['predictions'],after['predictions'][:5])
            self.assertTrue(all(ids[0]=='5' for ids in calls))
            self.assertEqual(failure.read_bytes(),original_failure)
            self.assertEqual(after['raw_responses'][1]['attempt_count'],3)
            with patch.object(sys,'argv',argv),patch.object(recovery,'verify',return_value={}),\
                 patch.object(runner,'ollama_chat',fixed),patch.object(runner,'atomic_write',runner.atomic_write),\
                 patch.object(runner,'write_jsonl',runner.write_jsonl):
                self.assertEqual(recovery.main(),0)
            self.assertEqual(len(calls),2)

    def test_amended_checker_accepts_budget_repair_rejects_sampling(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'results';out.mkdir();args,call=self.setup_call(out)
            args.prompt_version='p005v1-en-full-b5-t0-s20261009'
            def chat(**kw):
                if kw['num_predict']==8000:raise runner.RetryableBatchError('empty')
                return payload(['a','b']),{'done':True}
            wrapped=recovery.Recovery(args,chat);answer,raw=wrapped(**call)
            runtime={'gpus':[{'name':'NVIDIA L40S'}],'ollama_version':'0.32.14',
                     'model_modelfile':'FROM weights','model_digest':'digest','template_sha256':'template','model_parameters':'top_k 64'}
            rows=recovery.decorate([{'record_ids':['a','b'],'model':args.model,'prompt_version':args.prompt_version,
                                    'runtime_provenance':runtime,'raw_response':raw}])
            for suffix,items in [('predictions',answer['predictions']),('raw_responses',rows)]:
                runner.write_jsonl(out/(wrapped.prefix+'_'+suffix+'.jsonl'),items)
            sample=call['records'];runner.write_jsonl(root/'input.jsonl',sample)
            provenance={'prompt_sha256':'prompt','runner_sha256':'runner','batch_size':5,'max_retries':0,
                        'records_sha256':hashlib.sha256(json.dumps(sample,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
            (out/(wrapped.prefix+'_checkpoint.json')).write_text(json.dumps({'provenance':provenance}))
            options={k:call[k] for k in ('temperature','seed','top_p','top_k','min_p','num_ctx','num_predict')}
            manifest={'results_dir':'results','ollama_version':'0.32.14','decoding_options':options,
                'files_sha256':{'prompt':'prompt','scripts/run_bloom_coding.py':'runner'},
                'languages':{'english':{'code':'en','input':'input.jsonl','prompt':'prompt'}},
                'models':{args.model:{'batch_size':5,'weights_blob_sha256':'weights'}}}
            status=checker.check(root,manifest)
            self.assertEqual(status['issues'],[])
            self.assertEqual(status['runs'][0]['recovered_record_ids'],['a','b'])
            rows[0]['raw_response']['validation_recovery']['attempts'][2]['effective_decoding_options']['temperature']=0.4
            runner.write_jsonl(out/(wrapped.prefix+'_raw_responses.jsonl'),rows)
            self.assertIn('unapproved decoding',checker.check(root,manifest)['issues'][0])

if __name__=='__main__':unittest.main()
