#!/usr/bin/env python3
"""Measured packet-IQ superposition, native PHY; no waveform regeneration."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import json,hashlib,shutil,time,argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
from real_collision_experiment.paper_experiments import run_resubmission_heatmaps as h
from evaluate_sp_dechirp_real_pos import attach_sp_reliability_and_lambda
from sp_reference_guard import GUARDED_PAIR_POLICY
from real_collision_experiment.node01_sp_receiver.real_lora_config import RealCollisionLoRaConfig
from usrp_b210_lora_tx import payload_nibbles,hamming_codewords,interleave,gray_demap
from real_usrp_clean_packet_synth import detect_energy_segments
from real_collision_experiment.paper_experiments.frame_integrity import check_frame_integrity
from compare.real_packet_decoders import DEFAULT_PCUBE_POLICY
from real_collision_experiment.paper_experiments.arrival_density import scaled_starts
a=h.abc
OUT=ROOT/'real_usrp_outputs/revision_heatmaps_native_iq'
SOURCE=ROOT/'real_usrp_outputs/clean_pos_packets.npz'
PACKETS=None;AUDIT=None;CFG=None

def initialize():
    global PACKETS,AUDIT,CFG
    with np.load(OUT/'aligned_source_iq.npz') as z:PACKETS=z['packets']
    AUDIT=json.loads((OUT/'source_audit.json').read_text());CFG=RealCollisionLoRaConfig(**AUDIT['config'])
    for row in AUDIT['packets']:
        if row.get('excluded'):continue
        row.setdefault('observed_source_symbol_bins',row['symbol_bins'])
        row['symbol_bins']=[gray_demap(v,CFG) for v in interleave(hamming_codewords(payload_nibbles(bytes.fromhex(row['payload_hex']),CFG),CFG),CFG)]

def screen_frame_integrity():
    with np.load(SOURCE) as z:metadata=json.loads(str(z['metadata_json']))
    cov_by_file={r['metadata']['source_file']:np.array([[complex(*v) for v in row] for row in r['covariance']]) for r in AUDIT['packets'] if 'covariance' in r}
    checks=[]
    for i,(packet,meta) in enumerate(zip(PACKETS,metadata['packets'])):
        C=cov_by_file[meta['source_file']]
        result=check_frame_integrity(packet,CFG,float(np.trace(C).real/2))
        result.update(source_index=i,source_file=meta['source_file']);checks.append(result)
        row=AUDIT['packets'][i];row['frame_integrity']=result
        if not result['passed']:
            row.update(excluded=True,reason='frame_integrity_failed')
    AUDIT['excluded_indices']=[r['index'] for r in AUDIT['packets'] if r.get('excluded')]
    AUDIT['frame_integrity_policy']='Every complete preamble/sync/SFD/payload chirp: power >= early payload median -10 dB and >= measured noise +10 dB; no decode/PDR input'
    a.write_json(OUT/'frame_integrity_audit.json',dict(policy=AUDIT['frame_integrity_policy'],packets=checks,
        frame_integrity_failed=[r['source_index'] for r in checks if not r['passed']],excluded_indices=AUDIT['excluded_indices']))

def audit(exclude_unverified=False):
    OUT.mkdir(exist_ok=True)
    with np.load(SOURCE) as z:packets=z['packets'];md=json.loads(str(z['metadata_json']))
    cfg=RealCollisionLoRaConfig(**md['config']);bank=a.source_bank();covs={}
    for filename in sorted({m['source_file'] for m in md['packets']}):
        with np.load(ROOT/filename) as z:s=z['samples'].astype(np.complex128)
        s-=s.mean(axis=1,keepdims=True)
        mask=np.ones(s.shape[1],dtype=bool)
        for l,u in detect_energy_segments(s,cfg):
            mask[max(0,l-cfg.samples_per_symbol):min(s.shape[1],u+cfg.samples_per_symbol)]=False
        quiet=s[:,mask];assert quiet.shape[1]>cfg.samples_per_symbol
        covs[filename]=quiet@quiet.conj().T/quiet.shape[1]
    rows=[]
    for i,(packet,m) in enumerate(zip(packets,md['packets'])):
        e=dict(start_sample=0.,cfo_bins=bank[i]['cfo_bins'],channel=[[0.,0.],[0.,0.]])
        r=a.PaperComparisonContext(packet,[e],cfg,frontend_method='mrc').decode_mrc(e)
        original_mrc_ok=r['phy']['phy_crc_ok']
        for channel in (0,1):
            if r['phy']['phy_crc_ok']:break
            ce=dict(e,shared_sp_mrc_channel=[[float(channel==0),0.],[float(channel==1),0.]])
            cr=a.PaperComparisonContext(packet,[ce],cfg,frontend_method='mrc').decode_mrc(ce)
            if cr['phy']['phy_crc_ok']:r=cr
        used_delta=0
        if not r['phy']['phy_crc_ok']:
            for delta in np.arange(-1,1.001,.125):
                ee=dict(e,cfo_bins=bank[i]['cfo_bins']+float(delta))
                rr=a.PaperComparisonContext(packet,[ee],cfg,frontend_method='mrc').decode_mrc(ee)
                if rr['phy']['phy_crc_ok']:r=rr;e=ee;break
        if not r['phy']['phy_crc_ok']:
            if not exclude_unverified:raise ValueError(f'source {i} has no validated payload; source selection needs confirmation')
            rows.append(dict(index=i,excluded=True,reason='no_validated_payload_CRC'));continue
        print('SOURCE_CRC_OK',i,'boundary_delta',used_delta,flush=True)
        C=covs[m['source_file']];power=float(np.mean(abs(packet)**2)*2-np.trace(C).real)
        assert power>0
        rows.append(dict(index=i,metadata=m,covariance=[[ [float(v.real),float(v.imag)] for v in row] for row in C],
            signal_vector_power=power,payload_hex=r['phy']['payload_hex'],symbol_bins=r['symbol_bins'],cfo_bins=e['cfo_bins'],boundary_delta_samples=used_delta,source_MRC_crc_ok=original_mrc_ok))
    np.savez(OUT/'aligned_source_iq.npz',packets=packets)
    a.write_json(OUT/'source_audit.json',dict(config=md['config'],source=str(SOURCE),packets=rows,
        all_included_sources_crc_valid=True,noise_calibration_version=2,excluded_indices=[r['index'] for r in rows if r.get('excluded')],
        noise_model='full measured quiet covariance; additive residual budget per overlap interval'))

def synthesize(spec,old):
    rng=np.random.default_rng(spec['seed']);cfg=CFG
    bank=[dict(r,native_index=i) for i,r in enumerate(a.source_bank()) if not AUDIT['packets'][i].get('excluded')]
    selection=dict(family='A3_master',k=10) if spec['family']=='A3_density_delay' else spec
    for attempt in range(10000):
        selected=[bank[i]['native_index'] for i in a.select_sources(bank,selection,rng)][:spec['k']]
        if not spec['family'].startswith('C1'):break
        # Same eligibility at every SNR/SIR: do not select source pairs whose
        # retained noise cannot support the strongest interferer / highest SNR.
        C=np.zeros((2,2),complex)
        worst_sigma=1. if spec['family']=='C1_snr_sir' else 10.
        for j,idx in enumerate(selected):
            row=AUDIT['packets'][idx];v=np.array([[complex(*x) for x in rr] for rr in row['covariance']])
            C+=v*(2*(1. if j==0 else 100.)/row['signal_vector_power'])
        if np.linalg.eigvalsh(worst_sigma*np.eye(2)-C).min()>=0:break
    else:raise ValueError('no noise-feasible native source pair in this angle bin')
    if spec['family']=='A3_density_delay':
        gaps=np.array(old['timing']['planned_signed_adjacent_gaps']);offsets=np.r_[0.,np.cumsum(gaps)];offsets-=offsets.min()
    else:offsets=np.array([0.,.2])
    if spec['family']=='A3_density_delay' and 'arrival_density' in spec:
        starts,_=scaled_starts(offsets,spec['arrival_density'],cfg.samples_per_symbol)
    else:
        starts=np.rint((3+offsets)*cfg.samples_per_symbol).astype(int)
    length=int(starts.max()+cfg.frame_samples+3*cfg.samples_per_symbol)
    signal=np.zeros((2,length),dtype=np.complex64);truth=[];cov=[]
    for idx,ot,start in zip(selected,old['truth'],starts):
        r=AUDIT['packets'][idx];power=ot['power_per_channel']
        scale=np.sqrt(2*power/r['signal_vector_power']);phase=np.exp(2j*np.pi*rng.random())
        snippet=(PACKETS[idx]*(scale*phase)).astype(np.complex64)
        signal[:,start:start+cfg.frame_samples]+=snippet
        C=np.array([[complex(*v) for v in row] for row in r['covariance']])*scale**2;cov.append(C)
        truth.append(dict(source_index=idx,position=a.source_bank()[idx]['position'],start_sample=float(start),cfo_bins=r['cfo_bins'],
            power_per_channel=power,payload_hex=r['payload_hex'],symbol_bins=r['symbol_bins'],scale=float(scale),
            constant_phase_rad=float(np.angle(phase))))
    sigma=10**(-spec['snr_db']/10);bounds=sorted({0,length,*starts.tolist(),*(starts+cfg.frame_samples).tolist()});mineig=sigma
    for l,u in zip(bounds[:-1],bounds[1:]):
        C=sum((c for s,c in zip(starts,cov) if s<=l<s+cfg.frame_samples),np.zeros((2,2),complex))
        residual=sigma*np.eye(2)-C;vals,V=np.linalg.eigh(residual);mineig=min(mineig,float(vals.min()))
        if vals.min() < -1e-8*sigma:raise ValueError('embedded source noise exceeds requested SNR budget')
        transform=V@np.diag(np.sqrt(np.maximum(vals,0)))
        noise=(rng.normal(size=(2,u-l))+1j*rng.normal(size=(2,u-l)))/np.sqrt(2)
        signal[:,l:u]+=(transform@noise).astype(np.complex64)
    return signal,truth,dict(total_noise_variance=sigma,min_residual_covariance_eigenvalue=mineig,
        native_iq_preserved_up_to_constant_complex_scale=True,packet_resampling=False)

def run(spec,revision):
    path=OUT/'jobs'/(a.job_key(spec)+'.json')
    if path.exists():
        j=json.loads(path.read_text())
        if j['revision_hash']==revision:return
    old_key=spec.get('original_timing_job',path.stem)
    old=json.loads((h.OUT/'jobs'/(old_key+'.json')).read_text());samples,truth,noise=synthesize(spec,old)
    physical,white,es,sigma,W,cal=a.controlled_inputs(samples,truth,CFG)
    configured=attach_sp_reliability_and_lambda(white,es,CFG,noise_sigma2=sigma,gamma=.05,
        reference_guard=True,physical_samples=physical,whitener=W,
        remove_multiuser_lambda_cap=spec.get('remove_multiuser_lambda_cap',False),
        multiuser_lambda_cap=spec.get('multiuser_lambda_cap',4.0))
    contexts={m:a.PaperComparisonContext(physical,es,CFG,frontend_method=m) for m in ('mrc','pcube','maloragw')} if spec['family'].startswith('C1') else {}
    targets=[]
    for i in spec.get('focus',range(len(truth))):
        e=configured[i];bins=a.projected_decisions(white,e,CFG)[0];metrics=dict(sp=h.payload_metric(bins,truth[i],CFG))
        for m,c in contexts.items():
            b=getattr(c,'decode_'+m)(es[i])['symbol_bins'];metrics[m]=h.payload_metric(b,truth[i],CFG)
            if m=='mrc' and e['lambda_sp']==0:assert b==bins
        targets.append(dict(target_index=i,methods=metrics,lambda_sp=e['lambda_sp'],lambda_cap=e['lambda_cap_sp'],
            lambda_guard_reason=e.get('lambda_guard_reason_sp')))
    timing={}
    if 'arrival_density' in spec:
        gaps=np.array(old['timing']['planned_signed_adjacent_gaps'])
        _,timing=scaled_starts(np.r_[0.,np.cumsum(gaps)],spec['arrival_density'],CFG.samples_per_symbol)
        assert timing['actual_span_symbols']==np.ptp([t['start_sample'] for t in truth])/CFG.samples_per_symbol
    a.write_json(path,dict(spec=spec,config=AUDIT['config'],truth=truth,targets=targets,candidate_estimates=configured,timing=timing,
        calibration=cal,noise_budget=noise,sp_policy=GUARDED_PAIR_POLICY,pcube_policy=DEFAULT_PCUBE_POLICY,revision_hash=revision,
        provenance=dict(kind='native_measured_dual_channel_IQ_superposition',original_payloads=True,
            synthetic_chirp_generation=False,source_audit='source_audit.json',simultaneous_air_capture=False)))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);parser.add_argument('--pilot',action='store_true');parser.add_argument('--exclude-unverified-sources',action='store_true');args=parser.parse_args()
    if not (OUT/'source_audit.json').exists() or json.loads((OUT/'source_audit.json').read_text()).get('noise_calibration_version')!=2:audit(args.exclude_unverified_sources)
    initialize();screen_frame_integrity();jobs=[]
    AUDIT['source_file_sha256']=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    AUDIT['CFO_calibration']='isolated-source calibration; bounded +/-1 bin at 0.125 steps only after original CRC failure; controlled sync in mixtures'
    a.write_json(OUT/'source_audit.json',AUDIT)
    revision=hashlib.sha256((a.revision_hash()+Path(__file__).read_text()+json.dumps(AUDIT,sort_keys=True)).encode()).hexdigest()
    for stage in h.STAGES:
        source_manifest=h.OUT/f'manifest_{stage}.json'
        current_manifest=OUT/f'manifest_{stage}.json'
        if stage=='A3_density_delay' and current_manifest.exists() and json.loads(current_manifest.read_text()).get('timing_axis')=='actual_arrival_density':
            source_manifest=current_manifest
        manifest=json.loads(source_manifest.read_text());specs=manifest['jobs']
        if args.pilot:specs=[s for s in specs if s['repeat']==0]
        manifest.update(jobs=specs,revision_hash=revision,config=AUDIT['config'],sp_policy=GUARDED_PAIR_POLICY,pcube_policy=DEFAULT_PCUBE_POLICY,
            waveform='native IQ superposition; original within-packet changes retained',
            evidence='offline superposition of measured dual-channel IQ; not a simultaneous-air capture',
            included_sources=sum(not r.get('excluded') for r in AUDIT['packets']),excluded_source_indices=AUDIT['excluded_indices'],
            frame_integrity_policy=AUDIT['frame_integrity_policy'],frame_integrity_audit='frame_integrity_audit.json',
            source_audit='source_audit.json',source_noise_eligibility='fixed worst-case noise-feasibility rule across SNR/SIR, before decoding',
            original_generation_manifest=str((h.OUT/f'manifest_{stage}.json').relative_to(ROOT)))
        manifest.pop('runner_source_snapshot',None);manifest.pop('code_sha256',None)
        a.write_json(OUT/f'manifest_{stage}.json',manifest);jobs+=specs
    for relative in [Path(__file__).relative_to(ROOT),Path('real_collision_experiment/paper_experiments/frame_integrity.py'),Path('real_collision_experiment/paper_experiments/arrival_density.py'),Path('sp_reference_guard.py'),Path('sp_noise_competition.py'),Path('evaluate_sp_dechirp_real_pos.py'),Path('real_collision_experiment/node01_sp_receiver/lora_phy_decode.py'),Path('compare/real_packet_decoders.py'),Path('compare/PCube/soft_grouping.py'),Path('compare/mrc_input.py')]:
        target=OUT/'code_snapshot'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/relative).read_bytes())
    with ProcessPoolExecutor(max_workers=args.workers,initializer=initialize) as pool:
        fs=[pool.submit(run,s,revision) for s in jobs]
        for i,f in enumerate(as_completed(fs),1):
            f.result()
            if i%16==0:print(f'{i}/{len(jobs)}',flush=True)
    for stage in h.STAGES:h.render(stage,OUT,sp_policy=GUARDED_PAIR_POLICY)
    print('DONE',flush=True)

if __name__=='__main__':main()
