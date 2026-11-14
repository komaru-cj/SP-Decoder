#!/usr/bin/env python3
"""Frozen native-IQ collision limits: no waveform regeneration or result selection."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'real_collision_experiment/node01_sp_receiver'))
import argparse,hashlib,json,itertools,time,copy
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
from compare.mrc_input import physical_preamble_measurements
from compare.real_packet_decoders import PaperComparisonContext,PhysicalEvidencePayloadCache,DEFAULT_PCUBE_POLICY,_payload_parameters_key,_physical_mixed
from lora_mrc_sp_core import instantaneous_chirp
from real_collision_experiment.paper_experiments import run_native_iq_heatmaps as n
from evaluate_sp_dechirp_real_pos import attach_sp_reliability_and_lambda

OUT=ROOT/'real_usrp_outputs/collision_boundary_fairness_20261102'
KS=(2,4,6,8,10)
WIDTHS=(2.,1.,.5,.25,.05,.01)
BINS=((0.,2.),(2.,5.),(5.,10.),(10.,20.),(20.,40.),(40.,90.000001))
LAMBDAS=(0.,.125,.25,.5,.75,1.,1.5,2.,3.,4.,6.,8.,12.,16.,24.,32.,40.)
METHODS=('sp','mrc','pcube','maloragw')
CAL=None;GROUPS=None;CHANNELS=None;POSITIONS=None


class IntegerPayloadCache(PhysicalEvidencePayloadCache):
    """Exact integer-window specialization; noninteger hypotheses use the receiver."""
    def mixed_for(self,samples,est,cfg,symbol_index):
        start=float(est['start_sample'])+(cfg.payload_start_symbols+symbol_index)*cfg.samples_per_symbol
        start+=float(est.get('sto_samples_sp',est.get('sto_samples',0.)))
        if start!=int(start) or start<0 or start+cfg.samples_per_symbol>samples.shape[1]:
            return super().mixed_for(samples,est,cfg,symbol_index)
        key=(id(samples),*_payload_parameters_key(est,cfg,symbol_index))
        if key in self.mixed:self.mixed_hits+=1;return self.mixed[key]
        self.mixed_misses+=1
        cfo=float(est.get('cfo_bins_sp',est.get('continuous_cfo_bins',est['cfo_bins'])))
        if not hasattr(self,'carriers'):self.carriers={};self.down=instantaneous_chirp(0,cfg,up=False)
        if cfo not in self.carriers:
            self.carriers[cfo]=np.exp(-1j*2*np.pi*cfo*np.arange(cfg.samples_per_symbol)/cfg.samples_per_symbol).astype(np.complex64)
        value=(samples[:,int(start):int(start)+cfg.samples_per_symbol]*self.carriers[cfo][None,:])*self.down[None,:]
        self.mixed[key]=value
        return value


def initialize():
    global CAL,GROUPS,CHANNELS,POSITIONS
    n.initialize()
    CAL=json.loads((OUT/'calibration.json').read_text())
    CHANNELS={int(r['index']):n.a.complex_pairs(r['physical_channel']) for r in CAL['sources']}
    POSITIONS={int(r['index']):r['position'] for r in CAL['sources']}
    GROUPS=defaultdict(list)
    for r in CAL['sources']:GROUPS[r['position']].append(r['index'])


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def overlap_summary(starts,cfg,u):
    starts=np.asarray(starts,dtype=float)
    left=starts[u]+cfg.payload_start_symbols*cfg.samples_per_symbol
    right=starts[u]+cfg.frame_samples
    duration=right-left
    overlap=np.maximum(0.,np.minimum(right,starts+cfg.frame_samples)-np.maximum(left,starts))
    active=[int(v) for v in range(len(starts)) if v!=u and overlap[v]>0]
    points=sorted({left,right,*[float(t) for t in starts if left<t<right],
                   *[float(t+cfg.frame_samples) for t in starts if left<t+cfg.frame_samples<right]})
    peak=max(int(np.sum((starts<=((a+b)/2))&(starts+cfg.frame_samples>((a+b)/2)))) for a,b in zip(points[:-1],points[1:]))
    return dict(mean_concurrency=float(overlap.sum()/duration),peak_concurrency=peak,
        overlapping_indices=active,mean_interferer_overlap_fraction=float((overlap.sum()-duration)/max(1,len(active))/duration))


def synthesize(spec):
    cfg=n.CFG;rng=np.random.default_rng(spec['seed']);selected=spec['sources'];k=len(selected)
    offsets=np.array(spec['relative_offsets']);w=spec['width_ratio']*cfg.payload_symbol_count
    starts=np.rint((3+offsets*w)*cfg.samples_per_symbol).astype(int)
    powers=np.asarray(spec['powers']);phases=np.asarray(spec['phases'])
    length=int(max(starts)+cfg.frame_samples+3*cfg.samples_per_symbol)
    samples=np.zeros((2,length),np.complex64);truth=[];cov=[]
    for i,(index,start,power,phase) in enumerate(zip(selected,starts,powers,phases)):
        row=n.AUDIT['packets'][index]
        scale=np.sqrt(2*power/row['signal_vector_power'])
        samples[:,start:start+cfg.frame_samples]+=(n.PACKETS[index]*(scale*np.exp(1j*phase))).astype(np.complex64)
        cov.append(np.array([[complex(*v) for v in rr] for rr in row['covariance']])*scale**2)
        truth.append(dict(source_index=index,position=POSITIONS[index],
            start_sample=float(start),cfo_bins=row['cfo_bins'],power_per_channel=float(power),
            payload_hex=row['payload_hex'],symbol_bins=row['symbol_bins'],scale=float(scale),phase=float(phase)))
    sigma=10**(-spec['snr_db']/10)
    points=sorted({0,length,*starts.tolist(),*(starts+cfg.frame_samples).tolist()});min_eig=sigma
    for left,right in zip(points[:-1],points[1:]):
        C=sum((c for start,c in zip(starts,cov) if start<=left<start+cfg.frame_samples),np.zeros((2,2),complex))
        values,V=np.linalg.eigh(sigma*np.eye(2)-C)
        min_eig=min(min_eig,float(values.min()))
        if values.min() < -1e-8*sigma:raise ValueError('infeasible retained source-noise budget')
        noise=(rng.normal(size=(2,right-left))+1j*rng.normal(size=(2,right-left)))/np.sqrt(2)
        samples[:,left:right]+=((V@np.diag(np.sqrt(np.maximum(values,0))))@noise).astype(np.complex64)
    return samples,truth,dict(variance=sigma,min_residual_eigenvalue=min_eig)


def prepare():
    OUT.mkdir(parents=True,exist_ok=True);n.initialize()
    sources=[]
    for row in n.AUDIT['packets']:
        if row.get('excluded'):continue
        index=row['index'];estimate=dict(start_sample=0.,cfo_bins=row['cfo_bins'])
        channel,_,_=physical_preamble_measurements(n.PACKETS[index],estimate,n.CFG)
        channel=channel/np.linalg.norm(channel)
        C=np.array([[complex(*v) for v in rr] for rr in row['covariance']])*2/row['signal_vector_power']
        sources.append(dict(index=index,position=n.a.source_bank()[index]['position'],physical_channel=n.a.pairs(channel),
            noise_eigenvalue=float(np.linalg.eigvalsh(C).max())))
    # Conservative bound over every one-source-per-position combination.
    worst=sum(max(r['noise_eigenvalue'] for r in sources if r['position']==p) for p in sorted({r['position'] for r in sources}))
    feasible=[s for s in (10.,5.,0.) if 10**(-s/10)>=worst*10**.5]
    if not feasible:raise ValueError('no common noise-feasible mechanism SNR')
    snr=feasible[0]
    calibration=dict(sources=sources,source_positions=10,included_source_packets=22,
        main_snr_db=snr,worst_case_embedded_noise_eigenvalue_upper_bound=worst,
        snr_rule='Highest of 10,5,0 dB feasible for every one-source-per-position combination including +5 dB interferers, before decoding',
        source_iq_sha256=sha(n.OUT/'aligned_source_iq.npz'),
        angle_coordinate='isolated measured physical two-Rx projective direction',
        geometry_not_exposed_to_receivers=True)
    n.a.write_json(OUT/'calibration.json',calibration);initialize()
    groups=GROUPS;positions=sorted(groups);jobs=[]
    # Paired master source/power/phase/relative-timing draws across K and timing.
    for repeat in range(128):
        rng=np.random.default_rng(2026110200+repeat)
        order=rng.permutation(positions).tolist()
        sources=[int(rng.choice(groups[p])) for p in order]
        phases=rng.uniform(-np.pi,np.pi,10).tolist()
        raw=rng.uniform(0,1,10)
        for k in KS:
            widths=WIDTHS if repeat<24 else ((2.,.25,.01) if k==10 else ())
            relative=(raw[:k]-min(raw[:k]))/np.ptp(raw[:k])
            for width in widths:
                jobs.append(dict(family='temporal',k=k,width_ratio=width,repeat=repeat,
                    seed=3700000+repeat,sources=sources[:k],relative_offsets=relative.tolist(),
                    powers=[1.]*k,phases=phases[:k],snr_db=snr,focus=list(range(k))))
    availability=[]
    for k in KS:
        for lo,hi in BINS:
            eligible=[]
            for u in sorted(CHANNELS):
                far=defaultdict(list);near=[]
                pos=POSITIONS[u]
                for v in sorted(CHANNELS):
                    vp=POSITIONS[v]
                    if vp==pos:continue
                    angle=n.a.angle_deg(CHANNELS[u],CHANNELS[v])
                    if angle>=lo:
                        far[vp].append(v)
                        if angle<hi:near.append(v)
                if len(far)>=k-1 and near:eligible.append((u,dict(far),near))
            availability.append(dict(k=k,angle_low=lo,angle_high=min(hi,90.),
                eligible_target_sources=len(eligible),eligible_target_positions=len({POSITIONS[u] for u,_,_ in eligible}),
                near_source_pairs=len({tuple(sorted((u,v))) for u,_,near in eligible for v in near})))
            if not eligible:continue
            # Cycle eligible positions, then source packets, before decoding.
            bypos=defaultdict(list)
            for item in eligible:bypos[POSITIONS[item[0]]].append(item)
            ep=sorted(bypos)
            for repeat in range(32):
                rng=np.random.default_rng(810000+repeat+int(lo)*1000+k*100000)
                item=bypos[ep[repeat%len(ep)]][(repeat//len(ep))%len(bypos[ep[repeat%len(ep)]])]
                u,far,near=item;v=int(rng.choice(near));vpos=POSITIONS[v]
                others=[p for p in sorted(far) if p!=vpos]
                chosen=[u,v]+[int(rng.choice(far[p])) for p in rng.choice(others,k-2,replace=False)]
                raw=rng.random(k);raw=(raw-raw.min())/np.ptp(raw)
                phases=rng.uniform(-np.pi,np.pi,k).tolist()
                for sir in (0.,-5.):
                    jobs.append(dict(family='geometry',k=k,angle_low=lo,angle_high=min(hi,90.),
                        individual_sir_db=sir,width_ratio=.05,repeat=repeat,seed=4100000+repeat+int(lo)*1000+k*100000,
                        sources=chosen,relative_offsets=raw.tolist(),powers=[1.]+[10**(-sir/10)]*(k-1),
                        phases=phases,snr_db=snr,focus=[0]))
    # Isolated-link baseline calibration, balanced across every retained trace.
    for row in CAL['sources']:
        for repeat in range(3):
            jobs.append(dict(family='isolated',k=1,width_ratio=0.,repeat=repeat,
                seed=5100000+row['index']*10+repeat,sources=[row['index']],relative_offsets=[0.],
                powers=[1.],phases=[.33*repeat],snr_db=snr,focus=[0]))
    files=[Path(__file__),Path(__file__).with_name('render_boundary_fairness.py')]
    files += [ROOT/f for f in ('evaluate_sp_dechirp_real_pos.py','sp_reference_guard.py','sp_noise_competition.py',
        'compare/real_packet_decoders.py','compare/PCube/soft_grouping.py','compare/mrc_input.py',
        'real_collision_experiment/node01_sp_receiver/lora_phy_decode.py',
        'real_collision_experiment/paper_experiments/run_native_iq_heatmaps.py',
        'real_collision_experiment/paper_experiments/run_revision_abc.py',
        'real_collision_experiment/paper_experiments/run_resubmission_heatmaps.py')]
    hashes={str(f.relative_to(ROOT)):sha(f) for f in files if f.exists()}
    revision=hashlib.sha256(json.dumps(dict(jobs=jobs,calibration=calibration,code=hashes),sort_keys=True).encode()).hexdigest()
    for name in hashes:
        dst=OUT/'code_snapshot'/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes((ROOT/name).read_bytes())
    manifest=dict(jobs=jobs,revision=revision,code_sha256=hashes,main_snr_db=snr,
        methods=METHODS,sp_policy=n.GUARDED_PAIR_POLICY,pcube_policy=DEFAULT_PCUBE_POLICY,
        lambda_grid=LAMBDAS,geometry_availability=availability,
        temporal_repeats=24,fairness_repeats_per_anchor=128,fairness_widths=[2.,.25,.01],
        geometry_repeats=32,source_pool='22 measured packets at 10 positions',
        sampling_frozen_before_decoding=True,power_policy='temporal: equal mean received power; geometry: per-interferer SIR 0 and -5 dB, paired; aggregate SIR recorded',
        evidence='offline superposition of measured IQ, not simultaneous-air capture',
        synchronization='exact controlled starts/CFO for all methods; references from mixed preambles',
        confidence_scope='Monte Carlo bursts conditional on a fixed measured trace pool; not deployment confidence',
        reliable_pdr_threshold=.9,all_figures_include_failed_packets=True)
    n.a.write_json(OUT/'manifest.json',manifest)
    print(json.dumps(dict(jobs=len(jobs),main_snr_db=snr,availability=availability),indent=2),flush=True)


def exact_interval(p,q,bins,cap):
    truth=np.asarray(bins);p0=p[np.arange(len(truth)),truth,None];q0=q[np.arange(len(truth)),truth,None]
    A=p0-p;B=q-q0
    mask=np.ones(A.shape,dtype=bool);mask[np.arange(len(truth)),truth]=False
    a=A[mask];b=B[mask]
    lower=max(0.,float(np.max(-a[b>0]/b[b>0],initial=-np.inf)))
    upper=min(cap,float(np.min(-a[b<0]/b[b<0],initial=np.inf)))
    feasible=not np.any((b==0)&(a<=0)) and upper>lower
    return dict(lower=lower,upper=upper,nonempty=bool(feasible))


def run_job(spec,revision):
    started=time.perf_counter();key=n.a.job_key(spec);path=OUT/'jobs'/f'{key}.json'
    if path.exists() and json.loads(path.read_text()).get('revision')==revision:return
    samples,truth,noise=synthesize(spec)
    physical,white,estimates,sigma,W,cal=n.a.controlled_inputs(samples,truth,n.CFG)
    configured=attach_sp_reliability_and_lambda(white,estimates,n.CFG,noise_sigma2=sigma,gamma=.05,
        reference_guard=True,physical_samples=physical,whitener=W,multiuser_lambda_cap=4.)
    physical=np.asarray(physical,dtype=np.complex64)
    cache=IntegerPayloadCache()
    contexts={m:PaperComparisonContext(physical,estimates,n.CFG,frontend_method=m,payload_spectrum_cache=cache)
              for m in ('mrc','pcube','maloragw')}
    targets=[]
    for u in spec['focus']:
        target=truth[u];e=configured[u]
        decoded={m:getattr(c,'decode_'+m)(estimates[u])['symbol_bins'] for m,c in contexts.items()}
        spectra=np.asarray([cache.spectra_for(physical,e,n.CFG,s) for s in range(n.CFG.payload_symbol_count)])
        whitened=np.einsum('ab,sbk->sak',W,spectra)
        h=n.a.complex_pairs(e['channel_sp']);h=h/max(np.linalg.norm(h),1e-30)
        orth=np.array([-np.conj(h[1]),np.conj(h[0])])
        p=abs(np.einsum('a,sak->sk',h.conj(),whitened))**2
        q=abs(np.einsum('a,sak->sk',orth.conj(),whitened))**2
        lam=e['lambda_sp']
        if lam==0 and 'mrc_decision_channel_sp' in e:
            mh=n.a.complex_pairs(e['mrc_decision_channel_sp']);mh/=max(np.linalg.norm(mh),1e-30)
            spbins=np.argmax(abs(np.einsum('a,sak->sk',mh.conj(),whitened))**2,axis=1).tolist()
        else:spbins=np.argmax(p-lam*q,axis=1).tolist()
        decoded['sp']=spbins
        metrics={m:n.h.payload_metric(b,target,n.CFG) for m,b in decoded.items()}
        # Verify algebra/cache implementation against the unmodified receiver.
        if spec['repeat']==0:
            assert np.array_equal(cache.mixed_for(physical,estimates[u],n.CFG,0),_physical_mixed(physical,estimates[u],n.CFG,0))
            original=n.a.projected_decisions(white,e,n.CFG)[0]
            assert original==spbins,'cached linear whitening must reproduce production SP bins'
        overlap=overlap_summary([t['start_sample'] for t in truth],n.CFG,u)
        active=overlap.pop('overlapping_indices')
        angles=[n.a.angle_deg(CHANNELS[target['source_index']],CHANNELS[truth[v]['source_index']]) for v in active]
        active_angle=min(angles) if angles else None
        if spec['family']=='geometry':assert spec['angle_low']<=active_angle<spec['angle_high']
        competitors=sum(truth[v]['power_per_channel'] for v in active)
        diagnostic=[]
        reference_cap=max(0.,(e['L_u']-.05)/max(1-e['L_u'],1e-12))
        diagnostic_cap=min(40.,reference_cap)
        # Diagnostic every geometry focus and one prespecified temporal target.
        if spec['family']=='geometry' or (spec['family']=='temporal' and u==spec['repeat']%spec['k'] and spec['repeat']<24):
            for value in LAMBDAS:
                if value>diagnostic_cap+1e-9:
                    diagnostic.append(dict(lambda_value=value,admissible=False,delivered=None,ser=None));continue
                bins=decoded['mrc'] if value==0 else np.argmax(p-value*q,axis=1).tolist()
                result=n.h.payload_metric(bins,target,n.CFG)
                diagnostic.append(dict(lambda_value=value,admissible=True,delivered=result['delivered'],ser=result['ser']))
        # Offline clean-reference diagnostic on exactly the same payload observation.
        ch=W@CHANNELS[target['source_index']];ch/=np.linalg.norm(ch)
        bh=np.array([-np.conj(ch[1]),np.conj(ch[0])])
        cp=abs(np.einsum('a,sak->sk',ch.conj(),whitened))**2
        cq=abs(np.einsum('a,sak->sk',bh.conj(),whitened))**2
        clean_mrc=n.h.payload_metric(np.argmax(cp,axis=1).tolist(),target,n.CFG)
        best_clean=clean_mrc['delivered']
        for value in LAMBDAS[1:]:
            if best_clean:break
            best_clean=n.h.payload_metric(np.argmax(cp-value*cq,axis=1).tolist(),target,n.CFG)['delivered']
        row=dict(target_index=u,source_index=target['source_index'],position=target['position'],
            active_min_angle_deg=active_angle,active_competitors=len(active),**overlap,
            aggregate_sir_db=float(10*np.log10(target['power_per_channel']/competitors)) if competitors else None,
            lambda_sp=lam,lambda_cap=e['lambda_cap_sp'],diagnostic_cap=diagnostic_cap,L_u=e['L_u'],
            theta_deg=float(np.degrees(e['theta_total'])),guard=e.get('lambda_guard_reason_sp'),
            reference_error_deg=n.a.angle_deg(n.a.complex_pairs(e['channel_sp']),W@CHANNELS[target['source_index']]),
            methods=metrics,lambda_diagnostic=diagnostic,exact_all_symbol_interval=exact_interval(p,q,target['symbol_bins'],e['lambda_cap_sp']),
            extended_all_symbol_interval=exact_interval(p,q,target['symbol_bins'],diagnostic_cap),
            rescued_symbols=int(np.sum((np.asarray(decoded['mrc'])!=target['symbol_bins'])&(np.asarray(spbins)==target['symbol_bins']))),
            harmed_symbols=int(np.sum((np.asarray(decoded['mrc'])==target['symbol_bins'])&(np.asarray(spbins)!=target['symbol_bins']))),
            clean_reference_mrc=clean_mrc,clean_reference_tested_grid_any_success=bool(best_clean))
        targets.append(row)
    n.a.write_json(path,dict(spec=spec,revision=revision,truth=truth,targets=targets,
        noise_budget=noise,spectrum_cache=cache.audit(),elapsed_seconds=time.perf_counter()-started))
    return key


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--pilot',action='store_true');parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    if args.prepare:prepare();return
    initialize();manifest=json.loads((OUT/'manifest.json').read_text())
    jobs=manifest['jobs']
    if args.pilot:
        jobs=[s for s in jobs if s['family']=='isolated' or (s['repeat']==0 and s['family']=='temporal') or
              (s['repeat']==0 and s['family']=='geometry' and s['k'] in (2,10))]
    with ProcessPoolExecutor(max_workers=args.workers,initializer=initialize) as pool:
        futures=[pool.submit(run_job,s,manifest['revision']) for s in jobs]
        for i,f in enumerate(as_completed(futures),1):
            f.result()
            if i%16==0 or i==len(jobs):print(f'BOUNDARY {i}/{len(jobs)}',flush=True)


if __name__=='__main__':main()
