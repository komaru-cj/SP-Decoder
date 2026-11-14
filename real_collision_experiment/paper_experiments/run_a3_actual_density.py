"""User-approved actual-density A3, reusing native IQ and relative start patterns."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import json,hashlib,shutil
from concurrent.futures import ProcessPoolExecutor,as_completed
from real_collision_experiment.paper_experiments import run_native_iq_heatmaps as n

CANONICAL=n.OUT
OUT=ROOT/'real_usrp_outputs/revision_a3_actual_density'


def initialize():
    n.OUT=CANONICAL
    n.initialize()
    n.OUT=OUT


def main():
    global OUT
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--remove-lambda-cap4',action='store_true')
    parser.add_argument('--lambda-cap',type=float,choices=(4.,10.,40.),default=4.)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if args.remove_lambda_cap4:OUT=ROOT/'real_usrp_outputs/revision_a3_actual_density_nocap'
    elif args.lambda_cap!=4:OUT=ROOT/f'real_usrp_outputs/revision_a3_actual_density_cap{args.lambda_cap:g}'
    if args.out is not None:OUT=args.out
    OUT.mkdir(exist_ok=True)
    initialize()
    old=json.loads((CANONICAL/'manifest_A3_density_delay.json').read_text())
    if old.get('timing_axis')=='actual_arrival_density':
        # The original unscaled templates are retained even after publication.
        old=json.loads((CANONICAL/'backup_a3_nominal_density_20261030/manifest_A3_density_delay.json').read_text())
    jobs=[dict(s,arrival_density=1/s['gap_symbols'],original_timing_job=n.a.job_key(s)) for s in old['jobs']]
    if args.remove_lambda_cap4:
        jobs=[dict(s,remove_multiuser_lambda_cap=True) for s in jobs]
    elif args.lambda_cap!=4:
        jobs=[dict(s,multiuser_lambda_cap=args.lambda_cap) for s in jobs]
    files=['real_collision_experiment/paper_experiments/run_native_iq_heatmaps.py',
        'real_collision_experiment/paper_experiments/run_a3_actual_density.py',
        'real_collision_experiment/paper_experiments/arrival_density.py',
        'real_collision_experiment/paper_experiments/run_resubmission_heatmaps.py',
        'compare/real_packet_decoders.py','compare/PCube/soft_grouping.py',
        'sp_reference_guard.py','sp_noise_competition.py','evaluate_sp_dechirp_real_pos.py',
        'lora_mrc_sp_core.py','real_collision_experiment/node01_sp_receiver/lora_phy_decode.py']
    hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
    revision=hashlib.sha256((n.a.revision_hash()+json.dumps(hashes,sort_keys=True)+json.dumps(n.AUDIT,sort_keys=True)).encode()).hexdigest()
    manifest=dict(old,jobs=jobs,revision_hash=revision,timing_axis='actual_arrival_density',
        density_definition='rho=(K-1)*T_sym/(max(start)-min(start))',
        density_levels=[10/3,5.,10.,20.],
        timing_generation='Scale each original signed relative start pattern to W=(K-1)*T_sym/rho, then quantize to samples',
        absolute_jitter_preserved=False,relative_jitter_and_packet_order_preserved_up_to_sample_quantization=True,
        source_manifest=str(CANONICAL/'backup_a3_nominal_density_20261030/manifest_A3_density_delay.json'),
        waveform='native measured dual-channel IQ superposition; no chirp regeneration',
        sp_policy=n.GUARDED_PAIR_POLICY,pcube_policy=n.DEFAULT_PCUBE_POLICY,
        code_sha256=hashes,source_sha256=n.AUDIT['source_file_sha256'])
    manifest.update(lambda_fixed_cap_removed=args.remove_lambda_cap4,
        lambda_global_max=None if args.remove_lambda_cap4 else args.lambda_cap,
        lambda_range_policy='multiuser_reliability_bound_only' if args.remove_lambda_cap4 else f'multiuser_fixed_cap_{args.lambda_cap:g}',
        lambda_reference_reliability_bound_preserved=True,previous_candidates_preserved=args.remove_lambda_cap4 or args.lambda_cap>4)
    n.a.write_json(OUT/'manifest_A3_density_delay.json',manifest)
    n.a.write_json(OUT/'source_audit.json',n.AUDIT)
    for name in files:
        dest=OUT/'code_snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
    with ProcessPoolExecutor(max_workers=4,initializer=initialize) as pool:
        futures=[pool.submit(n.run,s,revision) for s in jobs]
        for i,f in enumerate(as_completed(futures),1):
            f.result()
            if i%16==0:print(f'A3 actual density {i}/{len(jobs)}',flush=True)
    n.h.render('A3_density_delay',OUT,sp_policy=n.GUARDED_PAIR_POLICY)
    print('A3_ACTUAL_DENSITY_COMPLETE',flush=True)


if __name__=='__main__':main()
