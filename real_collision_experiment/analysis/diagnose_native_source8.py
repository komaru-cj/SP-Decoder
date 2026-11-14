#!/usr/bin/env python3
"""Read-only diagnostic of source 8; no figure/filter/receiver changes."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from real_collision_experiment.paper_experiments import run_native_iq_heatmaps as n
n.initialize();a=n.a;c=n.CFG
OUT=n.OUT/'source8_diagnostic'

def main():
    tails=[]
    for r in n.AUDIT['packets']:
        if r.get('excluded'):continue
        p=n.PACKETS[r['index']];powers=[];bins=[];concentration=[]
        for q in range(c.payload_symbol_count):
            s=round((c.payload_start_symbols+q)*c.samples_per_symbol)
            w=p[:,s:s+c.samples_per_symbol];powers.append(float(np.mean(abs(w)**2)))
            comp=a.compensate_symbol_window(p,s,r['cfo_bins'],c)
            F=np.vstack([a.lora_symbol_fft(x*a.instantaneous_chirp(0,c,up=False),c) for x in comp])
            E=np.sum(abs(F)**2,axis=0);bins.append(int(np.argmax(E)));concentration.append(float(E.max()/E.sum()))
        baseline=float(np.median(powers[:30]))
        tails.append(dict(source=r['index'],last8_power_relative_db=(10*np.log10(np.array(powers[-8:])/baseline)).tolist(),
            last8_peak_bins=bins[-8:],encoded_last8=r['symbol_bins'][-8:],
            last8_peak_energy_fractions=concentration[-8:],frame_end=r['metadata']['refined_start']+c.frame_samples,
            detected_energy_end_with_guard=r['metadata']['energy_end']))
    r=n.AUDIT['packets'][8];p=n.PACKETS[8];scale=np.sqrt(2/r['signal_vector_power'])
    C=np.array([[complex(*v) for v in row] for row in r['covariance']])*scale**2
    start=3*c.samples_per_symbol;end=start+c.frame_samples;trials=[]
    vals,V=np.linalg.eigh(10*np.eye(2)-C);L=V@np.diag(np.sqrt(vals))
    for seed in range(16):
        rng=np.random.default_rng(945+seed);phase=np.exp(2j*np.pi*rng.random())
        samples=(rng.normal(size=(2,end+start))+1j*rng.normal(size=(2,end+start)))*np.sqrt(5)
        noise=(rng.normal(size=(2,c.frame_samples))+1j*rng.normal(size=(2,c.frame_samples)))/np.sqrt(2)
        samples[:,start:end]=p*(scale*phase)+L@noise
        truth=[dict(start_sample=float(start),cfo_bins=r['cfo_bins'])]
        physical,white,es,sigma,W,cal=a.controlled_inputs(samples.astype(np.complex64),truth,c)
        decoded=a.PaperComparisonContext(physical,es,c,frontend_method='mrc').decode_mrc(es[0])
        bins=decoded['symbol_bins'];variants={}
        for name,positions in [('unchanged',[]),('known_symbol36',[36]),('known_symbol37',[37]),('known_last_two',[36,37])]:
            b=list(bins)
            for q in positions:b[q]=r['symbol_bins'][q]
            phy=a.decode_payload_from_symbol_bins(b,c)
            variants[name]=bool(phy.phy_crc_ok and phy.payload.hex()==r['payload_hex'])
        trials.append(dict(seed=seed,error_positions=[q for q,(x,y) in enumerate(zip(bins,r['symbol_bins'])) if x!=y],
            observed_last_two=bins[-2:],known_symbol_interventions=variants))
    result=dict(scope='offline causal diagnostics only; true symbols not supplied to receiver or figures',
        snr_db=-10,interferers=0,all_source_tails=tails,source8_trials=trials,
        intervention_successes={k:sum(t['known_symbol_interventions'][k] for t in trials) for k in trials[0]['known_symbol_interventions']})
    a.write_json(OUT/'audit.json',result)
    print(result['intervention_successes'])
    print('error positions', [t['error_positions'] for t in trials])
    print('tail below -10dB',[(r['source'],round(r['last8_power_relative_db'][-1],2)) for r in tails if r['last8_power_relative_db'][-1]<-10])

if __name__=='__main__':main()
