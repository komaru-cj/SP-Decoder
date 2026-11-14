"""Finish all required evaluation stages after the frozen raw matrix completes."""
from pathlib import Path
import subprocess,sys,time
ROOT=Path(__file__).resolve().parents[2]
DIRECTORY=ROOT/'real_collision_experiment/paper_experiments'


if __name__=='__main__':
    log=Path('/tmp/boundary_priority4.log')
    print('Waiting for the full frozen raw matrix; no partial figures will be marked final.',flush=True)
    while not log.exists() or 'FROZEN_BOUNDARY_MATRIX_COMPLETE' not in log.read_text():
        time.sleep(15)
    stages=(('certified','replay_boundary_certified_candidates.py'),
            ('render','render_boundary_fairness.py'),('validate','validate_boundary_fairness.py'))
    for name,script in stages:
        print('START '+name,flush=True)
        with Path(f'/tmp/boundary_final_{name}.log').open('w') as output:
            subprocess.run([sys.executable,str(DIRECTORY/script)],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,check=True)
        print('COMPLETE '+name,flush=True)
    print('ALL_BOUNDARY_STAGES_COMPLETE',flush=True)
