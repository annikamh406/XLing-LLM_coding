"""Exercise actual process termination and recovery without a model/GPU."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FAKE = r'''
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv.pop(1))
import run_bloom_coding as runner
def fake(**kw):
    ids = [r['record_id'] for r in kw['records']]
    with open(os.environ['CALLS'], 'a') as f:
        f.write(json.dumps(ids) + '\n'); f.flush()
    if os.environ.get('PAUSE') == '1' and ids[0] == 'r5':
        time.sleep(120)
    predictions = [dict(record_id=i, bloom_label='Denial', certain='Yes',
                        flags={k:'No' for k in runner.REQUIRED_FLAGS}, comments='') for i in ids]
    return dict(schema_version='bloom_v5', predictions=predictions), {'response':'fake'}
runner.ollama_chat = fake
sys.exit(runner.main())
'''

class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.split = self.root / 'split'; self.split.mkdir()
        (self.split / 'dev_train.jsonl').write_text(''.join(json.dumps({'record_id':f'r{i}'})+'\n' for i in range(11)))
        self.prompt = self.root / 'prompt.md'; self.prompt.write_text('Frozen policy')
        self.results = self.root / 'results'
        self.calls = self.root / 'calls.jsonl'
        self.command = [sys.executable, '-c', FAKE, str(SCRIPTS), '--split','dev_train',
                        '--split-dir',str(self.split),'--prompt',str(self.prompt),
                        '--results-dir',str(self.results),'--model','fake','--batch-size','5','--resume']
        self.env = {**os.environ, 'CALLS':str(self.calls)}

    def tearDown(self):
        self.tmp.cleanup()

    def run_job(self):
        return subprocess.run(self.command, env=self.env, capture_output=True, text=True)

    def interrupt_after_first_batch(self):
        process = subprocess.Popen(self.command, env={**self.env,'PAUSE':'1'}, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if self.calls.exists() and len(self.calls.read_text().splitlines()) == 2:
                    return process
                if process.poll() is not None:
                    self.fail(process.communicate())
                time.sleep(.02)
            self.fail('Runner did not reach the second batch')
        except BaseException:
            process.kill(); process.communicate(); raise

    def test_interrupt_resume_and_finished_rerun(self):
        process = self.interrupt_after_first_batch()
        try:
            # Another writer must fail while the first owns the output lock.
            blocked = self.run_job()
            self.assertEqual(blocked.returncode, 2)
            self.assertIn('Another process', blocked.stderr)
        finally:
            process.terminate(); process.communicate(timeout=5)
        state = json.loads(next(self.results.glob('*_checkpoint.json')).read_text())
        self.assertEqual(len(state['predictions']), 5)
        self.assertFalse(list(self.results.glob('*_predictions.jsonl')))
        resumed = self.run_job(); self.assertEqual(resumed.returncode,0,resumed.stderr)
        calls = [json.loads(l) for l in self.calls.read_text().splitlines()]
        self.assertEqual(calls, [['r0','r1','r2','r3','r4'],['r5','r6','r7','r8','r9'],['r5','r6','r7','r8','r9'],['r10']])
        predictions = [json.loads(l) for l in next(self.results.glob('*_predictions.jsonl')).read_text().splitlines()]
        self.assertEqual([p['record_id'] for p in predictions], [f'r{i}' for i in range(11)])
        # Recover an interruption between publishing the two final files.
        next(self.results.glob('*_raw_responses.jsonl')).unlink()
        completed = self.run_job(); self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(len(self.calls.read_text().splitlines()),4)
        self.assertTrue(list(self.results.glob('*_raw_responses.jsonl')))

    def test_changed_prompt_and_corrupt_checkpoint_rejected(self):
        process = self.interrupt_after_first_batch()
        process.terminate(); process.communicate(timeout=5)
        self.prompt.write_text('Changed policy')
        changed = self.run_job(); self.assertEqual(changed.returncode,2)
        self.assertIn('does not match',changed.stderr)
        self.prompt.write_text('Frozen policy')
        cp = next(self.results.glob('*_checkpoint.json'))
        state = json.loads(cp.read_text()); state['raw_responses'][0]['record_ids'][0]='foreign'
        cp.write_text(json.dumps(state))
        corrupt = self.run_job(); self.assertNotEqual(corrupt.returncode,0)
        self.assertIn('Checkpoint batch IDs',corrupt.stderr)
        self.assertEqual(len(self.calls.read_text().splitlines()),2)

if __name__ == '__main__':
    unittest.main()
