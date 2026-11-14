#!/usr/bin/env python3
"""User-confirmed A3/C1 heatmaps with the current upgraded SP algorithm."""
from __future__ import annotations
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'
os.environ.setdefault('MPLCONFIGDIR', '/tmp/resubmission_heatmaps_mpl')
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import argparse
import copy
import csv
import hashlib
import json
import math
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from real_collision_experiment.paper_experiments import run_revision_abc as abc
from evaluate_sp_dechirp_real_pos import attach_sp_reliability_and_lambda, choose_lambda_sp, SPPacketReliability
from sp_noise_competition import TWO_PACKET_POLICY

OUT = ROOT / 'real_usrp_outputs/revision_heatmaps_A3_C1'
METHODS = ('sp', 'mrc', 'pcube', 'maloragw')
LABELS = {m: abc.LABELS[m] for m in METHODS}
STAGES = ('C1_snr_sir', 'C1_angle_sir', 'A3_density_delay')


def fingerprint():
    return hashlib.sha256((abc.revision_hash() + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()).encode()).hexdigest()


def specs_for(stage, repeats=16, jitter=None):
    if stage == 'C1_snr_sir':
        frozen = json.loads((abc.DEFAULT_OUT / 'manifest_B.json').read_text())['jobs']
        result = []
        for old in frozen:
            if (old['family'] == 'B_grid' and old['angle_low'] == 10
                and old['snr_db'] in (-30., -20., -10., 0.)
                and old['sir_db'] in (-20., -10., 0., 10.) and old['repeat'] < repeats):
                spec = dict(old, family=stage, source_job=abc.job_key(old))
                result.append(spec)
        if len(result) != 16 * repeats:
            raise ValueError('frozen SNR/SIR source supports up to 16 repeats')
        return result
    result = []
    groups = ([(lo, hi) for lo, hi in ((0.,2.),(2.,5.),(5.,10.),(10.,20.))]
              if stage == 'C1_angle_sir' else [(k, gap) for k in (4,6,8,10) for gap in (.05,.1,.2,.3)])
    for group in groups:
        # Paired seeds across SIR; A3 uses one nested ten-source draw per repeat
        # across every K/gap, including payloads, powers and relative phases.
        seed_group = (stage, group if stage == 'C1_angle_sir' else 'nested_ten_sources')
        base = int(hashlib.sha256(repr(seed_group).encode()).hexdigest()[:8], 16)
        for repeat in range(repeats):
            seed = (9452026 + base + repeat * 104729) % (2**32 - 1)
            if stage == 'C1_angle_sir':
                for sir in (-20.,-10.,0.,10.):
                    result.append(dict(family=stage, k=2, angle_low=group[0], angle_high=group[1],
                        snr_db=-10., sir_db=sir, repeat=repeat, seed=seed, focus=[0]))
            else:
                if jitter is None:
                    raise ValueError('A3 jitter units must be explicitly confirmed')
                result.append(dict(family=stage, k=group[0], gap_symbols=group[1],
                    snr_db=0., repeat=repeat, seed=seed, jitter_kind=jitter,
                    packet_power_db_range=[-3.,3.]))
    return result


def a3_synthesize(spec, bank, cfg):
    rng = np.random.default_rng(spec['seed'])
    selected = abc.select_sources(bank, dict(family='A3_master', k=10), rng)
    kind = spec['jitter_kind']
    if kind == 'absolute_0p005':
        jitter = rng.integers(-5,6,9) / 1000.
    elif kind == 'absolute_0p1':
        jitter = rng.integers(-100,101,9) / 1000.
    elif kind == 'relative_50pct':
        jitter = rng.uniform(-.5,.5,9) * spec['gap_symbols']
    elif kind == 'absolute_0p5':
        jitter = rng.integers(-500,501,9) / 1000.
    else:
        raise ValueError(kind)
    k = spec['k']
    gaps = np.round(spec['gap_symbols'] + jitter[:k-1], 3)
    offsets = np.r_[0., np.cumsum(gaps)]
    # Preserve signed increments and label reordering; never clip negatives.
    offsets -= min(0., float(np.min(offsets)))
    starts = np.rint((3 + offsets) * cfg.samples_per_symbol).astype(int)
    params = [(rng.integers(0,256,cfg.payload_len,dtype=np.uint8).tobytes(),
               float(rng.uniform(-3.,3.)), float(rng.random())) for _ in range(10)]
    length = int(max(starts) + cfg.frame_samples + 3 * cfg.samples_per_symbol)
    signal = np.zeros((2,length),dtype=np.complex64)
    truth = []
    for i in range(k):
        source, start = selected[i], int(starts[i])
        payload, power_db, phase = params[i]
        record = bank[source]
        frame, bins = abc.build_explicit_frame(payload,cfg)
        power = 10 ** (power_db/10)
        h = abc.complex_pairs(record['channel_ri']) * math.sqrt(2*power) * np.exp(2j*np.pi*phase)
        cfo = float(record['cfo_bins'])
        carrier = np.exp(2j*np.pi*cfo*np.arange(frame.size)/cfg.samples_per_symbol)
        signal[:,start:start+frame.size] += (h[:,None]*(frame*carrier)[None,:]).astype(np.complex64)
        truth.append(dict(source_index=source, position=record['position'], source_label=record['label'],
            start_sample=float(start), offset_symbols=float(start/cfg.samples_per_symbol-3),
            cfo_bins=cfo,power_per_channel=power,channel=abc.pairs(h),payload_hex=payload.hex(),symbol_bins=bins))
    noise_power = 10 ** (-spec['snr_db']/10)
    noise = (rng.normal(size=signal.shape)+1j*rng.normal(size=signal.shape))*math.sqrt(noise_power/2)
    return signal+noise.astype(np.complex64),truth,noise_power,dict(
        nominal_gap_symbols=spec['gap_symbols'], planned_signed_adjacent_gaps=gaps.tolist(),
        actual_signed_adjacent_gaps=(np.diff(starts)/cfg.samples_per_symbol).tolist(),
        sorted_adjacent_gaps=(np.diff(np.sort(starts))/cfg.samples_per_symbol).tolist(),
        time_order_packet_indices=np.argsort(starts,kind='stable').tolist(),
        negative_start_increment_count=int(np.count_nonzero(gaps<0)))


def payload_metric(bins, truth, cfg):
    phy = abc.decode_payload_from_symbol_bins(list(bins),cfg)
    errors = int(np.count_nonzero(np.asarray(bins)!=np.asarray(truth['symbol_bins'])))
    return dict(delivered=bool(phy.phy_crc_ok and phy.payload.hex()==truth['payload_hex']),
        symbol_errors=errors,symbol_count=len(truth['symbol_bins']),ser=errors/len(truth['symbol_bins']),status=phy.status)


def cached_grid(spec):
    key = spec['source_job']
    old_path = abc.DEFAULT_OUT/'jobs'/(key+'.json')
    new_path = ROOT/'real_usrp_outputs/revision_abc_noise_lambda_v1/jobs'/(key+'.json')
    old, new = json.loads(old_path.read_text()), json.loads(new_path.read_text())
    assert old['truth']==new['truth'] and len(new['candidate_estimates'])==2
    es = new['candidate_estimates']
    assert all(e['overlapping_interferer_count_sp']==1 for e in es)
    hs = [abc.complex_pairs(e['channel_sp']) for e in es]
    rels = [SPPacketReliability(e['theta_obs'],e['theta_drift'],e['theta_total'],e['L_u'],
        e['power_sp'],e['noise_sigma2_sp'],e['robust_hit_count']) for e in es]
    selected,*_ = choose_lambda_sp(0,rels,hs,gamma=.05,max_lambda=None,noise_bin_count=abc.default_cfg().m-1)
    assert abs(selected-es[0]['lambda_sp'])<1e-8
    targets = copy.deepcopy(new['targets'])
    for before, after in zip(old['targets'],targets):
        for m in ('mrc','pcube','maloragw'):
            assert before['methods'][m]==after['methods'][m]
        after['methods'] = {m:after['methods'][m] for m in METHODS}
        after['legacy_sp_ablation'] = before['methods']['sp']
    return dict(spec=spec,config=new['config'],targets=targets,truth=new['truth'],
        source_records=new['source_records'],physical_angle_deg=new['physical_angle_deg'],
        effective_whitened_angle_deg=new['effective_whitened_angle_deg'],sp_policy=TWO_PACKET_POLICY,
        provenance=dict(kind='exact_frozen_two-track_branch_reuse',
            source=str(new_path.relative_to(ROOT)),source_sha256=hashlib.sha256(new_path.read_bytes()).hexdigest(),
            legacy_source=str(old_path.relative_to(ROOT)),current_weight_reproduced=True))


def fresh_job(spec):
    cfg, bank = abc.default_cfg(), abc.source_bank()
    if spec['family']=='A3_density_delay':
        samples,truth,noise,timing = a3_synthesize(spec,bank,cfg)
    else:
        samples,truth,noise = abc.synthesize(spec,bank,cfg)
        timing = dict(actual_signed_adjacent_gaps=[.2])
    physical,white,estimates,sigma,W,cal = abc.controlled_inputs(samples,truth,cfg)
    configured = attach_sp_reliability_and_lambda(white,estimates,cfg,noise_sigma2=sigma,
        gamma=.05,max_lambda=None,noise_competition=True,noise_two_packet_only=True)
    focus = spec.get('focus',list(range(len(truth))))
    targets = []
    contexts = ({m:abc.PaperComparisonContext(physical,estimates,cfg,frontend_method=m)
                 for m in ('mrc','pcube','maloragw')} if spec['family']=='C1_angle_sir' else {})
    for i in focus:
        target = truth[i]
        config = configured[i]
        bins,_,_ = abc.projected_decisions(white,config,cfg)
        metrics = dict(sp=payload_metric(bins,target,cfg))
        for m,context in contexts.items():
            result = {'mrc':context.decode_mrc,'pcube':context.decode_pcube,'maloragw':context.decode_maloragw}[m](estimates[i])
            metrics[m] = payload_metric(result['symbol_bins'],target,cfg)
        targets.append(dict(target_index=i,source_index=target['source_index'],position=target['position'],
            methods=metrics,lambda_sp=config['lambda_sp'],lambda_cap=config['lambda_cap_sp'],
            direction_error_deg=abc.angle_deg(abc.complex_pairs(config['channel_sp']),W@abc.complex_pairs(target['channel'])),
            actual_snr_db=10*math.log10(target['power_per_channel']/noise)))
    physical_angle = abc.angle_deg(abc.complex_pairs(truth[0]['channel']),abc.complex_pairs(truth[1]['channel']))
    return dict(spec=spec,config=asdict(cfg),targets=targets,truth=truth,
        source_records=[bank[t['source_index']] for t in truth],sp_policy=TWO_PACKET_POLICY,
        timing=timing,physical_angle_deg=physical_angle,
        effective_whitened_angle_deg=abc.angle_deg(W@abc.complex_pairs(truth[0]['channel']),W@abc.complex_pairs(truth[1]['channel'])),
        candidate_estimates=configured,calibration=cal,noise_variance_per_channel=noise,
        provenance=dict(kind='fresh_measured_channel_CFO_driven_explicit_waveform_simulation',
            synchronization='controlled_exact_start_CFO; references estimated from mixed noisy preambles'))


def run_job(spec,out,revision):
    path = Path(out)/'jobs'/(abc.job_key(spec)+'.json')
    if path.exists() and json.loads(path.read_text()).get('revision_hash')==revision:
        return True
    started = time.perf_counter()
    result = cached_grid(spec) if spec['family']=='C1_snr_sir' else fresh_job(spec)
    result.update(revision_hash=revision,elapsed_s=time.perf_counter()-started)
    abc.write_json(path,result)
    return False


def write_csv(path,rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def render(stage,out,sp_policy=TWO_PACKET_POLICY):
    out=Path(out)
    manifest=json.loads((out/f'manifest_{stage}.json').read_text())
    grouped=defaultdict(list)
    for spec in manifest['jobs']:
        j=json.loads((out/'jobs'/(abc.job_key(spec)+'.json')).read_text())
        assert j['revision_hash']==manifest['revision_hash'] and j['sp_policy']==sp_policy
        if stage=='C1_snr_sir':x,y=spec['snr_db'],spec['sir_db']
        elif stage=='C1_angle_sir':x,y=(spec['angle_low'],spec['angle_high']),spec['sir_db']
        else:x,y=spec['k'],spec.get('arrival_density',spec['gap_symbols'])
        for m in (METHODS if stage.startswith('C1') else ('sp',)):
            grouped[m,x,y].append(j)
    xs=sorted({x for _,x,_ in grouped});ys=sorted({y for _,_,y in grouped})
    directory=out/'figures';directory.mkdir(exist_ok=True)
    metrics=[]
    plt.rcParams.update({'font.size':11,'pdf.fonttype':42,'svg.fonttype':'none'})
    for m in (METHODS if stage.startswith('C1') else ('sp',)):
        matrix=np.zeros((len(ys),len(xs)))
        for yi,y in enumerate(ys):
            for xi,x in enumerate(xs):
                jobs=grouped[m,x,y]
                values=[t['methods'][m]['delivered'] for j in jobs for t in j['targets']]
                matrix[yi,xi]=np.mean(values)
                metrics.append(dict(stage=stage,method=m,x_low=x[0] if isinstance(x,tuple) else x,
                    x_high=x[1] if isinstance(x,tuple) else x,y=y,scenes=len(jobs),packets=len(values),
                    successes=sum(values),pdr=float(np.mean(values)),sp_policy=sp_policy))
        fig,ax=plt.subplots(figsize=(5.4,4.6))
        im=ax.imshow(matrix,origin='lower',vmin=0,vmax=1,cmap='viridis',aspect='auto')
        for yi in range(len(ys)):
            for xi in range(len(xs)):
                v=matrix[yi,xi];ax.text(xi,yi,f'{v:.3f}',ha='center',va='center',color='white' if v<.45 else 'black')
        xlabels=[f'{x[0]:g}–{x[1]:g}' if isinstance(x,tuple) else f'{x:g}' for x in xs]
        ax.set_xticks(range(len(xs)),xlabels)
        ax.set_yticks(range(len(ys)),[f'{y:.3g}' for y in ys])
        ax.set_xlabel('SNR (dB)' if stage=='C1_snr_sir' else 'Source channel separation (°)' if stage=='C1_angle_sir' else 'Collision order K')
        ax.set_ylabel('SIR (dB)' if stage.startswith('C1') else
            r'Arrival density $\rho=(K-1)T_{sym}/W$' if manifest.get('timing_axis')=='actual_arrival_density'
            else 'Nominal start increment / T_sym')
        ax.set_title(LABELS[m]);fig.colorbar(im,ax=ax,label='PDR');fig.tight_layout()
        name=f'{stage}_{m}'
        for suffix in ('pdf','png','svg'):fig.savefig(directory/f'{name}.{suffix}',dpi=200,bbox_inches='tight')
        plt.close(fig)
    write_csv(directory/f'{stage}_metrics.csv',metrics)
    abc.write_json(directory/f'{stage}_figure_manifest.json',dict(stage=stage,sp_policy=sp_policy,
        pcube_policy=manifest.get('pcube_policy'),
        timing_axis=manifest.get('timing_axis','nominal_start_increment' if stage=='A3_density_delay' else None),
        revision_hash=manifest['revision_hash'],complete=True,jobs=len(manifest['jobs']),
        angle_coordinate='clean measured physical Rx channel' if stage=='C1_angle_sir' else None,
        scope='Controlled start/CFO, preamble-estimated references; no acquisition misses in PDR',
        figures=[f'{stage}_{m}.pdf' for m in (METHODS if stage.startswith('C1') else ('sp',))]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=STAGES,required=True)
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--repeats',type=int,default=16)
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--jitter',choices=('absolute_0p005','absolute_0p1','relative_50pct','absolute_0p5'))
    parser.add_argument('--render-only',action='store_true')
    args=parser.parse_args()
    if args.render_only:render(args.stage,args.out);return
    specs=specs_for(args.stage,args.repeats,args.jitter)
    rev=fingerprint()
    source_bytes=Path(__file__).read_bytes()
    source_digest=hashlib.sha256(source_bytes).hexdigest()
    snapshot=args.out/'source_versions'/f'run_resubmission_heatmaps_{source_digest}.py'
    snapshot.parent.mkdir(parents=True,exist_ok=True)
    snapshot.write_bytes(source_bytes)
    abc.write_json(args.out/f'manifest_{args.stage}.json',dict(stage=args.stage,revision_hash=rev,
        sp_policy=TWO_PACKET_POLICY,config=asdict(abc.default_cfg()),methods=list(METHODS) if args.stage.startswith('C1') else ['sp'],
        arguments={**vars(args),'out':str(args.out)},jobs=specs,
        evidence='measured-channel/CFO-driven explicit-waveform simulation',
        B_scope='controlled start/CFO; preamble-estimated channel and lambda',
        angle_coordinate='clean measured physical Rx channel',
        code_sha256=source_digest,runner_source_snapshot=str(snapshot.relative_to(args.out))))
    began=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(run_job,s,str(args.out),rev) for s in specs]
        for count,future in enumerate(as_completed(futures),1):
            cached=future.result()
            if count%16==0 or count==len(specs):print(json.dumps(dict(done=count,total=len(specs),cached=cached,wall_s=round(time.perf_counter()-began,2))),flush=True)
    render(args.stage,args.out)


if __name__=='__main__':main()
