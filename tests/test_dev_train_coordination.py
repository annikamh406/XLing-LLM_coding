"""Condo wins regardless of start order; use local fake workers, never Slurm."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'scripts'))
import coordinate_v5_dev_train as coordinator


class CoordinationTests(unittest.TestCase):
    def frozen(self):
        return {'results_dir':'results','languages':{'english':{'code':'en'}},'models':{'gemma4:31b':{'batch_size':1}}}

    def test_condo_first_or_finished_means_scavenger_never_loads(self):
        for state in ['RUNNING','CONFIGURING','COMPLETING','FINISHED']:
            with self.subTest(state=state),tempfile.TemporaryDirectory() as directory,patch.object(coordinator,'BASE',Path(directory)),patch.object(coordinator.subprocess,'Popen') as popen:
                status=coordinator.run_condition('scavenger','english','gemma4:31b','123',['fake'],self.frozen(),state_fn=lambda job:state)
                self.assertEqual(status,0);popen.assert_not_called()

    def test_scheduler_query_failure_prevents_scavenger_start(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(coordinator,'BASE',Path(directory)),patch.object(coordinator.subprocess,'Popen') as popen:
            def failure(job):raise RuntimeError('scheduler unavailable')
            with self.assertRaisesRegex(RuntimeError,'scheduler unavailable'):
                coordinator.run_condition('scavenger','english','gemma4:31b','123',['fake'],self.frozen(),state_fn=failure)
            popen.assert_not_called()

    def test_scavenger_stops_before_condo_worker_starts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);state=root/'state';state.write_text('PENDING')
            worker=root/'worker.py'
            worker.write_text('''import os,signal,sys,time
from pathlib import Path
root=Path(sys.argv[1]);role=sys.argv[2]
def log(event):
 with (root/'events').open('a') as f:f.write(event+'\\n')
try:fd=os.open(root/'active',os.O_CREAT|os.O_EXCL|os.O_WRONLY)
except FileExistsError:
 log('OVERLAP');raise SystemExit(3)
os.close(fd);log('start-'+role)
def stop(sig,frame):
 time.sleep(.15)
 (root/'active').unlink();log('stop-'+role);raise SystemExit(0)
signal.signal(signal.SIGTERM,stop)
if role=='condo':
 time.sleep(.1);(root/'active').unlink();log('finish-condo')
else:
 while True:time.sleep(.02)
''')
            driver=root/'driver.py';driver.write_text('''import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1]);import coordinate_v5_dev_train as c
root=Path(sys.argv[2]);role=sys.argv[3];c.BASE=root;c.complete=lambda *a:False
f={'results_dir':'results','languages':{'english':{'code':'en'}},'models':{'gemma4:31b':{'batch_size':1}}}
raise SystemExit(c.run_condition(role,'english','gemma4:31b','123',[sys.executable,str(root/'worker.py'),str(root),role],f,poll=.02,state_fn=lambda job:(root/'state').read_text()))
''')
            def start(role):return subprocess.Popen([sys.executable,str(driver),str(BASE/'scripts'),str(root),role],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            scav=start('scavenger');condo=None
            try:
                deadline=time.monotonic()+5
                while not (root/'events').exists() and time.monotonic()<deadline:time.sleep(.02)
                self.assertIn('start-scavenger',(root/'events').read_text())
                state.write_text('RUNNING');condo=start('condo')
                self.assertEqual(scav.wait(timeout=5),0,scav.stderr.read().decode())
                self.assertEqual(condo.wait(timeout=5),0,condo.stderr.read().decode())
                self.assertEqual((root/'events').read_text().splitlines(),['start-scavenger','stop-scavenger','start-condo','finish-condo'])
                self.assertFalse((root/'active').exists())
            finally:
                for child in [scav,condo]:
                    if child is not None:
                        if child.poll() is None:child.kill();child.wait()
                        child.stdout.close();child.stderr.close()

    def fake_commands(self,root):
        queue=root/'queue.json';queue.write_text(json.dumps([{'id':'7680704','name':'v5-train-gemma-en','state':'PENDING'}]))
        log=root/'calls.jsonl'
        program='''#!PYTHON
import json,os,sys
from pathlib import Path
root=Path(os.environ['FAKE_ROOT']);command=Path(sys.argv[0]).name
if command=='squeue':
 for j in json.loads((root/'queue.json').read_text()):print(j['id']+'|'+j['name']+'|'+j['state'])
else:
 with (root/'calls.jsonl').open('a') as f:f.write(json.dumps({'command':command,'args':sys.argv[1:],'paired':os.environ.get('PAIRED_CONDO_JOB_ID'),'split':os.environ.get('SPLIT')})+'\\n')
 if command=='scancel':
  if os.environ.get('RACE_RUNNING'):
   j=json.loads((root/'queue.json').read_text());j[0]['state']='RUNNING';(root/'queue.json').write_text(json.dumps(j))
  else:(root/'queue.json').write_text('[]')
 if command=='sbatch':print(10000+sum(1 for line in (root/'calls.jsonl').open()))
'''.replace('PYTHON',sys.executable)
        for command in ['squeue','sbatch','scancel']:
            p=root/command;p.write_text(program);p.chmod(0o755)
        return log,{**os.environ,'PATH':str(root)+os.pathsep+os.environ['PATH'],'FAKE_ROOT':str(root),
                    'LANGUAGES':'english','MODELS':'gemma4:31b','DRY_RUN':'','SPLIT':'test_lockbox','LIMIT':'10'}

    def test_replaces_only_pending_and_pairs_exact_condo_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);log,env=self.fake_commands(root)
            result=subprocess.run([sys.executable,'scripts/submit_v5_dev_train_dual.py','--replace-pending-condo'],cwd=BASE,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            calls=[json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([c['command'] for c in calls],['scancel','sbatch','sbatch'])
            self.assertEqual(calls[0]['args'],['--state=PENDING','7680704'])
            self.assertEqual(calls[2]['paired'],'10002')
            self.assertIn('--partition=l40s-gcondo',calls[1]['args']);self.assertIn('--account=gpu-scavenger',calls[2]['args'])
            self.assertTrue(all(c['split']=='dev_train' and '--constraint=l40s' in c['args'] for c in calls[1:]))

    def test_job_starting_during_cancel_is_left_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);log,env=self.fake_commands(root);env['RACE_RUNNING']='1'
            result=subprocess.run([sys.executable,'scripts/submit_v5_dev_train_dual.py','--replace-pending-condo'],cwd=BASE,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            calls=[json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([c['command'] for c in calls],['scancel'])
            self.assertIn('leaving condition alone',result.stdout)


if __name__=='__main__':unittest.main()
