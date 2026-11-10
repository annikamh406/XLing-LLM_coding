"""CPU checks for seed preservation, runtime matching, resume, and paired scoring."""
import collections
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'scripts'))
import run_bloom_coding as runner
import run_v65_diagnostic as diagnostic
import summarize_v65_diagnostic as report
import v65_diagnostic as config
from summarize_v5_nonrepetition import label, yes


def payload(rid, value='Denial'):
    return {'schema_version':'bloom_v6','predictions':[{'record_id':rid,'bloom_label':value,
        'certain':'Yes','comments':'test evidence','flags':{k:'No' for k in runner.FLAG_ORDER}}]}


class DiagnosticTests(unittest.TestCase):
    def test_scope_and_examples_match_approved_revision(self):
        frozen=config.verify()
        for c in frozen['languages'].values():
            text=(BASE/c['prompt']).read_text()
            self.assertNotIn('Apply this distinction after checking Nonpossession and Nonexistence.',text)
            self.assertIn('**Denial is a last-resort content category.**',text)
            self.assertIn('4. **Denial last:**',text)
            self.assertIn("No, there isn't any.",text)
            self.assertNotIn('Caregiver opens fridge, expected milk is gone.',text)
            self.assertIn('Do you like this?',text)
            self.assertIn('Which animals do you like?',text)
            self.assertNotIn("What foods don't you like?",text)
            self.assertIn("The transcript does not describe Dad reaching for a cookie.",text)
            self.assertIn('what is the rule about the sofa?',text)
            self.assertIn("it doesn't fit. Help me.",text)
            self.assertNotIn('jump on it, Daddy',text)

    def test_portable_v641_comparator_is_frozen_and_aligned(self):
        frozen=config.verify()
        for c in frozen['languages'].values():
            path=BASE/c['comparison_predictions']
            self.assertEqual(config.digest(path),frozen['files_sha256'][c['comparison_predictions']])
            self.assertEqual([r['record_id'] for r in runner.read_jsonl(path)],
                             [s['record_id'] for s in c['selection']])
            self.assertIn('6.5/baselines/',c['comparison_predictions'])

    def test_consolidated_rule_has_no_competing_old_requirements(self):
        frozen=config.verify()
        section=(BASE/'v6/6.5/rejection_denial_section.md').read_text().rstrip()
        paths=[BASE/c['prompt'] for c in frozen['languages'].values()]+[BASE/'v6/6.5/Bloom_coding_policy_v6.md']
        for path in paths:
            text=path.read_text()
            self.assertEqual(text.count(section),1)
            self.assertIn('If Rejection and Denial are both plausible, prefer `Rejection` and set `certain` to `No`.',text)
            for old in ['Five traps to avoid:','### Literal content versus live discourse move',
                '### Use the participants as your guide','nothing was offered, so not Rejection',
                'not `Rejection` (no directive is being resisted)']:
                self.assertNotIn(old,text)

    def test_inherits_exact_parent_sample_and_preserves_prompt_content(self):
        frozen=config.verify()
        parent=json.loads((BASE/'v6/dev_train_diagnostic_6_1_freeze.json').read_text())
        import runpy
        generator=runpy.run_path(str(BASE/'v6/6.5/make_prompts.py'))
        for lang,c in frozen['languages'].items():
            old=parent['languages'][lang]
            self.assertEqual(c['selection'],old['selection'])
            for key in ('input','human_reference','baseline'):
                self.assertEqual(c[key],old[key])
            self.assertEqual((BASE/c['prompt']).read_text(),generator['revised']((BASE/'v6/6.4'/Path(c['prompt']).name).read_text()))
            self.assertNotEqual(c['prompt_version'],old['prompt_version'])

    def test_parent_comparison_is_distinct_from_v5(self):
        rows=[dict(human_consensus=t,v5_label=old,v64_label=parent,v65_label=new,
                   v5_correct=old==t,v64_correct=parent==t,v65_correct=new==t,
                   v5_certain='Yes',v64_certain='Yes',v65_certain='Yes')
              for t,old,parent,new in [('rejection','denial','rejection','denial'),
                  ('denial','denial','rejection','denial')]]
        self.assertEqual((report.metrics(rows)['repaired'],report.metrics(rows)['regressed']),(0,0))
        prior=report.against_parent(rows)
        self.assertEqual((prior['repaired'],prior['regressed']),(1,1))
        self.assertEqual((prior['v64_correct'],prior['v65_correct']),(1,1))

    def test_paired_regressions_and_other_label_changes(self):
        rows=[dict(human_consensus=t,v5_label=b,v65_label=n,v5_correct=b==t,v65_correct=n==t,
                   v5_certain='Yes',v65_certain=certainty)
              for t,b,n,certainty in [('rejection','denial','rejection','Yes'),
                  ('rejection','rejection','denial','No'),('denial','denial','uncoded','No')]]
        m=report.metrics(rows)
        self.assertEqual((m['repaired'],m['regressed'],m['net_correct_change']),(1,2,-1))
        self.assertEqual((m['v5_R_to_D'],m['v65_R_to_D']),(1,1))
        self.assertEqual((m['v65_uncertain'],m['v65_uncoded']),(2,1))

    def test_actual_frozen_selection_and_controls(self):
        frozen=config.verify();counts=collections.Counter()
        for language,c in frozen['languages'].items():
            records=runner.read_jsonl(BASE/c['input']);refs=runner.read_jsonl(BASE/c['human_reference'])
            baseline=runner.read_jsonl(BASE/c['baseline'])
            original=json.loads((BASE/'v5/dev_train_current_freeze.json').read_text())
            original_records=runner.read_jsonl(BASE/original['languages'][language]['input'])
            indices={r['record_id']:i for i,r in enumerate(original_records)}
            originals={r['record_id']:r for r in original_records}
            utterances=set()
            for s,r,h,b in zip(c['selection'],records,refs,baseline):
                rid=r['record_id'];counts[s['group']]+=1
                self.assertEqual(r,originals[rid])
                self.assertEqual(s['original_effective_options']['seed'],20261009+indices[rid])
                truth=label(h['coder_1']['bloom_label'])
                self.assertEqual(truth,label(h['coder_2']['bloom_label']))
                self.assertFalse(any(yes((h[f'coder_{i}'].get('flags') or {}).get('repetition')) for i in (1,2)))
                if s['group']=='targeted':self.assertEqual((truth,label(b['bloom_label'])),('rejection','denial'))
                else:self.assertEqual(truth,label(b['bloom_label']))
                key=(r['transcript_id'],r.get('half'),r['line'])
                self.assertNotIn(key,utterances);utterances.add(key)
        self.assertEqual(dict(counts),{'targeted':40,'relevant_control':80,'broad_control':80})

    def fixture(self,root):
        options={'temperature':0.0,'seed':1000,'top_p':None,'top_k':None,'min_p':None,'num_ctx':32768,'num_predict':8000}
        parameters='top_k 64\ntop_p 0.95\ntemperature 1'
        runtime={'model_digest':'digest','ollama_version':'0.32.14','template_sha256':'template',
            'model_parameters':parameters,'model_parameters_sha256':hashlib.sha256(parameters.encode()).hexdigest(),
            'model_modelfile':'FROM frozen-weights','gpus':[{'name':'NVIDIA L40S'}]}
        signature={k:runtime[k] for k in ('model_digest','ollama_version','template_sha256')}
        signature['model_parameters']={'top_k':'64','top_p':'0.95','temperature':'1'}
        records=[{'record_id':str(i),'target_utterance':'no this mine',
            'coder_1_bloom':'Rejection','sampling_label':'secret','split':'dev_train',
            'transcript_id':'transcript','line':i,'context_before':[],'context_after':[]} for i in (1,19,45)]
        selection=[{'record_id':str(i),'original_batch_number':i,'original_effective_options':{**options,'seed':1000+i-1},
            'runtime_signature':signature,'group':'targeted','selection_reason':'test'} for i in (1,19,45)]
        runner.write_jsonl(root/'input.jsonl',records);(root/'prompt.md').write_text('frozen intervention')
        manifest=root/'freeze.json';manifest.write_text('{}')
        runtime_path=root/'runtime.json';runtime_path.write_text(json.dumps(runtime))
        c={'records':3,'input':'input.jsonl','prompt':'prompt.md','prompt_version':'p0065-en-diagnostic',
           'selection':selection,'counts':{'targeted':3},'baseline':'baseline.jsonl','parent_predictions':'parent.jsonl','comparison_predictions':'parent.jsonl','v62_predictions':'parent.jsonl','human_reference':'reference.jsonl'}
        f={'intervention':'6.5','model':'gemma4:31b','schema_version':'bloom_v6','batch_size':1,'max_retries':0,
           'weights_blob_sha256':'frozen-weights','timeout':1200,'decoding_options':options,
           'results_dir':'results','languages':{'english':c},'files_sha256':{'input.jsonl':config.digest(root/'input.jsonl')}}
        baseline=[{**payload(r['record_id'])['predictions'][0]} for r in records]
        refs=[{'record_id':r['record_id'],'coder_1':{'bloom_label':'Rejection'},'coder_2':{'bloom_label':'Rejection'}} for r in records]
        runner.write_jsonl(root/'baseline.jsonl',baseline);runner.write_jsonl(root/'parent.jsonl',baseline);runner.write_jsonl(root/'reference.jsonl',refs)
        return f,runtime_path,manifest

    def test_resume_preserves_original_seeds_and_no_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);f,rt,m=self.fixture(root);calls=[]
            def chat(**kw):
                calls.append(kw)
                if len(calls)==2:raise KeyboardInterrupt()
                rid=kw['records'][0]['record_id']
                return payload(rid,'Rejection'),{'done':True}
            with patch.object(config,'verify',return_value=f),patch.object(runner,'ollama_chat',chat):
                with self.assertRaises(KeyboardInterrupt):diagnostic.run('english','test',rt,root,m)
                partial=report.calculate(root,m)
                self.assertEqual(partial['languages']['english']['saved_records'],1)
                self.assertEqual(partial['rows'],[])
                self.assertNotIn('groups',partial['languages']['english'])
                diagnostic.run('english','test',rt,root,m)
                count=len(calls);diagnostic.run('english','test',rt,root,m)
                self.assertEqual(len(calls),count)
                data=report.calculate(root,m)
                rendered=report.render(data)
            self.assertEqual([c['seed'] for c in calls],[1000,1018,1018,1044])
            for c in calls:
                self.assertEqual(c['temperature'],0);self.assertEqual(c['num_ctx'],32768)
                self.assertNotIn('coder_1_bloom',c['records'][0]);self.assertNotIn('sampling_label',c['records'][0])
                self.assertNotIn('split',c['records'][0])
            self.assertTrue(data['all_complete'])
            self.assertEqual(data['languages']['english']['groups']['targeted']['repaired'],3)
            self.assertEqual(data['pooled_against_v62']['targeted']['repaired'],3)
            self.assertEqual(data['pooled_against_v64']['targeted']['repaired'],3)
            self.assertIn('Changes from 6.2 to 6.5',rendered)
            self.assertIn('Changes from 6.4 to 6.5',rendered)

    def test_genuine_failure_blocks_unamended_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);f,rt,m=self.fixture(root)
            with patch.object(config,'verify',return_value=f),patch.object(runner,'ollama_chat',side_effect=runner.ValidationError('bad output')) as chat:
                with self.assertRaises(runner.ValidationError):diagnostic.run('english','test',rt,root,m)
                with self.assertRaisesRegex(ValueError,'genuine failure'):diagnostic.run('english','test',rt,root,m)
                self.assertEqual(chat.call_count,1)

    def test_runtime_and_checkpoint_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);f,rt,m=self.fixture(root);c=f['languages']['english'];runtime=json.loads(rt.read_text())
            # Parameter ordering alone is harmless, values and template are not.
            runtime['model_parameters']='temperature 1\ntop_p 0.95\ntop_k 64'
            runtime['model_parameters_sha256']=hashlib.sha256(runtime['model_parameters'].encode()).hexdigest()
            config.check_runtime(runtime,f,c)
            for field,value in [('template_sha256','changed'),('ollama_version','different'),('gpus',[{'name':'NVIDIA A6000'}])]:
                with self.assertRaises(ValueError):config.check_runtime({**runtime,field:value},f,c)
            with patch.object(config,'verify',return_value=f),patch.object(runner,'ollama_chat',side_effect=lambda **kw:(payload(kw['records'][0]['record_id']),{})):
                diagnostic.run('english','test',rt,root,m)
                p=config.paths(f,'english',root)['checkpoint'];state=json.loads(p.read_text())
                state['raw_responses'][1]['effective_decoding_options']['seed']=1001;p.write_text(json.dumps(state))
                with self.assertRaisesRegex(ValueError,'seed/settings'):diagnostic.run('english','test',rt,root,m)

    def test_launcher_is_only_five_frozen_gemma_jobs(self):
        env={**os.environ,'DRY_RUN':'1','LIMIT':'1','SPLIT':'test_lockbox','BATCH_SIZE':'5'}
        env.pop('LANGUAGES',None)
        result=subprocess.run(['bash','scripts/submit_v65_diagnostic.sh'],cwd=BASE,env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        commands=[s for s in result.stdout.splitlines() if s.startswith('DRY:')]
        self.assertEqual(len(commands),5)
        self.assertTrue(all('--exclude=gpu3001' in command for command in commands))
        self.assertNotIn('test_lockbox',' '.join(commands));self.assertNotIn('run_v5',' '.join(commands))


if __name__=='__main__':unittest.main()
