#!/usr/bin/env python3
"""Blind-acquisition diagnostics and serial latency measurements for the revision."""
from pathlib import Path
import sys,os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import argparse,json,time,copy,platform
import numpy as np
from concurrent.futures import ProcessPoolExecutor,as_completed
from real_collision_experiment.paper_experiments import run_compact_revision_20261106 as c
b=c.b;OUT=c.OUT

def blind(spec):
    path=OUT/'blind_jobs'/(c.key(spec)+'.json')
    if path.exists():return 'cached'
    t=time.perf_counter();samples,truth,noise=b.synthesize(spec);cfg=b.n.CFG
    prepared=b.n.a.prepare_receiver_inputs(samples,cfg,max_candidates=24,candidates_per_window=16,
        threshold=3.,cfo_min=-40.,cfo_max=8.,sp_scan_phase_count=8)
    white,physical=prepared['white'],prepared['physical'];es=prepared['estimates']['mrc']
    _,W,_,_=b.n.a.dc_remove_and_whiten(samples,noise_samples=max(128,round(.75*cfg.samples_per_symbol)))
    configured=b.attach_sp_reliability_and_lambda(white,es,cfg,noise_sigma2=prepared['noise_sigma2_fft'],
        gamma=.05,reference_guard=True,physical_samples=physical,whitener=W,multiuser_lambda_cap=4.)
    front_seconds=time.perf_counter()-t
    results={m:[] for m in ('sp_core','sp_sync_refine','mrc')}
    ctx=b.PaperComparisonContext(physical,es,cfg,frontend_method='mrc')
    for u,e in enumerate(configured):
        stages=b.n.a.decode_sp_stages(white,e,cfg,max_sync_trials=32)
        for method in ('sp_core','sp_sync_refine'):results[method].append(next(r for r in stages if r['method']==method))
        results['mrc'].append(ctx.decode_mrc(es[u]))
    assignment=b.n.a.assign_tracks(es,truth,cfg)
    targets=[]
    for u,target in enumerate(truth):
        j=assignment.get(u)
        delivered={m:any(r['phy'].get('phy_crc_ok',False) and r['phy'].get('payload_hex')==target['payload_hex'] for r in rows) for m,rows in results.items()}
        targets.append(dict(target=u,source_index=target['source_index'],track_matched=j is not None,
            reference_error_deg=(b.n.a.angle_deg(b.n.a.complex_pairs(configured[j]['channel_sp']),W@b.CHANNELS[target['source_index']]) if j is not None else None),
            delivered=delivered))
    c.write(path,dict(spec=spec,targets=targets,candidate_count=len(es),frontend=prepared['native_diagnostics']['sp_detection'],
        frontend_seconds=front_seconds,elapsed_seconds=time.perf_counter()-t,
        scoring='unique CRC-valid exact payload matches / all transmitted targets; detection matches use offline start/CFO gates only',
        controlled_truth_not_passed_to_frontend=True,noise_budget=noise))
    return 'done'

def run_blind(workers,calibration=False):
    b.initialize();m=json.loads((OUT/'manifest_main.json').read_text())
    original=json.loads((b.OUT/'manifest.json').read_text());specs=[]
    for k in (2,4,6):
        for repeat in range(4):
            base=next(s for s in original['jobs'] if s['family']=='temporal' and s['k']==k and s['repeat']==repeat and s['width_ratio']==.05)
            for span in (0.,.1,.5,1.,2.):
                for snr in (m['s0'],m['s_good']):
                    s=copy.deepcopy(base);s.update(family='blind',width_ratio=span/b.n.CFG.payload_symbol_count,
                        snr_db=snr,span_symbols=span,seed=66300000+repeat+k*100)
                    specs.append(s)
    if calibration:
        specs=[c.base('blind_calibration',[source],0,66400000+source,snr) for source in sorted(b.CHANNELS) for snr in (m['s0'],m['s_good'])]
        for s in specs:s['span_symbols']=0.
    c.write(OUT/('manifest_blind_calibration.json' if calibration else 'manifest_blind.json'),dict(specs=specs,repeats=1 if calibration else 4,
        scope='Native-IQ mixtures passed to actual anonymous SP acquisition; all methods share detected sync; small fixed-pool diagnostic, not independent native frontends or deployment evidence'))
    with ProcessPoolExecutor(max_workers=workers,initializer=b.initialize) as pool:
        fs=[pool.submit(blind,s) for s in specs]
        for i,f in enumerate(as_completed(fs),1):
            f.result()
            if i%5==0 or i==len(fs):print(f'BLIND {i}/{len(fs)}',flush=True)

def timing():
    b.initialize();original=json.loads((b.OUT/'manifest.json').read_text());rows=[]
    for k in b.KS:
        specs=[s for s in original['jobs'] if s['family']=='temporal' and s['k']==k and s['width_ratio']==.05 and s['repeat']<8]
        for s in specs:
            samples,truth,noise=b.synthesize(s);physical,white,es,sigma,W,_=b.n.a.controlled_inputs(samples,truth,b.n.CFG)
            for offset in range(4):
                method=c.METHODS[(offset+s['repeat'])%4]
                start=time.perf_counter_ns()
                if method=='sp':
                    configured=b.attach_sp_reliability_and_lambda(white,es,b.n.CFG,noise_sigma2=sigma,gamma=.05,
                        reference_guard=True,physical_samples=physical,whitener=W,multiuser_lambda_cap=4.)
                    configuration_ms=(time.perf_counter_ns()-start)/1e6
                    for e in configured:
                        bins=b.n.a.projected_decisions(white,e,b.n.CFG)[0]
                        b.n.a.decode_payload_from_symbol_bins(bins,b.n.CFG)
                else:
                    ctx=c.CertifiedContext(physical,es,b.n.CFG,frontend_method=method)
                    configuration_ms=(time.perf_counter_ns()-start)/1e6
                    for e in es:getattr(ctx,'decode_'+method)(e)
                elapsed=(time.perf_counter_ns()-start)/1e6
                rows.append(dict(k=k,repeat=s['repeat'],method=method,milliseconds_per_burst=elapsed,
                    configuration_ms=configuration_ms,warmup=s['repeat']==0,targets=k))
            print(f'TIMING K={k} repeat={s["repeat"]}',flush=True)
    c.write(OUT/'timing.json',dict(rows=rows,platform=platform.platform(),processor=platform.processor(),
        threads=1,scope='Serial receiver parameter estimation + all K payload FFT/FEC/CRC, including failed targets; common DC/whitening/acquisition excluded. New context per method; no cross-method FFT cache; first repeat per K is warmup. Not a real-time throughput claim.'))

def controlled_blind(spec):
    path=OUT/'blind_controlled_jobs'/(c.key(spec)+'.json')
    if path.exists():return
    samples,truth,noise=b.synthesize(spec);cfg=b.n.CFG
    old=json.loads((OUT/'blind_jobs'/(c.key(spec)+'.json')).read_text())
    assert old['noise_budget']==noise
    white,W,sigma,cal=b.n.a.dc_remove_and_whiten(samples,noise_samples=max(128,round(.75*cfg.samples_per_symbol)))
    physical=np.asarray(samples-b.n.a.complex_pairs(cal['dc'])[:,None],dtype=np.complex64)
    es=[dict(start_sample=t['start_sample'],cfo_bins=t['cfo_bins'],continuous_cfo_bins=t['cfo_bins'],sto_samples=0.,channel=[[0.,0.],[0.,0.]]) for t in truth]
    configured=b.attach_sp_reliability_and_lambda(white,es,cfg,noise_sigma2=cfg.m*sigma,gamma=.05,reference_guard=True,physical_samples=physical,whitener=W,multiuser_lambda_cap=4.)
    cache=b.IntegerPayloadCache();ctx=c.CertifiedContext(physical,es,cfg,frontend_method='mrc',payload_spectrum_cache=cache);targets=[]
    for u,e in enumerate(configured):
        sp,_=c.sp_bins(physical,W,e,cache);mrc=ctx.decode_mrc(es[u])['symbol_bins']
        if spec['repeat']==0:assert sp==b.n.a.projected_decisions(white,e,cfg)[0]
        targets.append(dict(target=u,sp=b.n.h.payload_metric(sp,truth[u],cfg),mrc=b.n.h.payload_metric(mrc,truth[u],cfg)))
    c.write(path,dict(spec=spec,targets=targets,scope='Same mixture and same noise/DC/whitening prefix as blind replay; only acquisition replaced by known start and isolated-calibrated CFO, refs still mixed-preamble estimates.'))

def run_controlled(workers):
    m=json.loads((OUT/'manifest_blind.json').read_text())
    with ProcessPoolExecutor(max_workers=workers,initializer=b.initialize) as pool:
        fs=[pool.submit(controlled_blind,s) for s in m['specs']]
        for i,f in enumerate(as_completed(fs),1):
            f.result()
            if i%20==0 or i==len(fs):print(f'BLIND MATCHED CONTROL {i}/{len(fs)}',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['blind','blind_calibration','blind_controlled','timing']);ap.add_argument('--workers',type=int,default=2);args=ap.parse_args()
    if args.stage=='blind_controlled':run_controlled(args.workers)
    elif args.stage.startswith('blind'):run_blind(args.workers,calibration=args.stage=='blind_calibration')
    else:timing()
