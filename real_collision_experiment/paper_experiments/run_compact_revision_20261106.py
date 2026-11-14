#!/usr/bin/env python3
"""Frozen native-IQ rerun for the compact paper revision; production algorithms unchanged."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
os.environ.setdefault('MPLCONFIGDIR','/tmp/compact_revision_mpl')
from pathlib import Path
import sys,json,time,hashlib,argparse,copy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from concurrent.futures import ProcessPoolExecutor,as_completed
from real_collision_experiment.paper_experiments import run_boundary_fairness as b
from real_collision_experiment.paper_experiments.replay_boundary_certified_candidates import CertifiedContext

OUT=ROOT/'real_usrp_outputs/compact_revision_20261106'
METHODS=('sp','mrc','pcube','maloragw')
PILOT_SNRS=list(range(-26,5,3))
REPEATS=100

def write(path,obj): b.n.a.write_json(path,obj)
def key(spec): return b.n.a.job_key(spec)

def sp_bins(physical,W,e,cache):
    cfg=b.n.CFG
    f=np.asarray([cache.spectra_for(physical,e,cfg,j) for j in range(cfg.payload_symbol_count)])
    fw=np.einsum('ab,sbk->sak',W,f)
    h=b.n.a.complex_pairs(e.get('mrc_decision_channel_sp',e['channel_sp']) if e['lambda_sp']==0 else e['channel_sp']);h/=np.linalg.norm(h)
    o=np.array([-np.conj(h[1]),np.conj(h[0])])
    p=abs(np.einsum('a,sak->sk',h.conj(),fw))**2
    q=abs(np.einsum('a,sak->sk',o.conj(),fw))**2
    return np.argmax(p-e['lambda_sp']*q,axis=1).tolist(),f

def reference_rows(physical,estimate,truth,cfg,cache):
    h=b.physical_preamble_measurements(physical,estimate,cfg)[0]
    rows=[]
    for j,bin_value in enumerate(truth['symbol_bins']):
        f=cache.spectra_for(physical,estimate,cfg,j)
        rows.append(dict(symbol=j,delta_deg=b.n.a.angle_deg(h,f[:,bin_value])))
    return rows

def run(spec):
    path=OUT/'jobs'/(key(spec)+'.json')
    if path.exists(): return 'cached'
    t=time.perf_counter();samples,truth,noise=b.synthesize(spec)
    physical,white,es,sigma,W,cal=b.n.a.controlled_inputs(samples,truth,b.n.CFG)
    physical=np.asarray(physical,dtype=np.complex64);cache=b.IntegerPayloadCache()
    if spec['family']=='pilot':
        ctx=CertifiedContext(physical,es,b.n.CFG,frontend_method='mrc',payload_spectrum_cache=cache)
        bins=ctx.decode_mrc(es[0])['symbol_bins']
        metrics={'mrc':b.n.h.payload_metric(bins,truth[0],b.n.CFG)}
        result=dict(spec=spec,metrics=metrics,reference=reference_rows(physical,es[0],truth[0],b.n.CFG,cache))
    else:
        configured=b.attach_sp_reliability_and_lambda(white,es,b.n.CFG,noise_sigma2=sigma,gamma=.05,
            reference_guard=True,physical_samples=physical,whitener=W,multiuser_lambda_cap=4.)
        e=configured[0];bins,_=sp_bins(physical,W,e,cache)
        metrics={'sp':b.n.h.payload_metric(bins,truth[0],b.n.CFG)}
        contexts={m:CertifiedContext(physical,es,b.n.CFG,frontend_method=m,payload_spectrum_cache=cache) for m in METHODS[1:]}
        for m,c in contexts.items():
            bb=getattr(c,'decode_'+m)(es[0])['symbol_bins'];metrics[m]=b.n.h.payload_metric(bb,truth[0],b.n.CFG)
            if m=='mrc' and e['lambda_sp']==0: assert bins==bb
        if spec['repeat']==0: assert bins==b.n.a.projected_decisions(white,e,b.n.CFG)[0]
        result=dict(spec=spec,metrics=metrics,lambda_sp=e['lambda_sp'],guard=e.get('lambda_guard_reason_sp'),
            estimate=e,physical_angle=b.n.a.angle_deg(b.CHANNELS[spec['sources'][0]],b.CHANNELS[spec['sources'][1]]),
            reference=reference_rows(physical,es[0],truth[0],b.n.CFG,cache))
    result.update(noise_budget=noise,elapsed_seconds=time.perf_counter()-t)
    write(path,result)
    return 'done'

def base(family,sources,repeat,seed,snr,sir=0.):
    rng=np.random.default_rng(seed);k=len(sources)
    return dict(family=family,k=k,width_ratio=(.2/b.n.CFG.payload_symbol_count if k>1 else 0.),
        repeat=repeat,seed=seed,sources=sources,relative_offsets=([0.,1.] if k==2 else [0.]),
        powers=[1.]+[10**(-sir/10)]*(k-1),phases=rng.uniform(-np.pi,np.pi,k).tolist(),
        snr_db=float(snr),individual_sir_db=float(sir),focus=[0])

def prepare_pilot():
    b.initialize();specs=[]
    for source in sorted(b.CHANNELS):
        for repeat in range(4):
            for snr in PILOT_SNRS: specs.append(base('pilot',[source],repeat,66100000+source*100+repeat,snr))
    write(OUT/'manifest_pilot.json',dict(specs=specs,rule='All 22 intact source packets, four repeats each; same sources/phases/noise draws paired across SNR'))

def prepare_main():
    b.initialize();pilot=json.loads((OUT/'manifest_pilot.json').read_text());stats=[]
    for snr in PILOT_SNRS:
        rows=[json.loads((OUT/'jobs'/(key(s)+'.json')).read_text()) for s in pilot['specs'] if s['snr_db']==snr]
        stats.append(dict(snr=snr,n=len(rows),pdr=np.mean([r['metrics']['mrc']['delivered'] for r in rows])))
    s0=next(r['snr'] for r in stats if r['pdr']>=.9)
    good=next(r['snr'] for r in stats if r['snr']>=s0+6 and r['pdr']>=.99)
    snrs=[s0+d for d in (-6,-3,0,3,6)];maxsnr=max(good,max(snrs))
    cov={}
    for u in b.CHANNELS:
        row=b.n.AUDIT['packets'][u]
        cov[u]=np.array([[complex(*v) for v in line] for line in row['covariance']])*2/row['signal_vector_power']
    pools={};coverage=[]
    for low,high in b.BINS:
        pool=[]
        for u in sorted(b.CHANNELS):
            for v in sorted(b.CHANNELS):
                if b.POSITIONS[u]==b.POSITIONS[v]:continue
                angle=b.n.a.angle_deg(b.CHANNELS[u],b.CHANNELS[v])
                if low<=angle<high and np.linalg.eigvalsh(cov[u]+10*cov[v]).max()<=10**(-maxsnr/10):pool.append((u,v))
        pools[low]=pool
        coverage.append(dict(low=low,high=min(high,90),ordered_source_pairs=len(pool),physical_position_pairs=len({tuple(sorted((b.POSITIONS[u],b.POSITIONS[v]))) for u,v in pool})))
    specs=[]
    for family,lows,levels in [('snr',[20.],snrs),('angle',[z[0] for z in b.BINS],[good])]:
        for low in lows:
            pool=pools[low]
            if not pool:continue
            # Cycle actual target positions before source pairs; independent of outcomes.
            groups={p:[pair for pair in pool if b.POSITIONS[pair[0]]==p] for p in sorted({b.POSITIONS[u] for u,v in pool})}
            positions=list(groups)
            for repeat in range(REPEATS):
                choices=groups[positions[repeat%len(positions)]]
                u,v=choices[(repeat//len(positions))%len(choices)]
                seed=66200000+int(low)*1000+repeat
                for snr in levels:
                    for sir in (-10.,-5.,0.,5.):
                        spec=base(family,[u,v],repeat,seed,snr,sir)
                        spec.update(angle_low=low,angle_high=next(min(hi,90) for lo,hi in b.BINS if lo==low))
                        specs.append(spec)
    files=['run_compact_revision_20261106.py','run_boundary_fairness.py','run_native_iq_heatmaps.py','replay_boundary_certified_candidates.py']
    code={}
    for name in files:
        p=Path(__file__).with_name(name);code[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
        dst=OUT/'code_snapshot'/name;dst.parent.mkdir(exist_ok=True,parents=True);dst.write_bytes(p.read_bytes())
    for name in ['evaluate_sp_dechirp_real_pos.py','sp_reference_guard.py','sp_noise_competition.py','compare/real_packet_decoders.py']:
        p=ROOT/name;code[name]=hashlib.sha256(p.read_bytes()).hexdigest();dst=OUT/'code_snapshot'/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(p.read_bytes())
    write(OUT/'manifest_main.json',dict(specs=specs,pilot=stats,s0=s0,s_good=good,snrs=snrs,sirs=[-10,-5,0,5],coverage=coverage,repeats=REPEATS,code_sha256=code,
        scope='Native-IQ superposition, controlled known starts/calibrated CFO; references from mixed preambles; certified candidates for all methods; fixed development pool, not independent deployment confirmation'))
    print(json.dumps(dict(s0=s0,s_good=good,jobs=len(specs),coverage=coverage),indent=2),flush=True)

def execute(stage,workers):
    m=json.loads((OUT/f'manifest_{stage}.json').read_text());specs=m['specs'];started=time.perf_counter()
    todo=[s for s in specs if not (OUT/'jobs'/(key(s)+'.json')).exists()]
    print(f'{stage}: {len(todo)} missing / {len(specs)} frozen',flush=True)
    with ProcessPoolExecutor(max_workers=workers,initializer=b.initialize) as pool:
        futures=[pool.submit(run,s) for s in todo]
        for i,f in enumerate(as_completed(futures),1):
            f.result()
            if i%50==0 or i==len(todo):print(f'{stage} {i}/{len(todo)}, {time.perf_counter()-started:.0f}s',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['pilot','main']);ap.add_argument('--workers',type=int,default=4);args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.stage=='pilot':
        if not (OUT/'manifest_pilot.json').exists():prepare_pilot()
    else:
        if not (OUT/'manifest_main.json').exists():prepare_main()
    execute(args.stage,args.workers)
