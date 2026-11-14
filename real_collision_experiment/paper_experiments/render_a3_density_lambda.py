"""K=10 per-packet lambda under controlled actual arrival density."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/a3_actual_density_mpl')
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import argparse,json,csv
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import SymLogNorm
from real_collision_experiment.paper_experiments import run_native_iq_heatmaps as n


def render(root, repeat=None):
    root=Path(root)
    manifest=json.loads((root/'manifest_A3_density_delay.json').read_text())
    assert manifest['timing_axis']=='actual_arrival_density'
    uncapped=manifest.get('lambda_fixed_cap_removed',False)
    fixed_cap=manifest.get('lambda_global_max',None if uncapped else 4.)
    levels=sorted(manifest['density_levels']);rows=[];grouped=defaultdict(list);paired={}
    for spec in manifest['jobs']:
        if spec['k']!=10:continue
        j=json.loads((root/'jobs'/(n.a.job_key(spec)+'.json')).read_text())
        assert j['revision_hash']==manifest['revision_hash']
        signature=[(t['source_index'],t['position'],t['power_per_channel'],t['constant_phase_rad']) for t in j['truth']]
        if spec['repeat'] in paired:assert signature==paired[spec['repeat']]
        else:paired[spec['repeat']]=signature
        assert len({t['position'] for t in j['truth']})==10
        for t in j['targets']:
            source=j['truth'][t['target_index']];lam=t['lambda_sp'];cap=t['lambda_cap']
            row=dict(job=n.a.job_key(spec),repeat=spec['repeat'],source_position=source['position'],
                source_index=source['source_index'],target_index=t['target_index'],
                requested_density=spec['arrival_density'],actual_density=j['timing']['actual_density'],
                actual_span_symbols=j['timing']['actual_span_symbols'],lambda_sp=lam,lambda_cap=cap,
                at_value_4=bool(np.isclose(lam,4.,rtol=0,atol=1e-9)),above_4=bool(lam>4.+1e-9),
                at_individual_cap=bool(np.isclose(lam,cap,rtol=0,atol=1e-9)),
                at_zero=bool(lam==0),sp_delivered=t['methods']['sp']['delivered'],
                selection_branch=t['lambda_guard_reason'])
            rows.append(row)
    assert len(rows)==640
    all_rows=rows
    if repeat is not None:
        rows=[r for r in rows if r['repeat']==repeat]
        if len(rows)!=40:raise ValueError(f'Repeat {repeat} must contain all 40 K=10 packet/density values')
    scenes_per_density=16 if repeat is None else 1
    for row in rows:grouped[row['source_position'],row['requested_density']].append(row)
    positions=sorted({r['source_position'] for r in rows});means=np.zeros((10,4));summary=[]
    for y,pos in enumerate(positions):
        for x,rho in enumerate(levels):
            cell=grouped[pos,rho];assert len(cell)==scenes_per_density
            vals=np.array([r['lambda_sp'] for r in cell]);means[y,x]=vals.mean()
            summary.append(dict(source_position=pos,density=rho,n=len(cell),mean_lambda=float(vals.mean()),
                median_lambda=float(np.median(vals)),min_lambda=float(vals.min()),max_lambda=float(vals.max()),
                count_at_4=sum(r['at_value_4'] for r in cell),count_above_4=sum(r['above_4'] for r in cell),
                count_at_individual_cap=sum(r['at_individual_cap'] for r in cell),count_at_zero=sum(r['at_zero'] for r in cell)))
    directory=root/'figures';directory.mkdir(exist_ok=True)
    exports=[('A3_density_lambda_k10_per_packet.csv',all_rows),('A3_density_lambda_k10_summary.csv',summary)]
    if repeat is not None:exports.append(('A3_density_lambda_k10_selected_repeat.csv',rows))
    for name,values in exports:
        with (directory/name).open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
    plt.rcParams.update({'font.size':11,'pdf.fonttype':42,'svg.fonttype':'none'})
    color_max=max(1.,max(r['lambda_sp'] for r in rows)) if uncapped else float(fixed_cap)
    normalization=SymLogNorm(linthresh=1.,vmin=0.,vmax=color_max) if uncapped else None
    fig,ax=plt.subplots(figsize=(6.2,6))
    title='Mean across all 16 paired scenes' if repeat is None else f'Single paired repeat {repeat}'
    for matrix,title in ((means,title),):
        im=ax.imshow(matrix,origin='upper',cmap='viridis',aspect='auto',
            **({'norm':normalization} if uncapped else {'vmin':0,'vmax':color_max}))
        ax.set(xticks=range(4),xticklabels=[f'{x:.3g}' for x in levels],yticks=range(10),
            yticklabels=positions,xlabel=r'Arrival density $\rho=(K-1)T_{sym}/W$',ylabel='Source position',title=title)
        for y,x in np.ndindex(matrix.shape):
            value=matrix[y,x]
            label=f'{value:.2f}' if value<100 else f'{value:.3g}'
            fraction=float(normalization(value)) if uncapped else value/color_max
            ax.text(x,y,label,ha='center',va='center',color='black' if fraction>.62 else 'white')
    value_label=r'Mean selected $\lambda$' if repeat is None else r'Selected $\lambda$'
    bar=fig.colorbar(im,ax=ax,label=(value_label+' (symlog color scale)' if uncapped
        else value_label+f' (upper bound {fixed_cap:g})'),shrink=.9)
    if uncapped:
        ticks=[v for v in (0.,1.,4.,10.,100.,1000.,10000.,100000.,1000000.,1e9) if v<color_max]
        if ticks and ticks[-1]>0 and color_max/ticks[-1]<1.7:ticks.pop()
        ticks.append(color_max);bar.set_ticks(ticks);bar.set_ticklabels([f'{v:.3g}' for v in ticks])
    fig.suptitle('SP-Decoder, K = 10; '+('fixed cap 4 removed' if uncapped else rf'$\lambda_{{max}}={fixed_cap:g}$'))
    fig.tight_layout(rect=(0,0,1,.96))
    for ext in ('pdf','png','svg'):fig.savefig(directory/f'A3_density_lambda_k10.{ext}',dpi=200,bbox_inches='tight')
    plt.close(fig)
    aggregate=[]
    for rho in levels:
        cell=[r for r in rows if r['requested_density']==rho]
        aggregate.append(dict(density=rho,packets=len(cell),mean_lambda=float(np.mean([r['lambda_sp'] for r in cell])),
            median_lambda=float(np.median([r['lambda_sp'] for r in cell])),max_lambda=max(r['lambda_sp'] for r in cell),
            count_at_4=sum(r['at_value_4'] for r in cell),count_above_4=sum(r['above_4'] for r in cell),
            count_at_global_cap=int(sum(np.isclose(r['lambda_sp'],fixed_cap,rtol=0,atol=1e-9) for r in cell)) if fixed_cap is not None else None,
            count_at_individual_cap=sum(r['at_individual_cap'] for r in cell),count_at_zero=sum(r['at_zero'] for r in cell)))
    n.a.write_json(directory/'A3_density_lambda_k10_figure_manifest.json',dict(policy=manifest['sp_policy'],
        timing_axis='actual_arrival_density',revision_hash=manifest['revision_hash'],collision_order=10,
        scenes_per_density=scenes_per_density,packets=len(rows),all_available_packets=len(all_rows),source_positions=positions,
        selected_repeat=repeat,
        paired_sources_powers_and_phases=True,statistics=['per-position arithmetic mean of all 16 paired scenes' if repeat is None
            else 'raw per-packet values from one paired repeat; one scene at each density'],
        mean_only=repeat is None,no_filter_on_decode_success=True,global_lambda_bound=fixed_cap,
        fixed_cap_4_removed=uncapped,individual_reliability_bounds_preserved=True,
        color_scale='symlog (linear below 1)' if uncapped else 'linear',color_max=color_max,
        lambda_does_not_need_to_increase_monotonically=True,aggregate=aggregate,
        provenance='Native-IQ superposition with controlled timing/CFO; all packets scored, not just successful decodes'))
    print(json.dumps(aggregate,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'real_usrp_outputs/revision_a3_actual_density')
    parser.add_argument('--repeat',type=int,help='Plot all raw values for one paired repeat instead of the mean')
    args=parser.parse_args();render(args.out,repeat=args.repeat)
