#!/usr/bin/env python3
"""Finish serial benchmarks and publication after all independent decoding jobs close."""
from pathlib import Path
import sys,json,time,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from real_collision_experiment.paper_experiments import run_compact_revision_20261106 as c
OUT=c.OUT

last=None
while True:
    counts={};complete=True
    for stage in ('pilot','main','blind','blind_calibration'):
        m=json.loads((OUT/f'manifest_{stage}.json').read_text());folder='blind_jobs' if stage.startswith('blind') else 'jobs'
        paths=[OUT/folder/(c.key(s)+'.json') for s in m['specs']];n=sum(p.exists() for p in paths)
        counts[stage]=[n,len(paths)]
        if n!=len(paths):complete=False
    if counts!=last:print('WAITING',counts,flush=True);last=counts
    if complete:
        # A file name may become visible a moment before a write is complete.
        try:
            for stage in ('pilot','main','blind','blind_calibration'):
                m=json.loads((OUT/f'manifest_{stage}.json').read_text());folder='blind_jobs' if stage.startswith('blind') else 'jobs'
                for s in m['specs']:assert json.loads((OUT/folder/(c.key(s)+'.json')).read_text())['spec']==s
            break
        except (ValueError,AssertionError):pass
    time.sleep(15)
time.sleep(5)
scripts=Path(__file__).parent
if not (OUT/'timing.json').exists():
    print('STARTING SERIAL LATENCY',flush=True)
    subprocess.run([sys.executable,str(scripts/'run_compact_aux_20261106.py'),'timing'],check=True)
print('RENDERING FINAL FIGURES',flush=True)
subprocess.run([sys.executable,str(scripts/'render_compact_revision_20261106.py')],check=True)
print('VALIDATING AND PACKAGING',flush=True)
subprocess.run([sys.executable,str(scripts/'package_compact_revision_20261106.py')],check=True)
print('FINALIZATION COMPLETE',flush=True)
