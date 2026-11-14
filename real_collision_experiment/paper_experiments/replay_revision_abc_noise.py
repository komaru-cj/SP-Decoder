#!/usr/bin/env python3
"""Re-evaluate SP on frozen ABC IQ/frontends; preserve unchanged baselines.

All waveforms are regenerated at the same seeds. C reuses the already recorded
anonymous candidates/calibration, never truth synchronization. References must
reproduce the frozen estimates. C still runs production SP synchronization
refinement; no lambda/CRC retry is added. Output always goes to a new directory.
"""
import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import argparse
import copy
import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from real_collision_experiment.paper_experiments import run_revision_abc as abc
from evaluate_sp_dechirp_real_pos import attach_sp_reliability_and_lambda
from sp_noise_competition import POLICY

SOURCE = ROOT / 'real_usrp_outputs/revision_abc'
DEFAULT_OUT = ROOT / 'real_usrp_outputs/revision_abc_noise_lambda_v1'


def replay(spec, out, revision):
    key = abc.job_key(spec)
    source = SOURCE / 'jobs' / (key + '.json')
    path = Path(out) / 'jobs' / source.name
    if path.exists() and json.loads(path.read_text()).get('revision_hash') == revision:
        return key, True
    old = json.loads(source.read_text())
    job = copy.deepcopy(old)
    cfg = abc.default_cfg()
    began = time.perf_counter()
    samples, truth, noise = abc.synthesize(spec, abc.source_bank(), cfg)
    assert truth == old['truth'] and noise == old['noise_variance_per_channel']
    cal = old['calibration']
    whitener = np.asarray([[complex(*v) for v in row] for row in cal['whitener']])
    dc = abc.complex_pairs(cal['dc'])
    white = (whitener @ (samples.astype(np.complex128) - dc[:, None])).astype(np.complex64)
    estimates = old['candidate_estimates']
    started = time.perf_counter()
    configured = attach_sp_reliability_and_lambda(white, estimates, cfg,
        noise_sigma2=cfg.m * cal['noise_sigma2_time'], gamma=.05, max_lambda=None,
        noise_competition=True)
    config_seconds = time.perf_counter() - started
    for previous, current in zip(estimates, configured):
        assert np.allclose(previous['channel_sp'], current['channel_sp'], rtol=1e-12, atol=1e-10), 'reference mismatch'
        assert previous['theta_total'] == current['theta_total'], 'uncertainty mismatch'
    decoded, mechanism = [], []
    for index, config in enumerate(configured):
        started = time.perf_counter()
        bins, ref_bins, spectra = abc.projected_decisions(white, config, cfg,
            keep_spectra=spec['family'] == 'A')
        phy = abc.decode_payload_from_symbol_bins(bins, cfg)
        result = dict(symbol_bins=bins, phy=dict(phy_crc_ok=bool(phy.phy_crc_ok),
            payload_hex=phy.payload.hex(), status=phy.status))
        if spec['family'] == 'C':
            result = next(row for row in abc.decode_sp_stages(white, config, cfg,
                max_sync_trials=32) if row['method'] == 'sp_sync_refine')
        result['seconds'] = time.perf_counter() - started + config_seconds / max(1, len(configured))
        result['core_bins'], result['ref_bins'] = bins, ref_bins
        decoded.append(result)
        if spec['family'] == 'A':
            target = truth[index]
            support, orthogonal, score = spectra
            for q, b in enumerate(target['symbol_bins']):
                absolute = target['start_sample'] + (cfg.payload_start_symbols + q) * cfg.samples_per_symbol
                active = sum(t['start_sample'] < absolute + cfg.samples_per_symbol and t['start_sample'] + cfg.frame_samples > absolute for t in truth)
                mechanism.append(dict(target=index, symbol=q, true_bin=b,
                    mrc_bin=int(np.argmax(support[q])), sp_bin=int(np.argmax(score[q])),
                    lambda_sp=config['lambda_sp'], overlap_frames=int(active),
                    rank_before=int(1 + np.count_nonzero(support[q] > support[q, b])),
                    rank_after=int(1 + np.count_nonzero(score[q] > score[q, b]))))
    for target in job['targets']:
        i, j = target['target_index'], target['matched_candidate']
        config = configured[j] if j is not None else None
        target['lambda'] = config['lambda_sp'] if config else None
        target['lambda_cap'] = config['lambda_cap_sp'] if config else None
        result = decoded[j] if j is not None else None
        expected = truth[i]
        if spec['family'] == 'C':
            delivered = any(r['phy']['phy_crc_ok'] and r['phy']['payload_hex'] == expected['payload_hex'] for r in decoded)
        else:
            delivered = result is not None and result['phy']['phy_crc_ok'] and result['phy']['payload_hex'] == expected['payload_hex']
        bins = result['symbol_bins'] if result else []
        errors = sum(q >= len(bins) or bins[q] != b for q, b in enumerate(expected['symbol_bins']))
        target['methods']['sp'] = dict(delivered=bool(delivered), symbol_errors=int(errors),
            symbol_count=len(expected['symbol_bins']), ser=errors / len(expected['symbol_bins']),
            status=result['phy']['status'] if result else 'not_established')
        if result:
            target['core_rescued_symbols'] = sum(m != b and s == b for m, s, b in zip(result['ref_bins'], result['core_bins'], expected['symbol_bins']))
            target['core_harmed_symbols'] = sum(m == b and s != b for m, s, b in zip(result['ref_bins'], result['core_bins'], expected['symbol_bins']))
    job['candidate_estimates'] = configured
    job['decoder_work_s']['sp'] = sum(r['seconds'] for r in decoded)
    if mechanism:
        job['mechanism_symbols'] = mechanism
    job['lambda_policy'] = POLICY
    job['revision_hash'] = revision
    job['replay_audit'] = dict(source_path=str(source.relative_to(ROOT)),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_revision=old['revision_hash'], unchanged_baselines_reused=True,
        frontend='frozen_anonymous_candidates_and_calibration' if spec['family'] == 'C' else 'unchanged_controlled_timing_CFO',
        reconstructed_truth_equal=True, preamble_references_reproduced=True,
        original_elapsed_s=old['elapsed_s'], replay_elapsed_s=time.perf_counter() - began,
        timing='unchanged front-end/baseline times carried over; new SP stage timed; not a fresh whole-pipeline benchmark')
    abc.write_json(path, job)
    return key, False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--mode', choices=('A','B','C','pilot','all'), default='all')
    args = parser.parse_args()
    if args.out.resolve() == SOURCE.resolve():
        parser.error('frozen source output must not be overwritten')
    revision = hashlib.sha256((abc.revision_hash() + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()).encode()).hexdigest()
    specs = []
    modes = ('A','B','C','pilot') if args.mode == 'all' else (args.mode,)
    for mode in modes:
        manifest = json.loads((SOURCE / f'manifest_{mode}.json').read_text())
        manifest.update(revision_hash=revision, lambda_policy=POLICY,
            replay_source=str(SOURCE), source_revision=manifest['revision_hash'],
            replay_scope='SP recomputed; identical IQ, reference estimates, frontend and non-SP baselines',
            replay_arguments={**vars(args), 'out': str(args.out)})
        abc.write_json(args.out / f'manifest_{mode}.json', manifest)
        specs.extend(manifest['jobs'])
    began = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(replay, spec, str(args.out), revision) for spec in specs]
        for count, future in enumerate(as_completed(futures), 1):
            key, cached = future.result()
            if count % 16 == 0 or count == len(specs):
                print(json.dumps(dict(done=count, total=len(specs), key=key, cached=cached,
                    wall_s=round(time.perf_counter() - began, 2))), flush=True)


if __name__ == '__main__':
    main()
