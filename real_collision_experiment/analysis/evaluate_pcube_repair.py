"""Paired PCube repair evaluation on unchanged native-IQ C1 waveforms.

Writes separate diagnostic artifacts; never overwrites formal jobs or figures.
"""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import json,hashlib,csv
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from real_collision_experiment.paper_experiments import run_native_iq_heatmaps as native
from compare.PCube.soft_grouping import CONSERVATIVE_POLICY as POLICY
from compare.real_packet_decoders import PhysicalEvidencePayloadCache

OUT=native.OUT/'pcube_repair_v3'


def worker(item):
    spec,heldout=item
    key=native.a.job_key(spec)
    revision=hashlib.sha256((ROOT/'compare/PCube/soft_grouping.py').read_bytes()+
        (ROOT/'compare/real_packet_decoders.py').read_bytes()+Path(__file__).read_bytes()).hexdigest()
    path=OUT/'cases'/(key+'.json')
    if path.exists():
        cached=json.loads(path.read_text())
        if cached['revision']==revision:return cached
    original_spec=dict(spec)
    if heldout:original_spec['seed']=original_spec.pop('paired_original_seed')
    original_key=native.a.job_key(original_spec)
    old=json.loads((native.h.OUT/'jobs'/(original_key+'.json')).read_text())
    samples,truth,noise=native.synthesize(spec,old)
    physical,_,estimates,_,_,_=native.a.controlled_inputs(samples,truth,native.CFG)
    ctx=native.a.PaperComparisonContext(physical,estimates,native.CFG,frontend_method='pcube',
        payload_spectrum_cache=PhysicalEvidencePayloadCache())
    target=spec['focus'][0]
    legacy=ctx.decode_pcube(estimates[target],grouping_policy='legacy_fixed_gate')
    repair=ctx.decode_pcube(estimates[target],grouping_policy=POLICY)
    metrics={name:native.h.payload_metric(result['symbol_bins'],truth[target],native.CFG)
        for name,result in (('legacy',legacy),('repair',repair))}
    if not heldout:
        frozen_root=native.OUT
        if json.loads((native.OUT/f"manifest_{spec['family']}.json").read_text()).get('pcube_policy')==POLICY:
            frozen_root=native.OUT/'backup_pcube_legacy_before_v3_20261030'
        frozen=json.loads((frozen_root/'jobs'/(key+'.json')).read_text())
        assert truth==frozen['truth']
        expected=frozen['targets'][0]['methods']['pcube']
        assert metrics['legacy']==expected,(spec,metrics['legacy'],expected)
    result=dict(spec=spec,heldout=heldout,sources=[t['source_index'] for t in truth],
        methods=metrics,grouping=repair['paper_diagnostics']['grouping'],noise_budget=noise,revision=revision)
    native.a.write_json(path,result)
    return result


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--heldout',action='store_true')
    args=parser.parse_args()
    native.initialize()
    OUT.mkdir(exist_ok=True)
    files=['compare/PCube/soft_grouping.py','compare/real_packet_decoders.py',str(Path(__file__).relative_to(ROOT))]
    hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
    native.a.write_json(OUT/'run_manifest.json',dict(policy=POLICY,files=hashes,
        source_sha256=native.AUDIT['source_file_sha256'],production_changed=False,
        clustering_is_local_reproduction_choice=True))
    items=[]
    for stage in ('C1_snr_sir','C1_angle_sir'):
        specs=json.loads((native.OUT/f'manifest_{stage}.json').read_text())['jobs']
        items.extend((s,False) for s in specs)
        if args.heldout:
            for s in specs:
                if s['repeat']<4:
                    ns=dict(s,paired_original_seed=s['seed'],seed=(s['seed']+173205081)%2**32)
                    items.append((ns,True))
    with ProcessPoolExecutor(max_workers=4,initializer=native.initialize) as pool:
        rows=[]
        for i,row in enumerate(pool.map(worker,items),1):
            rows.append(row)
            if i%64==0:print(f'C1 {i}/{len(items)}',flush=True)
    native.a.write_json(OUT/'paired_results.json',dict(manifest=hashes,rows=rows))
    cells=defaultdict(lambda:dict(n=0,legacy=0,repair=0,gained=0,lost=0,legacy_errors=0,repair_errors=0))
    for r in rows:
        s=r['spec']
        x=s['snr_db'] if s['family']=='C1_snr_sir' else s['angle_low']
        key=(r['heldout'],s['family'],x,s['sir_db'])
        c=cells[key];c['n']+=1
        a,b=[r['methods'][m]['delivered'] for m in ('legacy','repair')]
        c['legacy']+=a;c['repair']+=b;c['gained']+=b and not a;c['lost']+=a and not b
        for m in ('legacy','repair'):c[m+'_errors']+=r['methods'][m]['symbol_errors']
    with (OUT/'cell_comparison.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=['heldout','family','x','sir_db',*next(iter(cells.values())).keys()])
        writer.writeheader()
        for (heldout,family,x,sir),v in sorted(cells.items()):
            writer.writerow(dict(heldout=heldout,family=family,x=x,sir_db=sir,**v))
    totals=defaultdict(lambda:dict(n=0,legacy=0,repair=0,gained=0,lost=0))
    for (heldout,family,x,sir),v in cells.items():
        for k in totals[(heldout,family)]:totals[(heldout,family)][k]+=v[k]
    print(json.dumps({str(k):v for k,v in totals.items()},indent=2))
    native.a.write_json(OUT/'summary.json',{str(k):v for k,v in totals.items()})


if __name__=='__main__':main()
