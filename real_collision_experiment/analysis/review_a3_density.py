"""Audit A3 density semantics and preview K=10 lambda, without changing paper plots."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/a3_density_review_mpl')
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import json,csv,hashlib
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from real_collision_experiment.paper_experiments import run_native_iq_heatmaps as n

OUT=ROOT/'real_usrp_outputs/a3_collision_density_review_20261030'


def csv_write(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def save(fig,name):
    for ext in ('pdf','png','svg'):fig.savefig(OUT/(name+'.'+ext),dpi=180,bbox_inches='tight')
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    manifest_path=n.OUT/'manifest_A3_density_delay.json'
    manifest=json.loads(manifest_path.read_text())
    if manifest.get('timing_axis')=='actual_arrival_density':
        manifest_path=n.OUT/'backup_a3_nominal_density_20261030/manifest_A3_density_delay.json'
        manifest=json.loads(manifest_path.read_text())
    source_root=manifest_path.parent
    cfg=n.RealCollisionLoRaConfig(**manifest['config'])
    scene_rows=[];lambda_rows=[];grouped=defaultdict(list);lambda_group=defaultdict(list)
    # Check paired source identities, powers and common source phases, not
    # decoded results, before drawing any per-packet density trajectory.
    paired={}
    for spec in manifest['jobs']:
        key=n.a.job_key(spec);j=json.loads((source_root/'jobs'/(key+'.json')).read_text())
        starts=np.asarray([t['start_sample'] for t in j['truth']])/cfg.samples_per_symbol
        width=float(np.ptp(starts));k=spec['k'];rho=(k-1)/width
        full_overlap=max(0.,cfg.frame_symbols-width)/cfg.frame_symbols
        row=dict(job=key,k=k,nominal_gap_symbols=spec['gap_symbols'],
                 nominal_density=1/spec['gap_symbols'],repeat=spec['repeat'],
                 actual_start_span_symbols=width,actual_density=rho,
                 common_frame_overlap_fraction=full_overlap,
                 successes=sum(t['methods']['sp']['delivered'] for t in j['targets']),packets=len(j['targets']))
        scene_rows.append(row);grouped[k,spec['gap_symbols']].append(row)
        if k!=10:continue
        signature=[(t['source_index'],t['position'],t['power_per_channel'],t['constant_phase_rad']) for t in j['truth']]
        if spec['repeat'] in paired:assert signature==paired[spec['repeat']]
        else:paired[spec['repeat']]=signature
        assert len({t['position'] for t in j['truth']})==10
        for t in j['targets']:
            i=t['target_index'];source=j['truth'][i];estimate=j['candidate_estimates'][i]
            assert estimate['lambda_sp']==t['lambda_sp']
            r=dict(job=key,repeat=spec['repeat'],source_position=source['position'],
                   source_index=source['source_index'],target_index=i,
                   nominal_gap_symbols=spec['gap_symbols'],nominal_density=1/spec['gap_symbols'],
                   actual_start_span_symbols=width,actual_density=rho,
                   lambda_sp=t['lambda_sp'],lambda_cap=t['lambda_cap'],
                   at_cap=bool(np.isclose(t['lambda_sp'],t['lambda_cap'])),
                   delivered=t['methods']['sp']['delivered'],
                   selection_branch=t['lambda_guard_reason'])
            lambda_rows.append(r);lambda_group[source['position'],spec['gap_symbols']].append(r)
    assert len(scene_rows)==256 and len(lambda_rows)==640
    csv_write(OUT/'scene_actual_density.csv',scene_rows)
    csv_write(OUT/'K10_per_packet_lambda.csv',lambda_rows)
    density_summary=[]
    for (k,gap),rows in sorted(grouped.items()):
        w=np.array([r['actual_start_span_symbols'] for r in rows]);d=np.array([r['actual_density'] for r in rows])
        density_summary.append(dict(k=k,nominal_gap_symbols=gap,nominal_density=1/gap,
            window_min=w.min(),window_median=np.median(w),window_max=w.max(),
            actual_density_min=d.min(),actual_density_median=np.median(d),actual_density_max=d.max()))
    csv_write(OUT/'density_summary.csv',density_summary)
    positions=sorted({r['source_position'] for r in lambda_rows});gaps=(.3,.2,.1,.05)
    mean=np.zeros((10,4));first=np.zeros_like(mean);summaries=[]
    for y,pos in enumerate(positions):
        for x,gap in enumerate(gaps):
            rows=lambda_group[pos,gap];assert len(rows)==16
            vals=np.array([r['lambda_sp'] for r in rows]);mean[y,x]=vals.mean()
            first[y,x]=next(r['lambda_sp'] for r in rows if r['repeat']==0)
            summaries.append(dict(source_position=pos,nominal_density=1/gap,
                n=16,mean=vals.mean(),median=np.median(vals),minimum=vals.min(),maximum=vals.max(),
                at_cap=int(sum(r['at_cap'] for r in rows)),at_zero=int((vals==0).sum())))
    csv_write(OUT/'K10_lambda_summary.csv',summaries)
    plt.rcParams.update({'font.size':11,'pdf.fonttype':42,'svg.fonttype':'none'})
    fig,axes=plt.subplots(1,2,figsize=(10,6),layout='constrained')
    for ax,matrix,title in zip(axes,(mean,first),('Mean of all 16 paired scenes','Individual packets, fixed repeat 0')):
        im=ax.imshow(matrix,origin='upper',vmin=0,vmax=4,cmap='viridis',aspect='auto')
        ax.set(xticks=range(4),xticklabels=['3.33','5','10','20'],
            yticks=range(10),yticklabels=positions,xlabel=r'Nominal start density $\rho_0=T_{sym}/\Delta$',
            ylabel='Source position',title=title)
        for y,x in np.ndindex(matrix.shape):
            ax.text(x,y,f'{matrix[y,x]:.2f}',ha='center',va='center',color='black' if matrix[y,x]>2.5 else 'white')
    fig.colorbar(im,ax=axes,label=r'Selected $\lambda$ (cap = 4)',shrink=.9)
    fig.suptitle('K = 10; preview from existing A3 scenes (nominal density)')
    save(fig,'A3_K10_lambda_nominal_density_preview')
    fig,ax=plt.subplots(figsize=(5.4,4.6))
    matrix=np.array([[sum(r['successes'] for r in grouped[k,gap])/sum(r['packets'] for r in grouped[k,gap])
                      for k in (4,6,8,10)] for gap in gaps])
    im=ax.imshow(matrix,origin='lower',vmin=0,vmax=1,cmap='viridis',aspect='auto')
    for y,x in np.ndindex(matrix.shape):ax.text(x,y,f'{matrix[y,x]:.3f}',ha='center',va='center',color='black' if matrix[y,x]>.6 else 'white')
    ax.set(xticks=range(4),xticklabels=['4','6','8','10'],yticks=range(4),yticklabels=['3.33','5','10','20'],
           xlabel='Collision order K',ylabel=r'Nominal start density $\rho_0=T_{sym}/\Delta$',title='SP-Decoder (existing scenes)')
    fig.colorbar(im,ax=ax,label='PDR');fig.tight_layout();save(fig,'A3_nominal_density_pdr_preview')
    cap_summary=[]
    for gap in gaps:
        rows=[r for r in lambda_rows if r['nominal_gap_symbols']==gap]
        cap_summary.append(dict(nominal_density=1/gap,n=len(rows),
            at_cap=sum(r['at_cap'] for r in rows),at_zero=sum(r['lambda_sp']==0 for r in rows),
            mean_lambda=float(np.mean([r['lambda_sp'] for r in rows]))))
    n.a.write_json(OUT/'summary.json',dict(scope='read-only audit and previews; formal figures not modified',
        source_manifest=str(manifest_path),source_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        nominal_density_definition='T_sym / nominal signed adjacent start increment',
        actual_density_definition='(K-1) T_sym / (max(start)-min(start))',
        same_sources_powers_and_phases_across_density_checked=True,frame_symbols=cfg.frame_symbols,
        first_repeat_fixed_in_advance=0,cap_summary=cap_summary,density_summary=density_summary))
    print(json.dumps(cap_summary,indent=2))


if __name__=='__main__':main()
