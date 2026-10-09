"""Check matched samples and validate synthetic repeated hardware runs."""
import csv
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'scripts'))
import summarize_v5_gemma_gpu_comparison as scorer
import run_bloom_coding as runner

class HardwareTests(unittest.TestCase):
    def test_frozen_samples_and_no_label_leak(self):
        for language in scorer.LANGUAGES.values():
            records=runner.read_jsonl(BASE/'splits'/language/'dev_train_gemma_gpu_v5.jsonl')
            self.assertEqual(len(records),40)
            self.assertEqual(len({r['record_id'] for r in records}),40)
            for r in records:
                self.assertEqual(r['evaluation_subset'],'double_coded_consensus')
                prompted=runner.prompt_record(r)
                self.assertNotIn('sampling_label',prompted)
                self.assertNotIn('bloom_1',prompted)
                self.assertNotIn('bloom_2',prompted)

    def test_scores_repeats_and_rejects_wrong_gpu(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);out=base/'results';out.mkdir()
            for code,language in scorer.LANGUAGES.items():
                split=base/'splits'/language;split.mkdir(parents=True)
                records=[{'record_id':str(i),'sampling_label':'Denial'} for i in range(40)]
                (split/'dev_train_gemma_gpu_v5.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
                for gpu in ('l40s','a6000'):
                    for repeat in ('1','2'):
                        predictions=[dict(record_id=str(i),bloom_label='Denial',certain='Yes',flags={k:'No' for k in runner.REQUIRED_FLAGS},comments='') for i in range(40)]
                        if gpu=='l40s' and repeat=='2':predictions[0]['bloom_label']='Rejection'
                        runtime={'model_digest':'fixed','ollama_version':'fixed','template_sha256':'fixed','model_parameters_sha256':'fixed',
                                 'gpus':[{'name':'NVIDIA L40S' if gpu=='l40s' else 'NVIDIA RTX A6000'}]}
                        raw=[{'record_ids':[str(i)],'model':'gemma4:31b','attempt_count':1,
                              'effective_decoding_options':{'temperature':0,'seed':20261009+i,'num_ctx':32768},
                              'runtime_provenance':runtime} for i in range(40)]
                        prefix=f'dev_train_gemma_gpu_v5_gemma4_31b_bloom_v5_p005g-{code}-{gpu}-r{repeat}-full-b1-t0'
                        for suffix,rows in [('predictions',predictions),('raw_responses',raw)]:
                            (out/(prefix+'_'+suffix+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with patch.object(scorer,'BASE',base),patch.object(scorer,'RESULTS',out):
                self.assertEqual(scorer.main(),0)
                with (out/'repeatability.csv').open() as handle:
                    pairs=list(csv.DictReader(handle))
                self.assertEqual(len(pairs),30)
                within=[r for r in pairs if r['comparison']=='within_gpu' and r['left_gpu']=='l40s']
                self.assertTrue(all(r['exact_label_differences']=='1' for r in within))
                target=next(out.glob('*-en-a6000-r1-*_raw_responses.jsonl'))
                rows=runner.read_jsonl(target);rows[0]['runtime_provenance']['gpus'][0]['name']='NVIDIA L40S'
                target.write_text(''.join(json.dumps(r)+'\n' for r in rows))
                self.assertEqual(scorer.main(),1)
                self.assertTrue(any('Wrong GPU' in issue for issue in json.loads((out/'status.json').read_text())['issues']))

if __name__=='__main__':unittest.main()
