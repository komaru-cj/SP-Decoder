#!/usr/bin/env python3
"""Replay the approved single-path reference/weight guards on frozen A3/C1."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import argparse
import copy
import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
from real_collision_experiment.paper_experiments import run_resubmission_heatmaps as hm
from evaluate_sp_dechirp_real_pos import attach_sp_reliability_and_lambda
from sp_reference_guard import GUARDED_PAIR_POLICY
abc=hm.abc
OUT=ROOT/'real_usrp_outputs/revision_heatmaps_A3_C1_guard_v2'


def replay(spec,out,revision):
    path=Path(out)/'jobs'/(abc.job_key(spec)+'.json')
    if path.exists():
        row=json.loads(path.read_text())
        if row['revision_hash']==revision:return row
    source=hm.OUT/'jobs'/path.name
    old=json.loads(source.read_text())
    began=time.perf_counter()
    row=copy.deepcopy(old)
    cfg=abc.default_cfg()
    if spec['family']=='A3_density_delay':
        # All supplied tracks overlap in these scenes. The guard deliberately
        # returns the identical bounded multiuser configuration for every one.
        assert all(e['overlapping_interferer_count_sp']>1 for e in old['candidate_estimates'])
        for e in row['candidate_estimates']:
            e.update(lambda_guard_policy_sp=GUARDED_PAIR_POLICY,
                lambda_guard_reason_sp='retain_bounded_multiuser_branch')
        kind='identical_bounded_multiuser_branch_reuse'
    else:
        samples,truth,_=abc.synthesize(spec,abc.source_bank(),cfg)
        assert truth==old['truth']
        physical,white,estimates,sigma,W,cal=abc.controlled_inputs(samples,truth,cfg)
        es=attach_sp_reliability_and_lambda(white,estimates,cfg,noise_sigma2=sigma,
            gamma=.05,max_lambda=None,reference_guard=True,physical_samples=physical,whitener=W)
        context=abc.PaperComparisonContext(physical,estimates,cfg,frontend_method='mrc')
        for t in row['targets']:
            i=t['target_index'];e=es[i]
            mrc=context.decode_mrc(estimates[i])
            assert hm.payload_metric(mrc['symbol_bins'],truth[i],cfg)==t['methods']['mrc']
            bins,_,_=abc.projected_decisions(white,e,cfg)
            if e['lambda_sp']==0:
                assert bins==mrc['symbol_bins'],'physical MRC fallback mismatch'
            t['previous_sp_ablation']=copy.deepcopy(t['methods']['sp'])
            t['previous_lambda_v1']=t.get('lambda_sp',t.get('lambda'))
            t['methods']['sp']=hm.payload_metric(bins,truth[i],cfg)
            t.update(lambda_sp=e['lambda_sp'],lambda_cap=e['lambda_cap_sp'],
                lambda_guard_reason=e['lambda_guard_reason_sp'],
                direction_error_deg=abc.angle_deg(abc.complex_pairs(e['channel_sp']),W@abc.complex_pairs(truth[i]['channel'])))
            if 'lambda' in t:t['lambda']=e['lambda_sp']
        row.update(candidate_estimates=es,calibration=cal)
        kind='fresh_single_path_core_replay_identical_waveform'
    row.update(sp_policy=GUARDED_PAIR_POLICY,revision_hash=revision,
        provenance=dict(kind=kind,source=str(source.relative_to(ROOT)),
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            payload_crc_selects_lambda=False,oracle_inputs=False),
        replay_elapsed_s=time.perf_counter()-began)
    abc.write_json(path,row)
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    digest=hashlib.sha256()
    paths=[Path(__file__),ROOT/'sp_reference_guard.py',ROOT/'evaluate_sp_dechirp_real_pos.py',
        ROOT/'sp_noise_competition.py',ROOT/'real_collision_experiment/paper_experiments/run_revision_abc.py']
    for p in paths:digest.update(p.read_bytes())
    rev=digest.hexdigest();jobs=[]
    for stage in hm.STAGES:
        manifest=json.loads((hm.OUT/f'manifest_{stage}.json').read_text())
        manifest.update(revision_hash=rev,sp_policy=GUARDED_PAIR_POLICY,
            source_manifest=str((hm.OUT/f'manifest_{stage}.json').relative_to(ROOT)),
            configuration='single preamble-configured lambda; no CRC mode selection')
        manifest['source_runner_code_sha256']=manifest.pop('code_sha256',None)
        historical=manifest.pop('runner_source_snapshot',None)
        if historical:manifest['source_runner_snapshot']=str((hm.OUT/historical).relative_to(ROOT))
        manifest['replay_runner_snapshot']='code_snapshot/real_collision_experiment/paper_experiments/replay_guarded_heatmaps.py'
        abc.write_json(args.out/f'manifest_{stage}.json',manifest)
        jobs.extend(manifest['jobs'])
    snapshot=args.out/'code_snapshot'
    for p in paths:
        target=snapshot/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    rows=[];began=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        fs=[pool.submit(replay,s,str(args.out),rev) for s in jobs]
        for i,f in enumerate(as_completed(fs),1):
            rows.append(f.result())
            if i%32==0:print(json.dumps(dict(done=i,total=len(jobs),elapsed_s=round(time.perf_counter()-began,1))),flush=True)
    for stage in hm.STAGES:hm.render(stage,args.out,sp_policy=GUARDED_PAIR_POLICY)
    audit=[]
    for stage in hm.STAGES[:2]:
        stage_rows=[r for r in rows if r['spec']['family']==stage]
        audit.append(dict(stage=stage,scenes=len(stage_rows),
            sp_successes=sum(t['methods']['sp']['delivered'] for r in stage_rows for t in r['targets']),
            old_sp_successes=sum(t['previous_sp_ablation']['delivered'] for r in stage_rows for t in r['targets']),
            mrc_successes=sum(t['methods']['mrc']['delivered'] for r in stage_rows for t in r['targets']),
            mrc_deliveries_lost=sum(t['methods']['mrc']['delivered'] and not t['methods']['sp']['delivered'] for r in stage_rows for t in r['targets'])))
    abc.write_json(args.out/'validation.json',dict(policy=GUARDED_PAIR_POLICY,revision_hash=rev,
        scenes=len(rows),C1=audit,A3='identical bounded branch reused; separately verify fresh subset',
        physical_mrc_symbol_equality_checked=True,payload_crc_selects_lambda=False,oracle_inputs=False))
    print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
