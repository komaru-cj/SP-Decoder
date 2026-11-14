#!/usr/bin/env python3
"""Offline prototype evaluation on frozen waveforms; one estimated lambda."""
import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import argparse
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from real_collision_experiment.paper_experiments import run_revision_abc as abc
from evaluate_sp_dechirp_real_pos import SPPacketReliability, choose_lambda_sp
from sp_noise_competition import select_with_noise, POLICY

BASE = ROOT / 'real_usrp_outputs/revision_abc'
OUT = ROOT / 'real_usrp_outputs/revision_abc_noise_lambda_prototype'


def scene(spec):
    key = abc.job_key(spec)
    job = json.loads((BASE / 'jobs' / (key + '.json')).read_text())
    cfg = abc.default_cfg()
    samples, truth, _ = abc.synthesize(spec, abc.source_bank(), cfg)
    assert truth == job['truth']
    _, white, _, _, _, _ = abc.controlled_inputs(samples, truth, cfg)
    es = job['candidate_estimates']
    rels = [SPPacketReliability(**{k: e[k] for k in (
        'theta_obs', 'theta_drift', 'theta_total')}, L=e['L_u'], power=e['power_sp'],
        noise_sigma2=e['noise_sigma2_sp'], robust_hit_count=e['robust_hit_count']) for e in es]
    channels = [abc.complex_pairs(e['channel_sp']) for e in es]
    _, _, _, pairs, old = choose_lambda_sp(0, rels, channels, gamma=.05, max_lambda=float('inf'))
    r = rels[0]
    new = select_with_noise(pairs, old['candidate_points'], power=r.power,
        reliability=r.L, noise_sigma2=r.noise_sigma2, cap=old['lambda_cap'],
        noise_bin_count=cfg.m - 1)
    target = job['targets'][0]
    e = dict(es[0], lambda_sp=new['selected_lambda'])
    sp_bins, _, spectra = abc.projected_decisions(white, e, cfg, keep_spectra=True)
    # Cache spectra to allow mathematical-policy checks without regenerating IQ.
    cache = OUT / 'spectra' / (key + '.npz')
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, support=spectra[0], orthogonal=spectra[1])
    phy = abc.decode_payload_from_symbol_bins(sp_bins, cfg)
    return dict(spec=spec, key=key, old=target['methods'], selection=new,
        pair_rows=pairs, old_search=old,
        reference=dict(power=r.power, L=r.L, noise_sigma2=r.noise_sigma2),
        truth_bins=truth[0]['symbol_bins'], payload_hex=truth[0]['payload_hex'],
        delivered=bool(phy.phy_crc_ok and phy.payload.hex() == truth[0]['payload_hex']),
        ser=float(np.mean(np.asarray(sp_bins) != truth[0]['symbol_bins'])))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    specs = json.loads((BASE / 'manifest_B.json').read_text())['jobs']
    specs = [s for s in specs if s['family'] == 'B_grid' and (
        (s['snr_db'] in (-20, -10, 0, 10) and s['sir_db'] in (-20, -10)) or
        (s['snr_db'] == -20 and s['sir_db'] == 0 and s['angle_low'] == 10))]
    grouped = defaultdict(list)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(scene, spec): spec for spec in specs}
        for count, future in enumerate(as_completed(futures), 1):
            result = future.result()
            abc.write_json(OUT / 'jobs' / (result['key'] + '.json'), result)
            s = result['spec']
            grouped[(s['snr_db'], s['sir_db'], s['angle_low'])].append(result)
            if count % 16 == 0:
                print(f'{count}/{len(specs)}', flush=True)
    aggregates = []
    for (snr, sir, angle), values in sorted(grouped.items()):
        row = dict(snr_db=snr, sir_db=sir, angle_low=angle, count=len(values),
            new_pdr=float(np.mean([v['delivered'] for v in values])),
            new_ser=float(np.mean([v['ser'] for v in values])),
            lambda_median=float(np.median([v['selection']['selected_lambda'] for v in values])))
        for method in ('sp', 'mrc', 'maloragw'):
            row[method + '_pdr'] = float(np.mean([v['old'][method]['delivered'] for v in values]))
        aggregates.append(row)
        print(json.dumps(row), flush=True)
    abc.write_json(OUT / 'summary.json', dict(policy=POLICY, scene_count=len(specs),
        prototype=True, aggregates=aggregates))


if __name__ == '__main__':
    main()
