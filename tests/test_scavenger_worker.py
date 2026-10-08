"""Check Slurm flags, GPU memory rejection, and batch-shell signal forwarding."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'

class WorkerTests(unittest.TestCase):
    def test_scavenger_submission_flags(self):
        result = subprocess.run(['bash', str(SCRIPTS/'submit_v5_multilingual_qwen_scavenger.sh')],
                                env={**os.environ,'DRY_RUN':'1'}, capture_output=True,text=True,check=True)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines),4)
        for line in lines:
            for flag in ('--partition=gpu-scavenger','--account=gpu-scavenger','--requeue',
                         '--signal=B:TERM@60','--resume','BATCH_SIZE=5',
                         'multilingual_production_pair_scavenger','--temperature 0'):
                self.assertIn(flag,line)

    def test_worker_memory_and_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'scripts').mkdir(); (root/'bin').mkdir()
            shutil.copy(SCRIPTS/'sbatch_v5.sh',root/'scripts')
            def executable(name, text, bin=True):
                p=root/('bin' if bin else 'scripts')/name
                p.write_text(text); p.chmod(0o755)
            executable('nvidia-smi', '#!/bin/sh\necho "$TEST_GPU_MEMORY"\n')
            executable('module','#!/bin/sh\nexit 0\n')
            executable('ollama', '#!'+sys.executable+'\nimport sys,time\nif sys.argv[1]=="serve": time.sleep(120)\nelse: print("NAME ID SIZE\\nqwen3.6:35b-a3b fake 1GB")\n')
            # macOS lacks util-linux setsid; emulate the Linux session primitive.
            executable('setsid', '#!'+sys.executable+'\nimport os,sys\nos.setsid(); os.execvp(sys.argv[1],sys.argv[1:])\n')
            executable('run_v5_language.sh', '#!'+sys.executable+'\nimport os,signal,time\nfrom pathlib import Path\ndef stop(*a):\n Path("stopped").write_text("terminated"); raise SystemExit(143)\nsignal.signal(signal.SIGTERM,stop)\nPath("ready").write_text(str(os.getpid()))\ntime.sleep(120)\n', bin=False)
            env={**os.environ,'PATH':str(root/'bin')+os.pathsep+os.environ['PATH'],
                 'SLURM_SUBMIT_DIR':str(root),'SLURM_JOB_ID':'123','CUDA_VISIBLE_DEVICES':'0',
                 'MIN_GPU_MEMORY_MIB':'45000','TEST_GPU_MEMORY':'24000'}
            command=['bash',str(root/'scripts/sbatch_v5.sh'),'qwen3.6:35b-a3b','german','engex','--resume']
            low=subprocess.run(command,env=env,capture_output=True,text=True)
            self.assertEqual(low.returncode,2); self.assertIn('24000 MiB',low.stderr)
            env['TEST_GPU_MEMORY']='48000'
            proc=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+10
                while not (root/'ready').exists() and time.monotonic()<deadline:
                    if proc.poll() is not None: self.fail(proc.communicate())
                    time.sleep(.02)
                self.assertTrue((root/'ready').exists())
                proc.terminate(); proc.communicate(timeout=5)
                deadline=time.monotonic()+3
                while not (root/'stopped').exists() and time.monotonic()<deadline: time.sleep(.02)
                self.assertEqual(proc.returncode,143)
                self.assertTrue((root/'stopped').exists(), 'Termination must reach coding process')
            finally:
                if proc.poll() is None: proc.kill(); proc.communicate()

if __name__=='__main__': unittest.main()
