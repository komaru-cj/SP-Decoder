#!/usr/bin/env python3
"""Frozen-waveform C1 diagnostics; no receiver policy or paper figures changed.

Oracle variants and fixed-lambda sweeps are diagnostics only, never receiver
inputs or CRC-based per-packet selection policies.
"""
import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import json
import math
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import numpy as np
from real_collision_experiment.paper_experiments import run_resubmission_heatmaps as hm
from evaluate_sp_dechirp_real_pos import SPPacketReliability, choose_lambda_sp, attach_sp_reliability_and_lambda
from compare.mrc_input import physical_preamble_measurements
abc = hm.abc
OUT = ROOT / 'real_usrp_outputs/c1_sp_fallback_diagnostic'


def response_power(cfo, cfg):
    """Known CFO response of the uncorrected five-bin preamble estimator."""
    center = round(cfo) % cfg.m
    local = [(center + k) % cfg.m for k in range(-2, 3)]
    spectrum = np.fft.fft(np.exp(2j * np.pi * cfo * np.arange(cfg.m) / cfg.m))
    return float(abs(np.dot(spectrum[local], [.12, .45, 1., .45, .12]))**2 / cfg.m**2)


def run(spec):
    saved = json.loads((hm.OUT / 'jobs' / (abc.job_key(spec) + '.json')).read_text())
    cfg = abc.default_cfg()
    samples, truth, _ = abc.synthesize(spec, abc.source_bank(), cfg)
    assert truth == saved['truth']
    physical, white, estimates, sigma, W, _ = abc.controlled_inputs(samples, truth, cfg)
    es = attach_sp_reliability_and_lambda(white, estimates, cfg, noise_sigma2=sigma,
        gamma=.05, max_lambda=None, noise_competition=True, noise_two_packet_only=True)
    rels = [SPPacketReliability(e['theta_obs'], e['theta_drift'], e['theta_total'],
        e['L_u'], e['power_sp'], e['noise_sigma2_sp'], e['robust_hit_count']) for e in es]
    hs = [abc.complex_pairs(e['channel_sp']) for e in es]
    gains = [response_power(t['cfo_bins'], cfg) for t in truth]
    true_power = [float(cfg.m**2 * np.linalg.norm(W @ abc.complex_pairs(t['channel']))**2) for t in truth]
    adjusted = [replace(r, power=r.power/g) for r,g in zip(rels,gains)]
    oracle = [replace(r, power=p) for r,p in zip(rels,true_power)]
    corrected_lam = choose_lambda_sp(0,adjusted,hs,gamma=.05,max_lambda=None,noise_bin_count=cfg.m-1)[0]
    oracle_lam = choose_lambda_sp(0,oracle,hs,gamma=.05,max_lambda=None,noise_bin_count=cfg.m-1)[0]
    _, _, spectra = abc.projected_decisions(white, es[0], cfg, keep_spectra=True)
    P,Q,_ = spectra
    variants = {}
    for label,lam in [('current',es[0]['lambda_sp']),('same_reference_lambda0',0.),
                      ('CFO_power_calibration',corrected_lam),('oracle_power_only',oracle_lam)]:
        variants[label] = dict(hm.payload_metric(np.argmax(P-lam*Q,axis=1).tolist(),truth[0],cfg),lambda_value=lam)
    assert variants['current']['delivered'] == saved['targets'][0]['methods']['sp']['delivered']
    assert variants['current']['symbol_errors'] == saved['targets'][0]['methods']['sp']['symbol_errors']
    for label,h in [('MRC_reference_white_lambda0',W @ physical_preamble_measurements(physical,estimates[0],cfg)[0]),
                    ('oracle_reference_lambda0',W @ abc.complex_pairs(truth[0]['channel']))]:
        config=dict(es[0],channel_sp=abc.pairs(h),lambda_sp=0.)
        bins,_,_=abc.projected_decisions(white,config,cfg)
        variants[label]=hm.payload_metric(bins,truth[0],cfg)
    for m in ('mrc','pcube','maloragw'):
        variants[m] = saved['targets'][0]['methods'][m]
    legacy_spec = dict(spec)
    if spec['family']=='C1_snr_sir':
        legacy_spec.pop('source_job');legacy_spec['family']='B_grid'
        old=json.loads((abc.DEFAULT_OUT/'jobs'/(abc.job_key(legacy_spec)+'.json')).read_text())
        variants['legacy_sp']=old['targets'][0]['methods']['sp']
    sweep={str(lam):hm.payload_metric(np.argmax(P-lam*Q,axis=1).tolist(),truth[0],cfg)
           for lam in (0.,.0625,.125,.25,.5,1.,2.,4.,8.,16.,32.,64.,128.,256.)}
    return dict(spec=spec,variants=variants,sweep=sweep,calibration_gain=gains,
        estimated_to_true_power=[r.power/p for r,p in zip(rels,true_power)],
        estimated_sir_db=10*math.log10(rels[0].power/rels[1].power),
        corrected_sir_db=10*math.log10(adjusted[0].power/adjusted[1].power),
        true_whitened_sir_db=10*math.log10(true_power[0]/true_power[1]),
        direction_error_deg=abc.angle_deg(hs[0],W@abc.complex_pairs(truth[0]['channel'])),
        theta_total_deg=math.degrees(rels[0].theta_total),L=rels[0].L,
        U=es[0]['U_max_sp'],certified=es[0]['certified_sp'],
        lambda_objective=es[0]['lambda_objective_sp'],pair_rows=es[0]['lambda_pair_rows_sp'],
        candidates=es[0]['lambda_candidate_points_sp'])


def main():
    specs=[]
    for stage in ('C1_snr_sir','C1_angle_sir'):
        jobs=json.loads((hm.OUT/f'manifest_{stage}.json').read_text())['jobs']
        specs.extend(s for s in jobs if (s['snr_db']==-20 if stage=='C1_snr_sir' else s['angle_low']<10 and s['sir_db']==0))
    OUT.mkdir(exist_ok=True)
    with ProcessPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(run,specs))
    abc.write_json(OUT/'per_scene.json',rows)
    groups=defaultdict(list)
    for row in rows:
        s=row['spec']
        key=f"SNR=-20,SIR={s['sir_db']:g}" if s['family']=='C1_snr_sir' else f"angle={s['angle_low']:g}-{s['angle_high']:g},SIR=0"
        groups[key].append(row)
    summary={}
    for key,rs in groups.items():
        methods={m:dict(successes=sum(r['variants'][m]['delivered'] for r in rs),
            packets=len(rs),ser=float(np.mean([r['variants'][m]['ser'] for r in rs]))) for m in rs[0]['variants']}
        summary[key]=dict(methods=methods,
            lambda_median=float(np.median([r['variants']['current']['lambda_value'] for r in rs])),
            lambda_zero=sum(r['variants']['current']['lambda_value']==0 for r in rs),
            fallback_sp_successes=sum(r['variants']['current']['delivered'] for r in rs if r['variants']['current']['lambda_value']==0),
            fallback_mrc_successes=sum(r['variants']['mrc']['delivered'] for r in rs if r['variants']['current']['lambda_value']==0),
            reference_error_median_deg=float(np.median([r['direction_error_deg'] for r in rs])),
            uncertainty_median_deg=float(np.median([r['theta_total_deg'] for r in rs])),
            power_ratio_median=float(np.median([r['estimated_to_true_power'][0] for r in rs])),
            gain_range=[min(r['calibration_gain'][0] for r in rs),max(r['calibration_gain'][0] for r in rs)],
            sweep_successes={k:sum(r['sweep'][k]['delivered'] for r in rs) for k in rs[0]['sweep']})
    abc.write_json(OUT/'summary.json',summary)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
