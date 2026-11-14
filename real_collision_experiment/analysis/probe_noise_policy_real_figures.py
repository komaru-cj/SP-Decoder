#!/usr/bin/env python3
"""Small real-IQ SP policy probe; never overwrite paper reports or figures."""
import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
RX = ROOT / 'real_collision_experiment/node01_sp_receiver'
sys.path[:0] = [str(ROOT), str(RX)]
import argparse
import copy
import csv
import hashlib
import json
import re
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from dataclasses import asdict
from evaluate_sp_dechirp_real_pos import SPPacketReliability, choose_lambda_sp
from real_lora_config import RealCollisionLoRaConfig
from sc16_io import read_sc16
from sp_node01_receiver import decode_sp_stages, validate_payload
from real_collision_experiment.paper_experiments.run_revision_abc import write_json

OUT = ROOT / 'real_usrp_outputs/sp_noise_policy_real_figure_probe'
INDOOR = ROOT / 'real_collision_experiment/analysis/fig9_10_12_5s/reports'
OUTDOOR = ROOT / 'real_collision_experiment/analysis/outdoor_fig13_5s/reports'
TRACE = ROOT / 'real_collision_experiment/analysis/fig9_10_12_10s/reports'
INTERVALS = ROOT / 'real_usrp_outputs/1fig11_real_run_intervals_2_4_8_12_16_scenes/fig11_real_collision_intervals.csv'


def load(path):
    return json.loads(Path(path).read_text())


def method(candidate):
    return next(m for m in candidate['methods'] if m['method'] == 'sp_sync_refine')


def cfg_for(report):
    c = report['config']
    return RealCollisionLoRaConfig(sf=int(c['sf']), bw_hz=float(c['bw_hz']),
        sample_rate_hz=float(c['sample_rate_hz']), preamble_len=int(c['preamble_len']),
        payload_len=int(c['payload_len']))


def weights(report):
    candidates = report['candidates']
    byid = {c['candidate_id']: c for c in candidates}
    cfg = cfg_for(report)
    sigma = cfg.m * report['calibration']['noise_sigma2_time']
    rows = []
    for candidate in candidates:
        old = float(candidate['lambda_sp'])
        new = old
        gate = candidate['overlapping_interferer_count_sp'] == 1
        if gate:
            pair = candidate['lambda_pair_rows_sp'][0]
            peer = byid[pair.get('interferer_candidate_id', pair['interferer_index'])]
            cs = [candidate, peer]
            hs = [np.asarray([complex(*v) for v in c['channel_sp']]) for c in cs]
            rels = [SPPacketReliability(0., 0., c['theta_total'], c['L_u'],
                float(np.vdot(h, h).real), sigma, c['robust_hit_count']) for c,h in zip(cs,hs)]
            reproduced, *_ = choose_lambda_sp(0, rels, hs, gamma=.05, max_lambda=4.)
            assert abs(reproduced-old) < 1e-8, ('old weight mismatch', candidate['candidate_id'], old, reproduced)
            new, *_ = choose_lambda_sp(0, rels, hs, gamma=.05, max_lambda=None,
                noise_bin_count=cfg.m-1)
        rows.append(dict(candidate_id=candidate['candidate_id'], gate=gate,
            old_lambda=old, new_lambda=float(new), changed=abs(new-old)>1e-8,
            competitors=candidate['overlapping_interferer_count_sp']))
    return rows


def sources():
    paths = []
    trace_names = sorted({r['run'] for r in csv.DictReader(INTERVALS.open())})
    paths += [('fig13_trace', TRACE / (name+'.json')) for name in trace_names]
    for family, directory in [('fig14_indoor', INDOOR), ('fig15_outdoor', OUTDOOR)]:
        for path in sorted(directory.glob('*.json')):
            if not re.fullmatch(r'run_[0-9a-f]{8}\.json',path.name):
                continue
            # The indoor two-node compact-deployment records are a different figure.
            if family == 'fig14_indoor' and path.stem.startswith('run_02'):
                continue
            paths.append((family,path))
    return paths


def audit():
    results=[]
    for family,path in sources():
        report=load(path)
        rows=weights(report)
        results.append(dict(family=family,report=str(path.relative_to(ROOT)),run=path.stem,
            report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            sf=report['config']['sf'],bw_hz=report['config']['bw_hz'],nodes=len(report['active_nodes']),
            window_s=report['input']['analysis_slice']['requested_duration_s'],
            candidates=len(rows),gate=sum(r['gate'] for r in rows),changed=sum(r['changed'] for r in rows),
            weights=[r for r in rows if r['gate']]))
        print(f"{family} {path.stem} candidates={len(rows)} gate={results[-1]['gate']} changed={results[-1]['changed']}",flush=True)
    write_json(OUT/'gate_audit.json',results)
    return results


def identify(report,result):
    raw_id=report.get('run_id')
    run_id=int(raw_id,0) if isinstance(raw_id,str) else raw_id
    manifest=report.get('_probe_manifest')
    if manifest is None:
        manifest=load(report['input']['manifest'])
        report['_probe_manifest']=manifest
    accepted={int(v) for v in manifest.get('config',{}).get('merged_source_run_ids',[])}
    app,ok,status=validate_payload(bytes.fromhex(result['phy']['payload_hex']),
        run_id=run_id,active_nodes=set(report['active_nodes']),accepted_run_ids=accepted)
    result['application']=dict(app_crc_ok=bool(ok),status=status,
        decoded=asdict(app) if app is not None else None)
    return result


def accepted_identity(row,expected=None):
    app=row.get('application',{})
    d=app.get('decoded')
    if not app.get('app_crc_ok') or not d:
        return None
    identity=(int(d['node_id']),int(d['sequence']))
    if expected is not None and identity[1] not in expected.get(str(identity[0]),[]):
        return None
    return identity


def source_identity(row):
    """Distinct physical payload identity, including its source capture/run."""
    app=row.get('application',{})
    d=app.get('decoded')
    if not app.get('app_crc_ok') or not d:
        return None
    return int(d['run_id']),int(d['node_id']),int(d['sequence'])


def probe(path_text,controls):
    path=ROOT/path_text
    report=load(path)
    key=path.parent.parent.name+'_'+path.stem
    cfg=cfg_for(report)
    w=weights(report)
    byid={c['candidate_id']:c for c in report['candidates']}
    selected={r['candidate_id'] for r in w if r['gate']}
    safe=[c['candidate_id'] for c in report['candidates']
          if c['start_sample']>=0 and c['start_sample']+cfg.frame_samples<=report['input']['analysis_slice']['samples_per_channel']]
    if safe and controls:
        selected.update(safe[i] for i in np.linspace(0,len(safe)-1,min(controls,len(safe)),dtype=int))
    weights_byid={r['candidate_id']:r for r in w}
    sl=report['input']['analysis_slice']
    samples=read_sc16(Path(report['input']['iq']),start_sample_per_channel=round(sl['start_time_s']*cfg.sample_rate_hz),
        max_samples_per_channel=int(sl['samples_per_channel']))
    cal=report['calibration']
    W=np.asarray([[complex(*v) for v in row] for row in cal['whitener']])
    dc=np.asarray([complex(*v) for v in cal['dc']])
    white=(W@(samples.astype(np.complex128)-dc[:,None])).astype(np.complex64)
    del samples
    decoded={}
    diagnostics=[]
    for cid in sorted(selected):
        candidate=byid[cid]
        est=dict(candidate,channel=candidate['channel_sp'],
            cfo_bins_sp=candidate.get('continuous_cfo_bins',candidate['cfo_bins']),
            sto_samples_sp=candidate.get('sto_samples',0.))
        args=dict(max_sync_trials=int(report['decoder'].get('sp_sync_max_trials',32)),
            sync_retry_policy=report['decoder'].get('sp_sync_retry_policy','strict_header'),
            relaxed_sync_max_trials=int(report['decoder'].get('sp_sync_relaxed_max_trials',8)))
        before=time.perf_counter()
        old=next(r for r in decode_sp_stages(white,est,cfg,**args) if r['method']=='sp_sync_refine')
        old=identify(report,old)
        cached=method(candidate)
        match=(old['symbol_bins']==cached['symbol_bins'] and old['phy']['phy_crc_ok']==cached['phy']['phy_crc_ok']
               and old['application']['app_crc_ok']==cached['application']['app_crc_ok'])
        if not match:
            write_json(OUT/'probes'/(key+'_mismatch.json'),dict(candidate_id=cid,estimate=est,recomputed=old,cached=cached))
            raise ValueError(f'{key} candidate {cid}: old decode does not reproduce; see mismatch diagnostic')
        old_seconds=time.perf_counter()-before
        new=old
        new_seconds=0.
        if weights_byid[cid]['changed']:
            trial=dict(est,lambda_sp=weights_byid[cid]['new_lambda'])
            before=time.perf_counter()
            new=next(r for r in decode_sp_stages(white,trial,cfg,**args) if r['method']=='sp_sync_refine')
            new=identify(report,new)
            new_seconds=time.perf_counter()-before
        decoded[cid]=new
        diagnostics.append(dict(**weights_byid[cid],baseline_reproduced=True,
            old_identity=accepted_identity(old),new_identity=accepted_identity(new),
            old_phy_crc=bool(old['phy']['phy_crc_ok']),new_phy_crc=bool(new['phy']['phy_crc_ok']),
            old_seconds=old_seconds,new_seconds=new_seconds,
            old_trials=old.get('synchronization_trials'),new_trials=new.get('synchronization_trials')))
        print(f'{key} candidate={cid} lambda={est["lambda_sp"]:.4g}->{weights_byid[cid]["new_lambda"]:.4g} '
              f'identity={accepted_identity(old)}->{accepted_identity(new)}',flush=True)
    expected=report['input'].get('planned_prr_window',{}).get('expected_sequences_by_node')
    old_set={i for c in report['candidates'] if (i:=accepted_identity(method(c),expected)) is not None}
    new_set={i for c in report['candidates'] if (i:=accepted_identity(decoded.get(c['candidate_id'],method(c)),expected)) is not None}
    old_source_set={i for c in report['candidates'] if (i:=source_identity(method(c))) is not None}
    new_source_set={i for c in report['candidates'] if (i:=source_identity(decoded.get(c['candidate_id'],method(c)))) is not None}
    metric=report['planned_crc_delivery_and_tps']['by_method']['sp_sync_refine']
    planned=int(metric['expected_tx_count'])
    denominator=min(planned,len(report['candidates']))
    result=dict(report=path_text,run=path.stem,window_s=sl['requested_duration_s'],
        sf=cfg.sf,bw_hz=cfg.bw_hz,nodes=len(report['active_nodes']),
        candidates=len(w),gate=sum(r['gate'] for r in w),changed=sum(r['changed'] for r in w),
        decoded_probes=len(diagnostics),old_unique=len(old_set),new_unique=len(new_set),
        old_prr=len(old_set)/denominator,new_prr=len(new_set)/denominator,denominator=denominator,
        reported_old_successes=metric['accepted_success_count'],
        old_source_unique=len(old_source_set),new_source_unique=len(new_source_set),
        source_rescued=[list(i) for i in sorted(new_source_set-old_source_set)],
        source_lost=[list(i) for i in sorted(old_source_set-new_source_set)],
        rescued=[list(i) for i in sorted(new_set-old_set)],lost=[list(i) for i in sorted(old_set-new_set)],
        diagnostics=diagnostics,new_results={str(k):v for k,v in decoded.items()},
        scope='Frozen candidate/channel/sync/calibration; all changed weights decoded, unchanged outputs reused; diagnostic concurrent timings are not a full latency benchmark')
    assert len(old_set)==metric['accepted_success_count'],('denominator/filter mismatch',key,len(old_set),metric['accepted_success_count'])
    write_json(OUT/'probes'/(key+'.json'),result)
    return {k:v for k,v in result.items() if k not in ('diagnostics','new_results')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-only',action='store_true')
    parser.add_argument('--report',action='append',default=[])
    parser.add_argument('--controls',type=int,default=3)
    parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    if not args.report:
        audit()
        return
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(probe,path,args.controls) for path in args.report]
        for future in as_completed(futures):
            print(json.dumps(future.result()),flush=True)


if __name__=='__main__':
    main()
