"""Resume the frozen matrix; calibration and geometry first, without changing specs."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import argparse,json,time
from concurrent.futures import ProcessPoolExecutor,as_completed
from real_collision_experiment.paper_experiments import run_boundary_fairness as b


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    b.initialize();m=json.loads((b.OUT/'manifest.json').read_text())
    rank={'isolated':0,'geometry':1,'temporal':2}
    jobs=sorted(m['jobs'],key=lambda s:(rank[s['family']],s['repeat'],s['k']))
    completed=0;todo=[]
    for s in jobs:
        p=b.OUT/'jobs'/(b.n.a.job_key(s)+'.json')
        try:valid=json.loads(p.read_text()).get('revision')==m['revision']
        except (FileNotFoundError,json.JSONDecodeError):valid=False
        if valid:completed+=1
        else:todo.append(s)
    print(f'RESUME {completed}/{len(jobs)}; remaining {len(todo)}',flush=True)
    started=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers,initializer=b.initialize) as pool:
        fs=[pool.submit(b.run_job,s,m['revision']) for s in todo]
        for i,f in enumerate(as_completed(fs),1):
            f.result()
            if i%16==0 or i==len(todo):
                elapsed=time.perf_counter()-started
                print(f'COMPLETE {completed+i}/{len(jobs)}; new={i}; elapsed={elapsed:.0f}s',flush=True)
    print('FROZEN_BOUNDARY_MATRIX_COMPLETE',flush=True)
