#!/usr/bin/env python3
"""Extreme-condition bridge and matched-kernel timing; frozen receiver unchanged."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ.setdefault('MPLCONFIGDIR','/tmp/redesign_20261113_mpl')
from pathlib import Path
import sys,json,time,hashlib,argparse,copy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from concurrent.futures import ProcessPoolExecutor,as_completed
from real_collision_experiment.paper_experiments import run_compact_revision_20261106 as c
b=c.b
OUT=ROOT/'real_usrp_outputs/figure_redesign_20261113'

def initialize():b.initialize();c.OUT=OUT

def prepare_extreme():
    initialize();pool=[];cov={}
    for u in b.CHANNELS:
        r=b.n.AUDIT['packets'][u];cov[u]=np.array([[complex(*v) for v in row] for row in r['covariance']])*2/r['signal_vector_power']
    for u in sorted(b.CHANNELS):
        for v in sorted(b.CHANNELS):
            if b.POSITIONS[u]==b.POSITIONS[v]:continue
            angle=b.n.a.angle_deg(b.CHANNELS[u],b.CHANNELS[v])
            if 10<=angle<60 and np.linalg.eigvalsh(cov[u]+100*cov[v]).max()<=1:pool.append((u,v))
    assert pool
    groups={p:[pair for pair in pool if b.POSITIONS[pair[0]]==p] for p in sorted({b.POSITIONS[u] for u,v in pool})};positions=list(groups);specs=[]
    for repeat in range(100):
        choices=groups[positions[repeat%len(positions)]];u,v=choices[(repeat//len(positions))%len(choices)]
        for snr in (-10.,0.):
            for sir in (-20.,-10.,0.,10.):
                s=c.base('extreme',[u,v],repeat,71300000+repeat,snr,sir);s.update(angle_low=10.,angle_high=60.);specs.append(s)
    c.write(OUT/'manifest_extreme.json',dict(specs=specs,ordered_pairs=len(pool),physical_position_pairs=len({tuple(sorted((b.POSITIONS[u],b.POSITIONS[v]))) for u,v in pool}),
        rule='All source pairs with measured physical angle 10–60deg and PSD-feasible noise at SNR0/SIR-20; balanced target positions; all eight power cells paired; no decode-result filtering',
        scope='New measured-IQ replay at old extreme-grid settings; same guard-v2 as Nov6, 100 trials/cell, 0.2-symbol offset, no new air acquisition',
        algorithm_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('evaluate_sp_dechirp_real_pos.py','sp_reference_guard.py','compare/real_packet_decoders.py')}))

def extremes(workers):
    OUT.mkdir(parents=True,exist_ok=True)
    if not (OUT/'manifest_extreme.json').exists():prepare_extreme()
    m=json.loads((OUT/'manifest_extreme.json').read_text());todo=[s for s in m['specs'] if not (OUT/'jobs'/(c.key(s)+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=workers,initializer=initialize) as pool:
        fs=[pool.submit(c.run,s) for s in todo]
        for i,f in enumerate(as_completed(fs),1):
            f.result()
            if i%50==0 or i==len(fs):print(f'EXTREME {i}/{len(todo)}',flush=True)

def nested(workers,moderate=False):
    initialize();old=json.loads((b.OUT/'manifest.json').read_text());specs=[]
    low=20 if moderate else 40
    masters=[s for s in old['jobs'] if s['family']=='geometry' and s['k']==8 and s['angle_low']==low and s['individual_sir_db']==-5]
    assert len(masters)==32
    for master in masters:
        u=master['sources'][0]
        nearest=min(range(1,8),key=lambda i:b.n.a.angle_deg(b.CHANNELS[u],b.CHANNELS[master['sources'][i]]))
        order=[0,nearest,*[i for i in range(1,8) if i!=nearest]]
        for k in (2,4,6,8):
            s=copy.deepcopy(master);s.update(family='nested_moderate' if moderate else 'nested',k=k,master_job=c.key(master))
            for field in ('sources','relative_offsets','powers','phases'):s[field]=[master[field][i] for i in order[:k]]
            s['fixed_minimum_angle']=b.n.a.angle_deg(b.CHANNELS[u],b.CHANNELS[master['sources'][nearest]])
            specs.append(s)
    c.write(OUT/('manifest_nested_moderate.json' if moderate else 'manifest_nested.json'),dict(specs=specs,master_scenes=32,rule='Target and nearest interferer fixed across K; add other interferers from same eight-packet master. Source IQ, phases, absolute digital starts, individual powers and calibrated CFO retained. Noise budget compensated per mixture; a common seed does not assert identical noise arrays across K.',scope='Paired nested source/time/phase concurrency scan on a fixed measured source pool, not a universal collision-order capacity.'))
    todo=[s for s in specs if not (OUT/'jobs'/(c.key(s)+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=workers,initializer=initialize) as pool:
        fs=[pool.submit(c.run,s) for s in todo]
        for i,f in enumerate(as_completed(fs),1):
            f.result()
            if i%20==0 or i==len(fs):print(f'NESTED {i}/{len(todo)}',flush=True)

def coefficients(e,W):
    h=b.n.a.complex_pairs(e.get('mrc_decision_channel_sp',e['channel_sp']) if e['lambda_sp']==0 else e['channel_sp']);h/=np.linalg.norm(h)
    orth=np.array([-np.conj(h[1]),np.conj(h[0])])
    return W.conj().T@h,W.conj().T@orth,float(e['lambda_sp'])

def decide(f,coeff):
    h,orth,lam=coeff
    p=abs(np.einsum('a,sak->sk',h.conj(),f))**2
    if lam!=0:p-=lam*abs(np.einsum('a,sak->sk',orth.conj(),f))**2
    return np.argmax(p,axis=1).tolist()

def timing():
    initialize();manifest=json.loads((b.OUT/'manifest.json').read_text());records=[];parity=0
    for k in b.KS:
        for repeat in range(8):
            spec=next(s for s in manifest['jobs'] if s['family']=='temporal' and s['k']==k and s['repeat']==repeat and s['width_ratio']==.05)
            raw,truth,_=b.synthesize(spec);physical_raw,white,es,sigma,W,_=b.n.a.controlled_inputs(raw,truth,b.n.CFG)
            physical=np.asarray(physical_raw,dtype=np.complex64)
            old=json.loads((b.OUT/'jobs'/(c.key(spec)+'.json')).read_text())
            per={};spectra=None
            for method in (('mrc','sp') if repeat%2==0 else ('sp','mrc')):
                t=time.perf_counter_ns()
                if method=='sp':
                    configured=b.attach_sp_reliability_and_lambda(white,es,b.n.CFG,noise_sigma2=sigma,gamma=.05,reference_guard=True,physical_samples=physical_raw,whitener=W,multiuser_lambda_cap=4.)
                    coeffs=[coefficients(e,W) for e in configured]
                else:
                    channels=[b.physical_preamble_measurements(physical,e,b.n.CFG)[0] for e in es]
                    coeffs=[(h/np.linalg.norm(h),None,0.) for h in channels]
                configuration_ms=(time.perf_counter_ns()-t)/1e6
                cache=b.IntegerPayloadCache();fft_ms=score_ms=phy_ms=0.;arrays=[]
                for u,e in enumerate(es):
                    t=time.perf_counter_ns();f=np.asarray([cache.spectra_for(physical,e,b.n.CFG,j) for j in range(b.n.CFG.payload_symbol_count)]);fft_ms+=(time.perf_counter_ns()-t)/1e6;arrays.append(f)
                    t=time.perf_counter_ns();bins=decide(f,coeffs[u]);score_ms+=(time.perf_counter_ns()-t)/1e6
                    t=time.perf_counter_ns();decoded=b.n.a.decode_payload_from_symbol_bins(bins,b.n.CFG);phy_ms+=(time.perf_counter_ns()-t)/1e6
                    target=next(r for r in old['targets'] if r['target_index']==u)
                    metric=b.n.h.payload_metric(bins,truth[u],b.n.CFG)
                    assert metric['delivered']==target['methods'][method]['delivered'] and metric['ser']==target['methods'][method]['ser']
                    if method=='sp':assert bins==b.n.a.projected_decisions(white,configured[u],b.n.CFG)[0]
                    parity+=1
                # Shared FFT arrays, shared argmax and identical outputs: decision-only repeat test.
                warm=[decide(f,co) for f,co in zip(arrays,coeffs)]
                micro=[]
                for q in range(21):
                    t=time.perf_counter_ns()
                    for f,co in zip(arrays,coeffs):decide(f,co)
                    micro.append((time.perf_counter_ns()-t)/1e6)
                per[method]=dict(configuration_ms=configuration_ms,fft_ms=fft_ms,score_ms=score_ms,phy_ms=phy_ms,
                    total_ms=configuration_ms+fft_ms+score_ms+phy_ms,micro_ms=float(np.median(micro[1:])),nonzero_weights=sum(co[2]!=0 for co in coeffs),cache=cache.audit())
            records.append(dict(k=k,repeat=repeat,warmup=repeat==0,targets=k,methods=per))
            print(f'MATCHED TIMING K={k} repeat={repeat}',flush=True)
    c.write(OUT/'timing_matched.json',dict(records=records,verified_packet_method_results=parity,
        identical_payload_kernel=True,identical_fft_cache=True,identical_crc_decoder=True,
        scope='Actual mixed-preamble configuration retained per method; identical per-target physical FFT extraction and identical score/argmax/PHY wrapper; no top2-margin or alias-group diagnostics charged only to MRC. Decision-only microbenchmark uses fixed FFT and coefficient inputs. Not a proof of asymptotic full-receiver speed.'))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['extreme','nested','nested_moderate','timing']);ap.add_argument('--workers',type=int,default=4);args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.stage=='extreme':extremes(args.workers)
    elif args.stage=='nested':nested(args.workers)
    elif args.stage=='nested_moderate':nested(args.workers,moderate=True)
    else:timing()
