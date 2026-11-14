#!/usr/bin/env python3
"""Diagnostic-only oracle-reference/lambda ablations; no receiver changes."""
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


def main():
    base = ROOT / 'real_usrp_outputs/revision_abc'
    out = ROOT / 'real_usrp_outputs/revision_abc_diagnosis'
    cfg, bank = abc.default_cfg(), abc.source_bank()
    specs = json.loads((base / 'manifest_B.json').read_text())['jobs']
    selected = []
    for spec in specs:
        if spec['family'] != 'B_grid':
            continue
        if spec['snr_db'] == -20 and spec['sir_db'] == 0 and spec['angle_low'] == 10:
            selected.append(('low_snr', spec))
        if spec['snr_db'] == 10 and spec['sir_db'] == -20 and spec['angle_low'] == 0:
            selected.append(('small_angle_strong_interferer', spec))
    rows, scenes = [], []
    for group, spec in selected:
        key = abc.job_key(spec)
        job = json.loads((base / 'jobs' / (key + '.json')).read_text())
        samples, truth, _ = abc.synthesize(spec, bank, cfg)
        assert truth == job['truth'], 'reconstructed scene differs from frozen experiment'
        _, white, _, _, whitener, _ = abc.controlled_inputs(samples, truth, cfg)
        estimate = job['candidate_estimates'][0]
        target = job['targets'][0]
        scenes.append(dict(group=group, key=key, angle_deg=job['effective_whitened_angle_deg'],
            direction_error_deg=target['direction_error_deg'], theta_deg=target['theta_deg'],
            lambda_sp=target['lambda'], lambda_cap=target['lambda_cap'],
            objective=estimate['lambda_objective_sp'], certified=estimate['certified_sp']))
        correct = np.asarray(truth[0]['symbol_bins'])
        for method in ('mrc', 'sp', 'maloragw'):
            metrics = target['methods'][method]
            rows.append(dict(group=group, key=key, reference='production', variant=method,
                delivered=metrics['delivered'], ser=metrics['ser']))
        for reference in ('estimated', 'truth'):
            params = dict(estimate)
            if reference == 'truth':
                params['channel_sp'] = abc.pairs(whitener @ abc.complex_pairs(truth[0]['channel']))
            _, _, (support, orthogonal, _) = abc.projected_decisions(white, params, cfg, keep_spectra=True)
            settings = [('selected', float(estimate['lambda_sp']))] + [
                (f'lambda_{value:g}', value) for value in (0, .125, .25, .5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024)]
            for variant, value in settings:
                bins = np.argmax(support - value * orthogonal, axis=1)
                phy = abc.decode_payload_from_symbol_bins(bins.tolist(), cfg)
                errors = bins != correct
                # The first eight symbols include the explicit header AND some
                # payload bits. This oracle repairs that whole initial block.
                repaired = bins.copy()
                repaired[:8] = correct[:8]
                repaired_phy = abc.decode_payload_from_symbol_bins(repaired.tolist(), cfg)
                delivered = bool(phy.phy_crc_ok and phy.payload.hex() == truth[0]['payload_hex'])
                row = dict(group=group, key=key, reference=reference, variant=variant,
                    lambda_value=value, delivered=delivered, ser=float(np.mean(errors)),
                    initial_block_ser=float(np.mean(errors[:8])), body_ser=float(np.mean(errors[8:])),
                    perfect_initial_block_delivered=bool(repaired_phy.phy_crc_ok and repaired_phy.payload.hex() == truth[0]['payload_hex']))
                if reference == 'estimated' and variant == 'selected':
                    assert delivered == target['methods']['sp']['delivered']
                    assert abs(row['ser'] - target['methods']['sp']['ser']) < 1e-12
                rows.append(row)
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['group'], row['reference'], row['variant'])].append(row)
    aggregates = []
    for (group, reference, variant), values in grouped.items():
        entry = dict(group=group, reference=reference, variant=variant, count=len(values))
        for metric in ('delivered', 'ser', 'initial_block_ser', 'body_ser', 'perfect_initial_block_delivered'):
            if metric in values[0]:
                entry[metric] = float(np.mean([r[metric] for r in values]))
        aggregates.append(entry)
    summary = dict(scene_count=len(scenes), unchanged_receiver=True,
        scope='Known timing/CFO; frozen identical waveforms. Truth reference, lambda sweeps and initial-block repair are diagnostic oracles, not deployable receiver results.',
        original_sp_reproduction_passed=True, aggregates=aggregates, scenes=scenes)
    abc.write_json(out / 'summary.json', summary)
    abc.write_json(out / 'per_scene.json', rows)
    for group in sorted({r['group'] for r in scenes}):
        print(group, flush=True)
        values = [r for r in scenes if r['group'] == group]
        for metric in ('angle_deg', 'direction_error_deg', 'theta_deg', 'lambda_sp', 'objective'):
            print(metric, np.round(np.quantile([r[metric] for r in values], [0, .5, 1]), 4).tolist())
        for entry in aggregates:
            if entry['group'] == group and (entry['reference'] == 'production' or entry['variant'] in ('selected', 'lambda_0', 'lambda_4', 'lambda_32', 'lambda_128', 'lambda_1024')):
                print(json.dumps(entry), flush=True)


if __name__ == '__main__':
    main()
