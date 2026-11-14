#!/usr/bin/env python3
"""Offline single-path proposal: aligned reference and confidence-gated lambda.

This is a development experiment, not the receiver default. No payload CRC or
truth enters configuration. The confidence approximation is not a PDR bound.
"""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import json
import math
import argparse
import hashlib
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import numpy as np
from scipy.stats import norm
from real_collision_experiment.paper_experiments import run_resubmission_heatmaps as hm
from evaluate_sp_dechirp_real_pos import SPPacketReliability,attach_sp_reliability_and_lambda,choose_lambda_sp,channel_angle
from compare.mrc_input import physical_preamble_measurements
abc=hm.abc
OUT=ROOT/'real_usrp_outputs/c1_sp_single_path_proposal'


def configure(physical,white,estimates,cfg,sigma,W):
    es=attach_sp_reliability_and_lambda(white,estimates,cfg,noise_sigma2=sigma,
        gamma=.05,max_lambda=None,noise_competition=True,noise_two_packet_only=True)
    old_h=[abc.complex_pairs(e['channel_sp']) for e in es]
    hs=[W@physical_preamble_measurements(physical,e,cfg)[0] for e in estimates]
    rels=[]
    for h,old,e in zip(hs,old_h,es):
        theta=min(math.pi/2,e['theta_total']+channel_angle(h,old))
        rels.append(SPPacketReliability(e['theta_obs'],e['theta_drift'],theta,
            math.cos(theta)**2,float(np.vdot(h,h).real),sigma,e['robust_hit_count']))
    for i,e in enumerate(es):
        if e['overlapping_interferer_count_sp']!=1:
            e['proposal_reason']='unchanged_nonpair_branch'
            continue
        assert len(es)==2, 'this C1 development experiment requires two tracks'
        j=1-i
        rs=[rels[i],rels[j]];ch=[hs[i],hs[j]]
        lam,U,cert,_,diag=choose_lambda_sp(0,rs,ch,gamma=.05,max_lambda=None,noise_bin_count=cfg.m-1)
        # Approximate strength-estimation SE for the preamble average in white
        # FFT units; Bonferroni split of the existing alpha across both users.
        n=sigma/max(1,cfg.preamble_len)
        se=math.sqrt(4*n*n+2*n*(rs[0].power+rs[1].power))
        strength_margin=rs[1].power-rs[0].power-norm.ppf(1-.05/2)*se
        if U>=rs[0].L:
            reason='reference_cones_not_separated';lam=0.
        elif strength_margin<=0:
            reason='no_confident_interference_dominance';lam=0.
        elif diag['selected_objective'] is None or diag['selected_objective']<=0:
            reason='no_positive_joint_margin';lam=0.
        else:reason='guarded_pair_weight'
        e.update(channel_sp=abc.pairs(hs[i]),lambda_sp=lam,proposal_reason=reason,
            proposal_strength_margin=strength_margin,proposal_objective=diag['selected_objective'],
            proposal_L=rs[0].L,proposal_U=U)
    return es


def run(spec):
    path=OUT/'jobs'/(abc.job_key(spec)+'.json')
    if path.exists():return json.loads(path.read_text())
    source=hm.OUT/'jobs'/(abc.job_key(spec)+'.json')
    saved=json.loads(source.read_text()) if source.exists() else None
    cfg=abc.default_cfg();samples,truth,_=abc.synthesize(spec,abc.source_bank(),cfg)
    if saved is not None:assert truth==saved['truth']
    physical,white,estimates,sigma,W,_=abc.controlled_inputs(samples,truth,cfg)
    es=configure(physical,white,estimates,cfg,sigma,W)
    mrc=abc.PaperComparisonContext(physical,estimates,cfg,frontend_method='mrc').decode_mrc(estimates[0])
    mrc_metric=hm.payload_metric(mrc['symbol_bins'],truth[0],cfg)
    if saved is not None:
        assert mrc_metric==saved['targets'][0]['methods']['mrc']
        old=saved['targets'][0]['methods']
    else:
        old_config=attach_sp_reliability_and_lambda(white,estimates,cfg,noise_sigma2=sigma,
            gamma=.05,max_lambda=None,noise_competition=True,noise_two_packet_only=True)[0]
        old_bins=abc.projected_decisions(white,old_config,cfg)[0]
        old=dict(mrc=mrc_metric,sp=hm.payload_metric(old_bins,truth[0],cfg))
    e=es[0]
    if e['lambda_sp']==0:bins=mrc['symbol_bins']
    else:bins=abc.projected_decisions(white,e,cfg)[0]
    row=dict(spec=spec,proposal=hm.payload_metric(bins,truth[0],cfg),
        old=old,lambda_value=e['lambda_sp'],reason=e['proposal_reason'])
    abc.write_json(path,row)
    return row


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fresh-seed-validation',action='store_true')
    args=parser.parse_args()
    jobs=[]
    for s in ('C1_snr_sir','C1_angle_sir'):
        jobs.extend(json.loads((hm.OUT/f'manifest_{s}.json').read_text())['jobs'])
    if args.fresh_seed_validation:
        OUT=ROOT/'real_usrp_outputs/c1_sp_single_path_fresh_seeds'
        jobs=[dict(s,seed=(s['seed']+7319503)%(2**32-1)) for s in jobs if s['repeat']<4]
    OUT.mkdir(exist_ok=True)
    abc.write_json(OUT/'manifest.json',dict(jobs=jobs,
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='same measured source bank, new seeds; not an independent deployment' if args.fresh_seed_validation else 'frozen C1 development grid',
        receiver_default_changed=False,oracle_inputs=False,payload_crc_selects_lambda=False))
    with ProcessPoolExecutor(max_workers=4) as pool:
        rows=[]
        for i,r in enumerate(pool.map(run,jobs),1):
            rows.append(r)
            if i%32==0:print(f'{i}/{len(jobs)}',flush=True)
    groups=defaultdict(list)
    for r in rows:
        s=r['spec'];x=s['snr_db'] if s['family']=='C1_snr_sir' else s['angle_low']
        groups[s['family'],x,s['sir_db']].append(r)
    summary=[]
    for (stage,x,sir),rs in sorted(groups.items()):
        summary.append(dict(stage=stage,x=x,sir=sir,scenes=len(rs),
            proposal=sum(r['proposal']['delivered'] for r in rs),
            old_sp=sum(r['old']['sp']['delivered'] for r in rs),
            mrc=sum(r['old']['mrc']['delivered'] for r in rs),
            lost_mrc=sum(r['old']['mrc']['delivered'] and not r['proposal']['delivered'] for r in rs),
            rescued_mrc=sum(not r['old']['mrc']['delivered'] and r['proposal']['delivered'] for r in rs),
            reason_counts={reason:sum(r['reason']==reason for r in rs) for reason in sorted({r['reason'] for r in rs})}))
    abc.write_json(OUT/'summary.json',summary)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
