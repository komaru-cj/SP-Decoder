#!/usr/bin/env python3
"""Cross-check production guard against fresh seeds and unchanged multiuser IQ."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import json
from concurrent.futures import ProcessPoolExecutor
from real_collision_experiment.paper_experiments import run_resubmission_heatmaps as hm
from evaluate_sp_dechirp_real_pos import attach_sp_reliability_and_lambda
abc=hm.abc
OUT=ROOT/'real_usrp_outputs/revision_heatmaps_A3_C1_guard_v2'


def check(task):
    kind,spec,expected=task
    cfg=abc.default_cfg()
    if kind=='A3':samples,truth,_,_=hm.a3_synthesize(spec,abc.source_bank(),cfg)
    else:samples,truth,_=abc.synthesize(spec,abc.source_bank(),cfg)
    physical,white,es,sigma,W,_=abc.controlled_inputs(samples,truth,cfg)
    new=attach_sp_reliability_and_lambda(white,es,cfg,noise_sigma2=sigma,gamma=.05,
        reference_guard=True,physical_samples=physical,whitener=W)
    if kind=='fresh_seeds':
        bins=abc.projected_decisions(white,new[0],cfg)[0]
        metric=hm.payload_metric(bins,truth[0],cfg)
        assert metric==expected['proposal'], 'production differs from frozen development proposal'
        assert abs(new[0]['lambda_sp']-expected['lambda_value'])<1e-8
        mrc=abc.PaperComparisonContext(physical,es,cfg,frontend_method='mrc').decode_mrc(es[0])
        baseline=hm.payload_metric(mrc['symbol_bins'],truth[0],cfg)
        assert baseline==expected['old']['mrc']
        if new[0]['lambda_sp']==0:assert bins==mrc['symbol_bins']
        return dict(kind=kind,sp=metric['delivered'],mrc=baseline['delivered'],
            lost_mrc=baseline['delivered'] and not metric['delivered'])
    old=attach_sp_reliability_and_lambda(white,es,cfg,noise_sigma2=sigma,gamma=.05,
        noise_competition=True,noise_two_packet_only=True)
    for before,after,target,t in zip(old,new,expected['candidate_estimates'],truth):
        assert before['channel_sp']==after['channel_sp']==target['channel_sp']
        assert before['lambda_sp']==after['lambda_sp']==target['lambda_sp']
        b=abc.projected_decisions(white,before,cfg)[0]
        a=abc.projected_decisions(white,after,cfg)[0]
        assert a==b
        scored=next(v for v in expected['targets'] if v['target_index']==new.index(after))
        assert hm.payload_metric(a,t,cfg)==scored['methods']['sp']
    return dict(kind=kind,packets=len(new),all_channels_weights_symbols_equal=True)


def main():
    tasks=[]
    for p in sorted((ROOT/'real_usrp_outputs/c1_sp_single_path_fresh_seeds/jobs').glob('*.json')):
        e=json.loads(p.read_text());tasks.append(('fresh_seeds',e['spec'],e))
    manifest=json.loads((hm.OUT/'manifest_A3_density_delay.json').read_text())
    for s in manifest['jobs']:
        if s['repeat']==0:
            e=json.loads((hm.OUT/'jobs'/(abc.job_key(s)+'.json')).read_text());tasks.append(('A3',s,e))
    with ProcessPoolExecutor(max_workers=4) as pool:rows=list(pool.map(check,tasks))
    fresh=[r for r in rows if r['kind']=='fresh_seeds'];multi=[r for r in rows if r['kind']=='A3']
    result=dict(fresh_seed_scenes=len(fresh),sp_successes=sum(r['sp'] for r in fresh),
        mrc_successes=sum(r['mrc'] for r in fresh),mrc_deliveries_lost=sum(r['lost_mrc'] for r in fresh),
        A3_fresh_scenes=len(multi),A3_fresh_packets=sum(r['packets'] for r in multi),
        A3_channels_weights_symbols_equal=all(r['all_channels_weights_symbols_equal'] for r in multi),rows=rows)
    abc.write_json(OUT/'additional_validation.json',result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))

if __name__=='__main__':main()
