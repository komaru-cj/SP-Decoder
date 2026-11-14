#!/usr/bin/env python3
"""Frozen B-grid diagnostic: relax only the global cap, keeping reliability."""
import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import json
from collections import defaultdict
import numpy as np
from real_collision_experiment.paper_experiments import run_revision_abc as abc
from evaluate_sp_dechirp_real_pos import SPPacketReliability, choose_lambda_sp


def main():
    base = ROOT / 'real_usrp_outputs/revision_abc'
    out = ROOT / 'real_usrp_outputs/revision_abc_diagnosis/lambda_caps'
    cfg, bank = abc.default_cfg(), abc.source_bank()
    specs = json.loads((base / 'manifest_B.json').read_text())['jobs']
    specs = [s for s in specs if s['family'] == 'B_grid' and (
        (s['snr_db'] in (-20, -10, 0, 10) and s['sir_db'] in (-20, -10)) or
        (s['snr_db'] == -20 and s['sir_db'] == 0 and s['angle_low'] == 10))]
    rows = []
    for counter, spec in enumerate(specs):
        key = abc.job_key(spec)
        job = json.loads((base / 'jobs' / (key + '.json')).read_text())
        samples, truth, _ = abc.synthesize(spec, bank, cfg)
        assert truth == job['truth']
        _, white, _, _, _, _ = abc.controlled_inputs(samples, truth, cfg)
        estimates = job['candidate_estimates']
        rels = [SPPacketReliability(**{k: e[k] for k in (
            'theta_obs', 'theta_drift', 'theta_total')}, L=e['L_u'],
            power=e['power_sp'], noise_sigma2=e['noise_sigma2_sp'],
            robust_hit_count=e['robust_hit_count']) for e in estimates]
        channels = [abc.complex_pairs(e['channel_sp']) for e in estimates]
        selected, _, _, _, _ = choose_lambda_sp(0, rels, channels, gamma=.05, max_lambda=4.)
        assert abs(selected - estimates[0]['lambda_sp']) < 1e-9
        relaxed, _, _, _, diag = choose_lambda_sp(0, rels, channels, gamma=.05, max_lambda=float('inf'))
        _, _, (support, orthogonal, _) = abc.projected_decisions(white, estimates[0], cfg, keep_spectra=True)
        common = dict(key=key, snr_db=spec['snr_db'], sir_db=spec['sir_db'],
            angle_low=spec['angle_low'], angle_high=spec['angle_high'],
            lambda_original=selected, lambda_relaxed=relaxed,
            reliability_cap=diag['lambda_cap'], direction_error_deg=job['targets'][0]['direction_error_deg'])
        correct = np.asarray(truth[0]['symbol_bins'])
        for method in ('mrc', 'sp', 'maloragw'):
            old = job['targets'][0]['methods'][method]
            rows.append(dict(common, variant=method, delivered=old['delivered'], ser=old['ser']))
        # All candidates below use only estimated preamble parameters. No truth
        # reference or payload-driven lambda tuning is used for these variants.
        variants = [('relaxed_global_cap', relaxed), ('same_reference_lambda0', 0.)]
        variants += [(f'fixed_{v:g}', v) for v in (.5, 4., 16., 64., 256., 1024.)]
        for variant, value in variants:
            bins = np.argmax(support - value * orthogonal, axis=1)
            phy = abc.decode_payload_from_symbol_bins(bins.tolist(), cfg)
            delivered = bool(phy.phy_crc_ok and phy.payload.hex() == truth[0]['payload_hex'])
            rows.append(dict(common, variant=variant, lambda_value=value,
                delivered=delivered, ser=float(np.mean(bins != correct))))
        if (counter + 1) % 16 == 0:
            print(f'{counter + 1}/{len(specs)} scenes', flush=True)
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['snr_db'], row['sir_db'], row['angle_low'], row['variant'])].append(row)
    aggregates = []
    for (snr, sir, angle, variant), values in sorted(grouped.items()):
        aggregates.append(dict(snr_db=snr, sir_db=sir, angle_low=angle,
            variant=variant, count=len(values),
            pdr=float(np.mean([r['delivered'] for r in values])),
            ser=float(np.mean([r['ser'] for r in values])),
            lambda_original_median=float(np.median([r['lambda_original'] for r in values])),
            lambda_relaxed_median=float(np.median([r['lambda_relaxed'] for r in values])),
            reliability_cap_median=float(np.median([r['reliability_cap'] for r in values]))))
    abc.write_json(out / 'summary.json', dict(scene_count=len(specs), unchanged_receiver=True,
        scope='Frozen B grid; conditional known timing/CFO. Relaxed selector keeps the existing reliability cap and candidate rule; only global cap=4 removed. Fixed-lambda sweeps are diagnostic, not a validated selection policy.',
        original_selection_reproduction_passed=True, aggregates=aggregates))
    abc.write_json(out / 'per_scene.json', rows)
    print('complete', flush=True)
    for entry in aggregates:
        if entry['variant'] in ('sp', 'maloragw', 'relaxed_global_cap'):
            print(json.dumps(entry), flush=True)


if __name__ == '__main__':
    main()
