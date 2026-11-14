"""Read-only PCube fidelity controls; alternatives are diagnostic, not baselines.

Retains native measured IQ. Never rewrites heatmaps, jobs, or receiver policy.
"""
import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import json
import hashlib
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from real_collision_experiment.paper_experiments import run_native_iq_heatmaps as native
from compare.real_packet_decoders import _local_peaks, PhysicalEvidencePayloadCache


def worker(task):
    idx, snr, repeat = task[:3]
    repair = len(task)>3 and task[3]
    cfg = native.CFG
    row = native.AUDIT['packets'][idx]
    source = native.PACKETS[idx]
    if snr is None:
        samples = source.copy()
        start = 0.
    else:
        rng = np.random.default_rng(9452026 + idx * 104729 + repeat)
        covariance = np.array([[complex(*v) for v in rr] for rr in row['covariance']])
        scale = np.sqrt(2. / row['signal_vector_power'])
        sigma = 10. ** (-snr / 10.)
        residual = sigma * np.eye(2) - covariance * scale**2
        vals, vectors = np.linalg.eigh(residual)
        assert vals.min() >= 0
        start = 3 * cfg.samples_per_symbol
        samples = np.zeros((2, cfg.frame_samples + 6 * cfg.samples_per_symbol), np.complex64)
        # Match the source-noise budget inside the measured frame.
        for lo, hi, cov in ((0, start, sigma*np.eye(2)),
                            (start, start+cfg.frame_samples, residual),
                            (start+cfg.frame_samples, samples.shape[1], sigma*np.eye(2))):
            ev, vec = np.linalg.eigh(cov)
            noise = (rng.normal(size=(2,hi-lo)) + 1j*rng.normal(size=(2,hi-lo))) / np.sqrt(2)
            samples[:,lo:hi] = (vec @ np.diag(np.sqrt(ev)) @ noise).astype(np.complex64)
        samples[:,start:start+cfg.frame_samples] += source * scale
        samples -= samples[:,:2*cfg.samples_per_symbol].mean(axis=1,keepdims=True)
    est = dict(start_sample=float(start), cfo_bins=row['cfo_bins'], channel=[[0.,0.],[0.,0.]])
    context = native.a.PaperComparisonContext(samples,[est],cfg,frontend_method='pcube',
        payload_spectrum_cache=PhysicalEvidencePayloadCache())
    current = context.decode_pcube(est,grouping_policy='legacy_fixed_gate')
    mrc = context.decode_mrc(est)
    variants = {'current':current['symbol_bins'], 'mrc':mrc['symbol_bins'],
                'diagnostic_ungated_rotated':[], 'diagnostic_nearest_phase':[]}
    if repair:
        from compare.PCube.soft_grouping import POLICY, TARGET_POLICY, CONSERVATIVE_POLICY
        for name,policy in (('experimental_soft_grouping',POLICY),('experimental_target_noise',TARGET_POLICY),
                            ('experimental_soft_extension',CONSERVATIVE_POLICY)):
            variants[name] = context.decode_pcube(est,grouping_policy=policy)['symbol_bins']
    gate_rejections = []
    for q, true_bin in enumerate(row['symbol_bins']):
        spectra = context._payload_spectra(est,q)
        energy = np.sum(abs(spectra)**2,axis=0)
        candidates = _local_peaks(energy,ratio=6.,limit=64)
        z = spectra[0] * spectra[1].conj()
        distance = abs(np.angle(z[candidates] * np.exp(-1j*context._pdoas[0])))
        rotated = np.real(z[candidates] * np.exp(-1j*context._pdoas[0]))
        variants['diagnostic_ungated_rotated'].append(int(candidates[np.argmax(rotated)]))
        variants['diagnostic_nearest_phase'].append(int(candidates[np.argmin(distance)]))
        hit = np.flatnonzero(candidates==true_bin)
        if hit.size and distance[hit[0]] > .5 and variants['current'][q] != true_bin:
            gate_rejections.append(dict(symbol=q, phase_distance=float(distance[hit[0]]),
                true_energy_rank=int(1+np.sum(energy[candidates]>energy[true_bin]))))
    return dict(source=idx,snr=snr,repeat=repeat,pdoa=context._pdoas[0],
                methods={m:native.h.payload_metric(b,row,cfg) for m,b in variants.items()},
                true_candidate_outside_gate_errors=gate_rejections)


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--repair',action='store_true')
    args=parser.parse_args()
    native.initialize()
    tasks = [(r['index'],None,0) for r in native.AUDIT['packets'] if not r.get('excluded')]
    tasks += [(r['index'],snr,repeat) for r in native.AUDIT['packets'] if not r.get('excluded')
              for snr in (-20.,-10.,0.) for repeat in range(8)]
    if args.repair:tasks=[(*t,True) for t in tasks]
    with ProcessPoolExecutor(max_workers=4,initializer=native.initialize) as pool:
        rows = []
        for i,row in enumerate(pool.map(worker,tasks),1):
            rows.append(row)
            if i%100==0:print(f'controls {i}/{len(tasks)}',flush=True)
    prefix='pcube_repair' if args.repair else 'pcube_fidelity'
    native.a.write_json(native.OUT/(prefix+'_control_rows.json'),rows)
    summary = defaultdict(lambda:defaultdict(lambda:dict(success=0,count=0,symbol_errors=0,symbols=0)))
    for row in rows:
        for method,metric in row['methods'].items():
            total = summary[str(row['snr'])][method]
            total['count'] += 1
            total['success'] += int(metric['delivered'])
            total['symbol_errors'] += metric['symbol_errors']
            total['symbols'] += native.CFG.payload_symbol_count
    result = dict(scope='isolated measured-IQ single-packet controls; no production changes; diagnostic variants are not paper-faithful replacements',
                  receiver_sha256=hashlib.sha256((ROOT/'compare/real_packet_decoders.py').read_bytes()).hexdigest(),
                  source_sha256=native.AUDIT['source_file_sha256'],summary=summary,rows=rows)
    native.a.write_json(native.OUT/(prefix+'_controls.json'),result)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
