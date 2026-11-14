#!/usr/bin/env python3
"""Common-bank, common-SNR study: one controlled change per main comparison."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ.setdefault('MPLCONFIGDIR','/tmp/unified_study_mpl')
from pathlib import Path
import sys,json,itertools,hashlib,argparse,copy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from concurrent.futures import ProcessPoolExecutor,as_completed
from real_collision_experiment.paper_experiments import run_compact_revision_20261106 as c
b=c.b;OUT=ROOT/'real_usrp_outputs/unified_operating_study_20261114'
SIRS=(-20.,-15.,-10.,-5.,0.,5.,10.);KS=(2,3,4,5,6);REPEATS=100

def initialize():b.initialize();c.OUT=OUT

def run_density(spec):
    # Multiuser lambda=0 does not certify the pair guard's physical-MRC mapping.
    # Preserve the production result; only assert equality when that mapping exists.
    path=OUT/'jobs'/(c.key(spec)+'.json')
    if path.exists():return 'cached'
    samples,truth,noise=b.synthesize(spec);physical,white,es,sigma,W,_=b.n.a.controlled_inputs(samples,truth,b.n.CFG)
    ee=b.attach_sp_reliability_and_lambda(white,es,b.n.CFG,noise_sigma2=sigma,gamma=.05,reference_guard=True,physical_samples=physical,whitener=W,multiuser_lambda_cap=4.)
    physical=np.asarray(physical,dtype=np.complex64);cache=b.IntegerPayloadCache();e=ee[0];bins,_=c.sp_bins(physical,W,e,cache)
    assert bins==b.n.a.projected_decisions(white,e,b.n.CFG)[0]
    metrics={'sp':b.n.h.payload_metric(bins,truth[0],b.n.CFG)}
    for method in c.METHODS[1:]:
        ctx=c.CertifiedContext(physical,es,b.n.CFG,frontend_method=method,payload_spectrum_cache=cache)
        bb=getattr(ctx,'decode_'+method)(es[0])['symbol_bins'];metrics[method]=b.n.h.payload_metric(bb,truth[0],b.n.CFG)
        if method=='mrc' and e['lambda_sp']==0 and 'mrc_decision_channel_sp' in e:assert bb==bins
    c.write(path,dict(spec=spec,metrics=metrics,lambda_sp=e['lambda_sp'],guard=e.get('lambda_guard_reason_sp'),estimate=e,
        physical_angle=b.n.a.angle_deg(b.CHANNELS[spec['sources'][0]],b.CHANNELS[spec['sources'][1]]),
        reference=c.reference_rows(physical,es[0],truth[0],b.n.CFG,cache),noise_budget=noise,
        validation_note='SP bins match production; zero lambda in retained multiuser branch need not use physical-MRC reference. Receiver algorithm unchanged.'))
    return 'done'

def prepare():
    initialize();cov={}
    for u in b.CHANNELS:
        row=b.n.AUDIT['packets'][u];cov[u]=np.array([[complex(*v) for v in rr] for rr in row['covariance']])*2/row['signal_vector_power']
    eligible={};coverage=[]
    for u in sorted(b.CHANNELS):
        bypos={}
        for v in sorted(b.CHANNELS):
            if b.POSITIONS[u]==b.POSITIONS[v]:continue
            angle=b.n.a.angle_deg(b.CHANNELS[u],b.CHANNELS[v])
            if 10<=angle<60:bypos.setdefault(b.POSITIONS[v],[]).append(v)
        choices=[]
        for pp in itertools.combinations(sorted(bypos),5):
            for vv in itertools.product(*(bypos[p] for p in pp)):
                C=cov[u]+100*sum((cov[v] for v in vv),np.zeros((2,2),complex))
                if np.linalg.eigvalsh(C).max()<=1:choices.append(tuple(vv))
        if choices:eligible[u]=choices
        coverage.append(dict(target_source=u,position=b.POSITIONS[u],admissible_six_packet_combinations=len(choices)))
    assert eligible
    groups={p:[u for u in eligible if b.POSITIONS[u]==p] for p in sorted({b.POSITIONS[u] for u in eligible})};positions=list(groups)
    masters=[]
    for repeat in range(REPEATS):
        rng=np.random.default_rng(71400000+repeat);uu=groups[positions[repeat%len(positions)]];u=uu[(repeat//len(positions))%len(uu)]
        competitors=list(eligible[u][int(rng.integers(len(eligible[u])))]);rng.shuffle(competitors)
        # Uniform source order, not ordered by angular proximity or decode outcome.
        centre=float(rng.uniform(.2,1.8));direction=int(rng.choice([-1,1]));offsets=[centre,centre+.2*direction,*rng.uniform(0,2,4).tolist()]
        master=dict(repeat=repeat,seed=71410000+repeat,sources=[u,*competitors],offsets=offsets,phases=rng.uniform(-np.pi,np.pi,6).tolist())
        masters.append(master)
    def spec(master,family,k,sir,snr=0.):
        return dict(family=family,k=k,repeat=master['repeat'],seed=master['seed'],sources=master['sources'][:k],
            width_ratio=2/b.n.CFG.payload_symbol_count,relative_offsets=(np.array(master['offsets'][:k])/2).tolist(),
            phases=master['phases'][:k],powers=[1.]+[10**(-sir/10)]*(k-1),snr_db=float(snr),individual_sir_db=float(sir),focus=[0],angle_low=10.,angle_high=60.)
    main=[];snr=[];angle=[]
    for master in masters:
        main.extend(spec(master,'unified',2,sir) for sir in SIRS)
        main.extend(spec(master,'unified',k,sir) for k in KS[1:] for sir in (-10.,-5.))
        snr.extend(spec(master,'low_snr',2,-10.,level) for level in (-26.,-23.,-20.,-17.,-14.,-11.,-8.,-5.,-2.))
    angular_coverage=[]
    for low,high in [(0,2),(2,5),(5,10),(10,20),(20,40),(40,60),(60,90.000001)]:
        pool=[]
        for u in sorted(b.CHANNELS):
            for v in sorted(b.CHANNELS):
                if b.POSITIONS[u]==b.POSITIONS[v]:continue
                aa=b.n.a.angle_deg(b.CHANNELS[u],b.CHANNELS[v])
                if low<=aa<high and np.linalg.eigvalsh(cov[u]+100*cov[v]).max()<=1:pool.append((u,v))
        angular_coverage.append(dict(low=low,high=min(high,90),ordered_source_pairs=len(pool),position_pairs=len({tuple(sorted((b.POSITIONS[u],b.POSITIONS[v]))) for u,v in pool})))
        if not pool:continue
        gg={p:[(u,v) for u,v in pool if b.POSITIONS[u]==p] for p in sorted({b.POSITIONS[u] for u,v in pool})};ps=list(gg)
        for repeat in range(REPEATS):
            pairs=gg[ps[repeat%len(ps)]];u,v=pairs[(repeat//len(ps))%len(pairs)]
            s=c.base('angle_boundary',[u,v],repeat,71420000+int(low)*1000+repeat,0.,-10.)
            s.update(angle_low=float(low),angle_high=float(min(high,90)));angle.append(s)
    meta=dict(common_snr_db=0.,common_phy=b.n.AUDIT['config'],common_angle_interval=[10,60],master_scenes=REPEATS,
        main_rule='Identical six-packet source bank, each target/interferer angle 10–60deg; nested uniformly shuffled interferers, same per-link source/phase/digital starts. Two-packet target/interferer start gap 0.2Tsym; all master starts within 2Tsym. No outcome-based master choice.',
        noise_rule='Master feasibility at SNR0 and per-interferer SIR-20 before decoding. Per-mixture remaining source-noise covariance compensated. Same seed is not identical noise across K.',
        eligibility_rule='All distinct-position six-packet combinations satisfying physical-angle and source-noise budget constraints. Balanced eligible target positions, then target source traces. Not a deployment sample.',
        coverage=coverage,angular_coverage=angular_coverage,masters=masters,eligible_target_positions=positions,
        raw_iq_sha256=b.CAL['source_iq_sha256'],algorithm_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('evaluate_sp_dechirp_real_pos.py','sp_reference_guard.py','compare/real_packet_decoders.py')},
        scoring='Controlled exact starts/calibrated CFO, mixed-preamble references and online fixed lambda, CRC+exact target payload; all methods identical observations/candidates.')
    c.write(OUT/'protocol.json',meta)
    for stage,specs in [('main',main),('snr',snr),('angle',angle)]:c.write(OUT/f'manifest_{stage}.json',dict(specs=specs))
    print(json.dumps(dict(main=len(main),snr=len(snr),angle=len(angle),target_positions=positions,coverage=coverage),indent=2),flush=True)

def run(stage,workers):
    initialize()
    if stage=='safety' and not (OUT/'manifest_safety.json').exists():
        specs=[]
        for original in json.loads((OUT/'manifest_snr.json').read_text())['specs']:
            s=copy.deepcopy(original);s.update(family='safety_snr',powers=[1.,1.],individual_sir_db=0.);specs.append(s)
        for original in json.loads((OUT/'manifest_angle.json').read_text())['specs']:
            if original['angle_low']>=10:continue
            s=copy.deepcopy(original);s.update(family='safety_angle',powers=[1.,1.],individual_sir_db=0.);specs.append(s)
        c.write(OUT/'manifest_safety.json',dict(specs=specs,rule='Equal-power MRC-viable controls: same target/source/phase/timing as noise and <10deg angle stress cases; only SIR changes from -10 to 0. Used for numeric guard verification, not as main gain evidence.'))
    if stage=='calibration' and not (OUT/'manifest_calibration.json').exists():
        specs=[c.base('pilot',[source],repeat,71430000+source*10+repeat,0.) for source in sorted(b.CHANNELS) for repeat in range(4)]
        c.write(OUT/'manifest_calibration.json',dict(specs=specs,rule='Collision-free physical-MRC check at the fixed main SNR0; all22 retained traces, four repeats each.'))
    if stage=='density' and not (OUT/'manifest_density.json').exists():
        p=json.loads((OUT/'protocol.json').read_text());specs=[]
        for master in p['masters']:
            offsets=np.array(master['offsets']);relative=(offsets-offsets.min())/np.ptp(offsets)
            for width in (2.,1.,.5,.25,.1,.05):
                specs.append(dict(family='density',k=6,repeat=master['repeat'],seed=master['seed'],sources=master['sources'],phases=master['phases'],width_ratio=width,relative_offsets=relative.tolist(),powers=[1.]+[10**.5]*5,snr_db=0.,individual_sir_db=-5.,focus=[0],angle_low=10.,angle_high=60.))
        c.write(OUT/'manifest_density.json',dict(specs=specs,rule='Same frozen 100 six-packet masters; fixed SNR0 and individual SIR-5; scale normalized digital start pattern to W/Tpayload=2,1,.5,.25,.1,.05. Source/power/phase/order fixed; no outcome-based source filtering.'))
    m=json.loads((OUT/f'manifest_{stage}.json').read_text());todo=[s for s in m['specs'] if not (OUT/'jobs'/(c.key(s)+'.json')).exists()]
    print(stage,'remaining',len(todo),flush=True)
    with ProcessPoolExecutor(max_workers=workers,initializer=initialize) as pool:
        fs=[pool.submit(run_density if stage=='density' else c.run,s) for s in todo]
        for i,f in enumerate(as_completed(fs),1):
            f.result()
            if i%50==0 or i==len(fs):print(f'{stage.upper()} {i}/{len(fs)}',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','main','snr','angle','density','calibration','safety']);ap.add_argument('--workers',type=int,default=4);args=ap.parse_args();OUT.mkdir(exist_ok=True,parents=True)
    if args.stage=='prepare':prepare()
    else:run(args.stage,args.workers)
