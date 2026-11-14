#!/usr/bin/env python3
"""Outcome-based collision boundaries with explicit fixed-pool replay scope."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/boundary_fairness_mpl')
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import argparse,json,csv,hashlib,subprocess
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from PIL import Image,ImageOps,ImageDraw
from scipy.stats import beta

OUT=ROOT/'real_usrp_outputs/collision_boundary_fairness_20261102'
METHODS=('sp','mrc','pcube','maloragw')
LABELS=dict(sp='SP-Decoder',mrc='MRC',pcube='PCube',maloragw='MaLoRaGW')
COLORS=dict(sp='#171717',mrc='#e17c05',pcube='#2878b5',maloragw='#9867b9')
MARKERS=dict(sp='o',mrc='s',pcube='^',maloragw='D')
KS=(2,4,6,8,10);WIDTHS=(2.,1.,.5,.25,.05,.01)
ANGLE_LABELS=('0–2','2–5','5–10','10–20','20–40','40–90')
ANCHORS=(2.,.25,.01)
FIGURES=[];AGG=[];NODE_ROWS=[];GAIN_ROWS=[]
TARGET_SNR=10.;COMPLETE=True


def write_csv(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def wilson(success,n,z=1.96):
    if not n:return (np.nan,np.nan)
    p=success/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return max(0.,center-half),min(1.,center+half)


def ci(values):
    x=np.asarray(values,dtype=float)
    if not len(x):return np.nan,np.nan,np.nan
    mean=float(x.mean())
    if np.all((x==0)|(x==1)):
        lo,hi=wilson(x.sum(),len(x));return mean,lo,hi
    if np.all((x==0)|(x==-1)):
        lo,hi=wilson((-x).sum(),len(x));return mean,-hi,-lo
    # Burst is the resampling unit, including all its correlated target packets.
    rng=np.random.default_rng(94527)
    means=x[rng.integers(0,len(x),(3000,len(x)))].mean(axis=1)
    lo,hi=np.quantile(means,[.025,.975]);return mean,float(lo),float(hi)


def paired_ci(values):
    """Bonferroni-combine exact gain/loss intervals; unseen harm stays possible."""
    x=np.asarray(values,float)
    if not len(x):return np.nan,np.nan,np.nan
    assert np.isin(x,(-1.,0.,1.)).all()
    def bound(count):
        n=len(x);tail=.05/4
        return (0. if count==0 else float(beta.ppf(tail,count,n-count+1)),
                1. if count==n else float(beta.ppf(1-tail,count+1,n-count)))
    gain_low,gain_high=bound(int(np.sum(x>0)))
    loss_low,loss_high=bound(int(np.sum(x<0)))
    return float(x.mean()),max(-1.,gain_low-loss_high),min(1.,gain_high-loss_low)


def save(fig,name,title,caption):
    caption=f'Target SNR = {TARGET_SNR:g} dB. '+caption
    if not COMPLETE:
        title='INCOMPLETE PREVIEW — '+title
        caption='PREVIEW: per-cell counts vary; sample counts below describe the planned full matrix. '+caption
    fig.suptitle(title,fontsize=13,y=.99)
    fig.text(.01,.005,caption,fontsize=8,color='#444444',ha='left',va='bottom')
    fig.tight_layout(rect=(0,.055,getattr(fig,'_content_right',1),.94))
    for ext in ('pdf','svg','png'):
        fig.savefig(OUT/'figures'/f'{name}.{ext}',dpi=200,bbox_inches='tight',facecolor='white')
    FIGURES.append(dict(name=name,title=title,caption=caption))
    plt.close(fig)


def style(ax):
    ax.set_ylim(0,1.02);ax.grid(alpha=.18);ax.set_axisbelow(True)
    ax.spines[['top','right']].set_visible(False)


def heatmap(ax,matrix,xlabels,ylabels,title):
    cmap=plt.get_cmap('viridis').copy();cmap.set_bad('#dddddd')
    im=ax.imshow(np.ma.masked_invalid(matrix),vmin=0,vmax=1,cmap=cmap,aspect='auto',origin='lower')
    ax.set(xticks=range(len(xlabels)),xticklabels=xlabels,yticks=range(len(ylabels)),yticklabels=ylabels,title=title)
    for y,x in np.ndindex(matrix.shape):
        v=matrix[y,x]
        ax.text(x,y,f'{v:.2f}' if np.isfinite(v) else 'N/A',ha='center',va='center',fontsize=9,
                color='white' if np.isfinite(v) and v<.45 else 'black')
        if np.isfinite(v) and v>=.9:
            ax.add_patch(Rectangle((x-.49,y-.49),.98,.98,fill=False,ec='#ed466d',lw=2.))
    return im


def load(partial=False):
    manifest=json.loads((OUT/'manifest.json').read_text());jobs=[];missing=[]
    policy_path=OUT/'certified_candidate_policy.json'
    candidate_policy=json.loads(policy_path.read_text()) if policy_path.exists() else None
    if not partial and (not candidate_policy or not candidate_policy['complete']):
        raise ValueError('Final plots require certified-candidate baseline replay for the full matrix')
    # Importing the runner also supplies exactly the same canonical job-key function.
    from real_collision_experiment.paper_experiments import run_boundary_fairness as b
    for spec in manifest['jobs']:
        path=OUT/'jobs'/(b.n.a.job_key(spec)+'.json')
        if not path.exists():missing.append(path.name);continue
        job=json.loads(path.read_text())
        if job.get('revision')!=manifest['revision']:missing.append(path.name);continue
        job['job_id']=path.stem
        correction_path=OUT/'certified_candidate_results'/path.name
        if correction_path.exists():
            correction=json.loads(correction_path.read_text())
            assert correction['raw_job_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
            if candidate_policy:assert correction['adapter_sha256']==candidate_policy['adapter_sha256']
            for target in job['targets']:
                target['methods'].update(correction['targets'].get(str(target['target_index']),{}))
                target.update(correction.get('diagnostics',{}).get(str(target['target_index']),{}))
                if not partial and spec['family']=='geometry':assert 'isolated_reference_same_cap_any_success' in target
            job['original_blind_group_count']=correction['original_blind_group_count']
        elif not partial:raise ValueError(f'Missing certified-candidate replay for {path.name}')
        assert len(job['truth'])==spec['k']
        assert len({t['position'] for t in job['truth']})==spec['k']
        assert len(job['targets'])==len(spec['focus'])
        assert job['noise_budget']['min_residual_eigenvalue']>=-1e-9
        for t in job['targets']:
            assert 0<=t['lambda_sp']<=t['lambda_cap']+1e-8
            assert all(0<=t['methods'][m]['ser']<=1 for m in METHODS)
        jobs.append(job)
    if missing and not partial:raise ValueError(f'{len(missing)} unfinished jobs; final figures require the full frozen matrix')
    return manifest,jobs,missing


def temporal(jobs):
    selected=[j for j in jobs if j['spec']['family']=='temporal' and j['spec']['repeat']<24]
    groups=defaultdict(list)
    for j in selected:groups[j['spec']['k'],j['spec']['width_ratio']].append(j)
    fig,axes=plt.subplots(1,5,figsize=(17,3.7),sharey=True)
    for ax,k in zip(axes,KS):
        for m in METHODS:
            xs=[];ys=[];los=[];his=[]
            for width in WIDTHS:
                cell=groups[k,width]
                if not cell:continue
                vals=[np.mean([t['methods'][m]['delivered'] for t in j['targets']]) for j in cell]
                v,lo,hi=ci(vals)
                xs.append(np.mean([t['mean_concurrency'] for j in cell for t in j['targets']]))
                ys.append(v);los.append(lo);his.append(hi)
                AGG.append(dict(family='temporal',k=k,width_ratio=width,method=m,pdr=v,ci_low=lo,ci_high=hi,
                    bursts=len(cell),packets=sum(len(j['targets']) for j in cell),mean_concurrency=xs[-1]))
            ax.plot(xs,ys,color=COLORS[m],marker=MARKERS[m],label=LABELS[m],lw=1.7,ms=4)
            ax.fill_between(xs,los,his,color=COLORS[m],alpha=.09)
        style(ax);ax.set(title=f'K = {k}',xlabel='Mean concurrent packets\nover target payload')
    axes[0].set_ylabel('Packet delivery ratio');axes[-1].legend(fontsize=8,loc='lower left')
    save(fig,'01_temporal_load_curves','Performance as temporal overlap increases',
        'Equal received packet powers; same 24 source/phase draws across timing; 95% burst-level intervals. Controlled start/CFO; measured-IQ replay.')
    fig,axes=plt.subplots(2,2,figsize=(11,8),sharex=True,sharey=True)
    for ax,m in zip(axes.flat,METHODS):
        matrix=np.full((5,6),np.nan)
        for y,k in enumerate(KS):
            for x,width in enumerate(WIDTHS):
                cell=groups[k,width]
                if cell:matrix[y,x]=np.mean([t['methods'][m]['delivered'] for j in cell for t in j['targets']])
        im=heatmap(ax,matrix,[f'{w:g}' for w in WIDTHS],KS,LABELS[m])
        ax.set(xlabel='Start span W / payload duration → more crowded',ylabel='Packets in burst K')
    fig.colorbar(im,ax=axes.ravel().tolist(),label='PDR',fraction=.025,pad=.03)
    # Allocate the colorbar manually so tight_layout cannot overlap the panels.
    fig.delaxes(fig.axes[-1]);fig.subplots_adjust(right=.90)
    cax=fig.add_axes([.93,.19,.018,.58]);fig.colorbar(im,cax=cax,label='PDR')
    fig._content_right=.90
    save(fig,'02_temporal_pdr_heatmaps','Temporal collision limits: matched observations for four receivers',
        '24 paired bursts/cell; all K targets scored. Pink frames: observed PDR ≥ 0.90, not a reliability guarantee. Shared 0–1 scale.')


def spatial(jobs,manifest):
    groups=defaultdict(list)
    for j in jobs:
        s=j['spec']
        if s['family']=='geometry':groups[s['individual_sir_db'],s['k'],s['angle_low']].append(j)
    lows=(0.,2.,5.,10.,20.,40.)
    for sir in (0.,-5.):
        fig,axes=plt.subplots(2,2,figsize=(10.5,8),sharex=True,sharey=True)
        for ax,m in zip(axes.flat,METHODS):
            matrix=np.full((6,5),np.nan)
            for y,low in enumerate(lows):
                for x,k in enumerate(KS):
                    cell=groups[sir,k,low]
                    if not cell:continue
                    vals=[j['targets'][0]['methods'][m]['delivered'] for j in cell]
                    v,lo,hi=ci(vals);matrix[y,x]=v
                    AGG.append(dict(family='geometry',individual_sir_db=sir,k=k,angle_low=low,method=m,
                        pdr=v,ci_low=lo,ci_high=hi,bursts=len(cell),packets=len(cell),
                        target_positions=len({j['targets'][0]['position'] for j in cell}),
                        measured_groups=len({tuple(j['spec']['sources']) for j in cell})))
            im=heatmap(ax,matrix,KS,ANGLE_LABELS,LABELS[m])
            ax.set(xlabel='Packets in burst K',ylabel='Minimum active channel angle (°)')
        cax=fig.add_axes([.94,.20,.018,.57]);fig.colorbar(im,cax=cax,label='PDR')
        fig._content_right=.90
        tag='equal_power' if sir==0 else 'strong_interference'
        save(fig,f'03_spatial_boundary_{tag}',f'Spatial collision boundary; per-interferer SIR = {sir:g} dB',
            'W = 0.05 × payload duration; 32 target trials/cell. Grey: no measured source combination. Pink: observed PDR ≥ 0.90. See coverage figure.')
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    available=manifest['geometry_availability']
    for ax,field,title in zip(axes,('eligible_target_positions','near_source_pairs'),('Eligible target positions','Distinct near source-packet pairs')):
        matrix=np.array([[next(a[field] for a in available if a['k']==k and a['angle_low']==low) for k in KS] for low in lows])
        im=ax.imshow(matrix,origin='lower',cmap='Blues',aspect='auto')
        ax.set(xticks=range(5),xticklabels=KS,yticks=range(6),yticklabels=ANGLE_LABELS,title=title,
               xlabel='Packets in burst K',ylabel='Minimum active channel angle (°)')
        for y,x in np.ndindex(matrix.shape):ax.text(x,y,str(matrix[y,x]),ha='center',va='center',color='white' if matrix[y,x]>matrix.max()*.6 else 'black')
    save(fig,'04_geometry_coverage','What the measured channel pool actually supports',
        '22 retained packets from 10 physical positions; the 0–2° bin has one physical position pair. Noise/phase repetitions add no new deployments.')
    return groups


def fairness(jobs):
    groups=defaultdict(list)
    for j in jobs:
        s=j['spec']
        if s['family']=='temporal' and s['k']==10 and s['width_ratio'] in ANCHORS:
            for t in j['targets']:groups[s['width_ratio'],t['position']].append((s['repeat'],t))
    positions=sorted({p for _,p in groups})
    if not positions:return
    fig,axes=plt.subplots(1,3,figsize=(13,4),sharex=True,sharey=True)
    for ax,width,title in zip(axes,ANCHORS,('Partial overlap','Intermediate overlap','Nearly full overlap')):
        for m in METHODS:
            vals=[]
            for pos in positions:
                cell=groups[width,pos]
                if not cell:continue
                v,lo,hi=ci([t['methods'][m]['delivered'] for _,t in cell]);vals.append(v)
                angles=[t['active_min_angle_deg'] for _,t in cell if t['active_min_angle_deg'] is not None]
                NODE_ROWS.append(dict(position=pos,width_ratio=width,method=m,pdr=v,ci_low=lo,ci_high=hi,
                    trials=len(cell),median_active_min_angle_deg=float(np.median(angles)) if angles else None))
            x=np.sort(vals);y=np.arange(1,len(x)+1)/len(x)
            ax.step(np.r_[0,x,1],np.r_[0,y,1],where='post',color=COLORS[m],label=LABELS[m],lw=1.9)
        style(ax);ax.set(title=f'{title}\nW/Tpayload = {width:g}',xlabel='Per-position PDR',xlim=(0,1))
    axes[0].set_ylabel('Fraction of 10 measured positions');axes[-1].legend(fontsize=8,loc='upper left')
    save(fig,'05_position_pdr_cdf','Does average performance hide disadvantaged positions?',
        'K = 10; 128 balanced trials/position/condition; zero-success positions retained. Conditional measured-IQ replay, not a 24-node deployment CDF.')
    fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    heavy=[r for r in NODE_ROWS if r['width_ratio']==.01]
    for m in METHODS:
        rows=sorted([r for r in heavy if r['method']==m],key=lambda r:r['median_active_min_angle_deg'])
        if not rows:continue
        x=np.array([r['median_active_min_angle_deg'] for r in rows]);y=np.array([r['pdr'] for r in rows])
        axes[0].errorbar(x,y,yerr=[y-[r['ci_low'] for r in rows],[r['ci_high'] for r in rows]-y],
            fmt=MARKERS[m],color=COLORS[m],label=LABELS[m],alpha=.85,capsize=2,ms=5)
    style(axes[0]);axes[0].set(xlabel='Median nearest active channel angle (°)',ylabel='Per-position PDR')
    axes[0].legend(fontsize=8)
    for pos in positions:
        cell=sorted(groups[.01,pos]);sp=np.array([t['methods']['sp']['delivered'] for _,t in cell],float)
        x=np.median([t['active_min_angle_deg'] for _,t in cell]);mrc=np.array([t['methods']['mrc']['delivered'] for _,t in cell],float)
        diff=sp-mrc;v,lo,hi=paired_ci(diff)
        axes[1].errorbar(x,v,yerr=[[v-lo],[hi-v]],fmt='o',color=COLORS['sp'],capsize=3)
        axes[1].annotate(pos.replace('pos',''),(x,v),xytext=(4,4),textcoords='offset points',fontsize=8)
        for baseline in ('mrc','pcube','maloragw'):
            delta=sp-np.array([t['methods'][baseline]['delivered'] for _,t in cell],float)
            mean,lower,upper=paired_ci(delta)
            GAIN_ROWS.append(dict(position=pos,baseline=baseline,pdr_gain=mean,ci_low=lower,ci_high=upper,trials=len(cell),median_min_angle=x))
    axes[1].axhline(0,color='#999999',ls='--');axes[1].grid(alpha=.2)
    axes[1].set(xlabel='Median nearest active channel angle (°)',ylabel='PDR gain: SP − MRC')
    save(fig,'06_position_angle_and_gain','Spatial separation and the positions that gain or lose',
        'K = 10, nearly full overlap; same 128 draws. Left: Wilson PDR intervals; right: conservative paired intervals allowing unobserved gains and losses.')
    fig,axes=plt.subplots(1,3,figsize=(12,5.2),sharey=True)
    for ax,baseline in zip(axes,('mrc','pcube','maloragw')):
        rows=sorted([r for r in GAIN_ROWS if r['baseline']==baseline],key=lambda r:r['position'])
        for i,row in enumerate(rows):
            v=row['pdr_gain'];ax.errorbar(v,i,xerr=[[v-row['ci_low']],[row['ci_high']-v]],fmt='o',
                color='#197f62' if v>=0 else '#cc4555',capsize=3)
        ax.axvline(0,color='#999999',ls='--');ax.grid(axis='x',alpha=.2)
        ax.set(yticks=range(len(positions)),yticklabels=positions,title=f'SP − {LABELS[baseline]}',xlabel='Paired PDR difference')
    save(fig,'07_position_gain_audit','Every position, including losses against each baseline',
        'K = 10; nearly full overlap; 128 matched trials/position. Green/red indicate positive/negative observed differences, not significance.')
    return groups


def lambda_maps(groups,manifest):
    grid=np.array(manifest['lambda_grid']);lows=(0.,2.,5.,10.,20.,40.)
    fig,axes=plt.subplots(1,3,figsize=(14,5),sharey=True)
    diagnostic_rows=[]
    for ax,k in zip(axes,(4,6,10)):
        matrix=np.full((6,len(grid)),np.nan);admissible_matrix=np.full(matrix.shape,np.nan);medians=[]
        for y,low in enumerate(lows):
            cell=groups[-5.,k,low]
            if not cell:continue
            targets=[j['targets'][0] for j in cell]
            for x,value in enumerate(grid):
                entries=[next(d for d in t['lambda_diagnostic'] if d['lambda_value']==value) for t in targets]
                success=sum(bool(d['admissible'] and d['delivered']) for d in entries)
                matrix[y,x]=success/len(entries)
                admissible_matrix[y,x]=sum(d['admissible'] for d in entries)
                diagnostic_rows.append(dict(k=k,angle_low=low,lambda_value=value,scenes=len(entries),
                    admissible=sum(d['admissible'] for d in entries),admissible_and_delivered=success,rate=matrix[y,x]))
            medians.append((y,float(np.median([t['lambda_sp'] for t in targets]))))
        cmap=plt.get_cmap('viridis').copy();cmap.set_bad('#dddddd')
        im=ax.imshow(np.ma.masked_invalid(matrix),origin='lower',aspect='auto',vmin=0,vmax=1,cmap=cmap)
        for y,x in np.ndindex(matrix.shape):
            if admissible_matrix[y,x]==0:ax.text(x,y,'×',ha='center',va='center',color='white',fontsize=8)
        tick=[0,2,5,9,13,16];ax.set(xticks=tick,xticklabels=[f'{grid[i]:g}' for i in tick],
            yticks=range(6),yticklabels=ANGLE_LABELS,xlabel='Offline tested λ (nonuniform grid)',title=f'K = {k}')
        ax.axvline(9,color='white',ls='--',lw=1)
        for y,med in medians:
            x=np.interp(np.log1p(med),np.log1p(grid),np.arange(len(grid)))
            ax.plot(x,y,'o',mec='#ff4b8b',mfc='none',ms=8,mew=1.5)
        ax.set_ylabel('Minimum active channel angle (°)')
    cax=fig.add_axes([.94,.2,.015,.59]);fig.colorbar(im,cax=cax,label='Admissible and decoded / all trials')
    fig._content_right=.90
    save(fig,'08_lambda_recoverable_region','Where does a usable weight still exist? Offline λ diagnostic',
        'SIR −5 dB. Dashed: λ=4; circles: median online λ; ×: no trial admits λ. Reliability bound retained; cap relaxed to 40 only offline. λ=0 uses MRC.')
    write_csv(OUT/'lambda_grid_summary.csv',diagnostic_rows)
    fig,axes=plt.subplots(1,3,figsize=(14,4.3),sharex=True,sharey=True)
    for ax,low,title in zip(axes,(0.,5.,20.),('Nearest angle 0–2°','Nearest angle 5–10°','Nearest angle 20–40°')):
        series=defaultdict(list)
        for k in KS:
            cell=groups[-5.,k,low]
            if not cell:continue
            ts=[j['targets'][0] for j in cell]
            values={
                'MRC':[t['methods']['mrc']['delivered'] for t in ts],
                'Online SP':[t['methods']['sp']['delivered'] for t in ts],
                'Mixed ref: any tested λ':[t['methods']['sp']['delivered'] or any(d['admissible'] and d['delivered'] for d in t['lambda_diagnostic']) for t in ts],
                'Isolated ref: same allowed λ':[t.get('isolated_reference_same_cap_any_success',t['clean_reference_tested_grid_any_success']) for t in ts]}
            for label,values_ in values.items():series[label].append((k,float(np.mean(values_))))
        for (label,values),color,ls in zip(series.items(),('#e17c05','#171717','#2878b5','#169c80'),('--','-','-.',':')):
            ax.plot([v[0] for v in values],[v[1] for v in values],marker='o',label=label,color=color,ls=ls,ms=4)
        style(ax);ax.set(title=title,xlabel='Packets in burst K',xticks=KS)
    axes[0].set_ylabel('Fraction of target trials decoded');axes[-1].legend(fontsize=7,loc='best')
    save(fig,'09_reference_and_weight_diagnostic','Separate reference limitations from weight-selection limitations',
        'Reference comparison uses the same allowed weights and payload observation. Any-weight success is offline truth-assisted, not deployable or a universal capacity bound.')


def symbol_effect(jobs):
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for width,color in zip((2.,.25,.01),('#2878b5','#e17c05','#171717')):
        cells=[[t for j in jobs if j['spec']['family']=='temporal' and j['spec']['repeat']<24 and
                j['spec']['k']==k and j['spec']['width_ratio']==width for t in j['targets']] for k in KS]
        for ax,field in zip(axes,('rescued_symbols','harmed_symbols')):
            values=[sum(t[field] for t in ts)/max(1,sum(t['methods']['sp']['symbol_count'] for t in ts)) for ts in cells]
            ax.plot(KS,values,'o-',color=color,label=f'W/Tpayload={width:g}')
            ax.grid(alpha=.2);ax.set(xlabel='Packets in burst K',ylabel='Fraction of all payload symbols',xticks=KS)
    axes[0].set_title('MRC wrong → SP correct');axes[1].set_title('MRC correct → SP wrong');axes[1].legend(fontsize=8)
    save(fig,'10_symbol_rescue_and_damage','What signed spatial evidence repairs, and what it damages',
        '24 paired bursts/cell; all payload symbols, including failed packets. Rates use the same all-symbol denominator; no conditioning on MRC errors.')


def gain_maps(groups):
    lows=(0.,2.,5.,10.,20.,40.);matrices={};gain_rows=[]
    for sir in (0.,-5.):
        for baseline in ('mrc','pcube','maloragw'):
            matrix=np.full((6,5),np.nan)
            for y,low in enumerate(lows):
                for x,k in enumerate(KS):
                    cell=groups[sir,k,low]
                    if not cell:continue
                    differences=[float(j['targets'][0]['methods']['sp']['delivered'])-
                                 float(j['targets'][0]['methods'][baseline]['delivered']) for j in cell]
                    mean,lo,hi=paired_ci(differences);matrix[y,x]=100*mean
                    gain_rows.append(dict(individual_sir_db=sir,k=k,angle_low=low,baseline=baseline,
                        paired_pdr_difference=mean,ci_low=lo,ci_high=hi,trials=len(cell)))
            matrices[sir,baseline]=matrix
    maximum=max([abs(v) for mat in matrices.values() for v in mat.flat if np.isfinite(v)]+[1.])
    limit=float(np.ceil(maximum/10)*10)
    fig,axes=plt.subplots(2,3,figsize=(14,8),sharex=True,sharey=True)
    cmap=plt.get_cmap('RdBu').copy();cmap.set_bad('#dddddd')
    for row,sir in enumerate((0.,-5.)):
        for col,baseline in enumerate(('mrc','pcube','maloragw')):
            ax=axes[row,col];matrix=matrices[sir,baseline]
            im=ax.imshow(np.ma.masked_invalid(matrix),origin='lower',aspect='auto',cmap=cmap,vmin=-limit,vmax=limit)
            ax.set(xticks=range(5),xticklabels=KS,yticks=range(6),yticklabels=ANGLE_LABELS,
                xlabel='Packets in burst K',ylabel='Minimum active channel angle (°)',
                title=f'SP − {LABELS[baseline]}; SIR {sir:g} dB')
            for y,x in np.ndindex(matrix.shape):
                v=matrix[y,x];ax.text(x,y,f'{v:+.0f}' if np.isfinite(v) else 'N/A',ha='center',va='center',fontsize=8,
                    color='white' if np.isfinite(v) and abs(v)>limit*.55 else 'black')
    cax=fig.add_axes([.94,.19,.015,.6]);fig.colorbar(im,cax=cax,label='PDR difference (percentage points)')
    fig._content_right=.90
    save(fig,'11_paired_gain_heatmaps','Direct comparisons: where SP gains and where it loses',
        'Blue: SP higher; red: baseline higher. One shared symmetric scale from the full matrix; cell values in percentage points. Paired intervals in spatial_gain_summary.csv.')
    write_csv(OUT/'spatial_gain_summary.csv',gain_rows)


def calibration(jobs,manifest):
    rows=[]
    for j in jobs:
        if j['spec']['family']=='isolated':
            t=j['targets'][0]
            for m in METHODS:rows.append(dict(source=t['source_index'],position=t['position'],method=m,delivered=t['methods'][m]['delivered']))
    write_csv(OUT/'isolated_link_results.csv',rows)
    result={m:dict(success=sum(r['delivered'] for r in rows if r['method']==m),trials=sum(r['method']==m for r in rows)) for m in METHODS}
    return result


def findings(jobs,summary):
    boundaries=[]
    for sir in (0.,-5.):
        for low,label in zip((0.,2.,5.,10.,20.,40.),ANGLE_LABELS):
            row=dict(individual_sir_db=sir,minimum_angle_bin=label)
            for method in METHODS:
                valid=[r['k'] for r in AGG if r['family']=='geometry' and r['individual_sir_db']==sir
                       and r['angle_low']==low and r['method']==method and r['pdr']>=.9]
                row[method+'_observed_PDR_ge90_K']=';'.join(str(k) for k in valid) if valid else 'none'
            boundaries.append(row)
    write_csv(OUT/'observed_90pct_regions.csv',boundaries)
    fairness_summary={}
    for method in METHODS:
        rows=[r for r in NODE_ROWS if r['method']==method and r['width_ratio']==.01]
        if rows:fairness_summary[method]=dict(mean_pdr=float(np.mean([r['pdr'] for r in rows])),
            worst_position_pdr=min(r['pdr'] for r in rows),best_position_pdr=max(r['pdr'] for r in rows))
    diagnostic={}
    for sir in (0.,-5.):
        ts=[j['targets'][0] for j in jobs if j['spec']['family']=='geometry' and j['spec']['individual_sir_db']==sir]
        if not ts:continue
        online=[t['methods']['sp']['delivered'] for t in ts]
        mixed=[bool(t['methods']['sp']['delivered'] or any(d['admissible'] and d['delivered'] for d in t['lambda_diagnostic'])) for t in ts]
        isolated=[t.get('isolated_reference_same_cap_any_success',t['clean_reference_tested_grid_any_success']) for t in ts]
        diagnostic[str(sir)]=dict(trials=len(ts),online_SP_success=sum(online),mixed_reference_any_tested_weight_success=sum(mixed),
            isolated_reference_any_tested_weight_success=sum(isolated),
            mixed_grid_recovers_online_failure=sum(a and not b for a,b in zip(mixed,online)))
    changed={m:dict(gained=0,lost=0) for m in ('pcube','maloragw')};affected=0
    for path in (OUT/'certified_candidate_results').glob('*.json'):
        c=json.loads(path.read_text())
        if not c['corrected']:continue
        affected+=1;raw=json.loads((OUT/'jobs'/path.name).read_text())
        for t in raw['targets']:
            after=c['targets'][str(t['target_index'])]
            for method in changed:
                a=t['methods'][method]['delivered'];b=after[method]['delivered']
                changed[method]['gained']+=int(b and not a);changed[method]['lost']+=int(a and not b)
    lines=['# 本轮结果怎么读','',
        f'固定矩阵：{summary["completed_jobs"]}个场景，{summary["targets"]}个目标包；目标SNR=10dB。',
        '22段实测源包、10个位置，所有源载荷彼此不同。四方法单包校准均为66/66。',
        '这是受控准确起点/CFO下的原始IQ叠加实验；不把它表述为24节点端到端空口结果。','',
        '## 从部分重叠到近全重叠','',
        '同一24次主样本配对；表中为W/Tpayload从2降至0.01的PDR。','',
        '|K|SP|MRC|PCube|MaLoRaGW|','|---:|---:|---:|---:|---:|']
    for k in KS:
        cells=[]
        for method in METHODS:
            pair=[]
            for width in (2.,.01):
                matches=[r for r in AGG if r['family']=='temporal' and r['k']==k and r['width_ratio']==width and r['method']==method]
                pair.append(f'{matches[0]["pdr"]:.1%}' if matches else '待完成')
            cells.append(' → '.join(pair))
        lines.append('|'+str(k)+'|'+'|'.join(cells)+'|')
    lines+=['','## 空间边界：强干扰档','',
        '以下列出观察PDR≥90%的受测K，不强制单调、不跨空白格外推；32次目标试验/格，置信区间见cell_summary.csv。','',
        '|最小活跃夹角|SP|MRC|PCube|MaLoRaGW|','|---|---|---|---|---|']
    for row in boundaries:
        if row['individual_sir_db']!=-5.:continue
        lines.append('|'+row['minimum_angle_bin']+'°|'+'|'.join(row[m+'_observed_PDR_ge90_K'].replace(';',', ') for m in METHODS)+'|')
    lines+=['','## 逐位置结果：K=10，近全重叠','',
        '每位置128次，10个位置全部保留，均值为等权位置平均。','',
        '|方法|平均PDR|最低位置PDR|最高位置PDR|','|---|---:|---:|---:|']
    for method,row in fairness_summary.items():
        lines.append(f'|{LABELS[method]}|{row["mean_pdr"]:.1%}|{row["worst_position_pdr"]:.1%}|{row["best_position_pdr"]:.1%}|')
    lines+=['','SP低于各基线的位置数量与逐位置配对区间见position_gains.csv；不能由平均增益推断每个节点均受益。','',
        '## λ诊断','',
        '任一测试权重成功是离线载荷真值辅助诊断，不是在线选择算法，不是对全部连续权重的保证。各条件均保留全部目标。','',
        '|每干扰者SIR|目标试验|在线SP成功|混合参考下任一允许测试权重成功|单包校准参考下任一测试权重成功|',
        '|---:|---:|---:|---:|---:|']
    for sir,row in diagnostic.items():
        lines.append(f'|{float(sir):g}dB|{row["trials"]}|{row["online_SP_success"]}|{row["mixed_reference_any_tested_weight_success"]}|{row["isolated_reference_any_tested_weight_success"]}|')
    lines+=['','## 比较公平性审计','',
        f'{affected}个场景的盲前端别名合并会影响确认候选列表。主图统一使用确认候选适配，原始结果不删除。',
        f'该适配相对原始结果的增减：{changed}。不按场景或解码结果选择版本。','',
        '建议主文优先使用01时间曲线、03强干扰空间边界、05逐位置CDF和06角度关联；08/09解释λ与参考的限制，其余作完整对照与附录。',
        '经验边界取决于此处的SNR、SIR、时序、PHY和实测源库。小角度位置对较少，不能把噪声/初相重复数量当作独立部署数量。']
    (OUT/'FINDINGS.md').write_text('\n'.join(lines)+'\n')
    return dict(observed_90pct_regions=boundaries,fairness= fairness_summary,lambda_diagnostic=diagnostic,
        certified_candidate_affected_scenes=affected,certified_candidate_baseline_changes=changed)


def main():
    global TARGET_SNR,COMPLETE
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args()
    (OUT/'figures').mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':10,'pdf.fonttype':42,'svg.fonttype':'none','axes.titleweight':'medium'})
    manifest,jobs,missing=load(args.partial)
    policy_path=OUT/'certified_candidate_policy.json'
    policy=json.loads(policy_path.read_text()) if policy_path.exists() else None
    TARGET_SNR=manifest['main_snr_db'];COMPLETE=not missing and bool(policy and policy['complete'])
    temporal(jobs);groups=spatial(jobs,manifest);fairness(jobs);lambda_maps(groups,manifest);symbol_effect(jobs);gain_maps(groups)
    isolated=calibration(jobs,manifest)
    write_csv(OUT/'cell_summary.csv',AGG);write_csv(OUT/'position_pdr.csv',NODE_ROWS);write_csv(OUT/'position_gains.csv',GAIN_ROWS)
    packet_rows=[];lambda_trial_rows=[]
    cfg=json.loads((OUT/'input_source_audit.json').read_text())['config']
    samples_per_symbol=2**cfg['sf']*cfg['sample_rate_hz']/cfg['bw_hz']
    for j in jobs:
        s=j['spec']
        for t in j['targets']:
            base={k:v for k,v in t.items() if not isinstance(v,(dict,list))}
            source=j['truth'][t['target_index']]
            payload_start=source['start_sample']+(cfg['preamble_len']+4.25)*samples_per_symbol
            end=source['start_sample']+(cfg['preamble_len']+4.25+t['methods']['sp']['symbol_count'])*samples_per_symbol
            active=[other for i,other in enumerate(j['truth']) if i!=t['target_index'] and other['start_sample']<end
                and other['start_sample']+(cfg['preamble_len']+4.25+t['methods']['sp']['symbol_count'])*samples_per_symbol>payload_start]
            base.update(job_id=j['job_id'],job_family=s['family'],k=s['k'],repeat=s['repeat'],width_ratio=s['width_ratio'],
                individual_sir_db=s.get('individual_sir_db'),target_snr_db=s['snr_db'],
                original_blind_group_count=j.get('original_blind_group_count'),certified_candidates=s['k'],
                target_native_cfo_bins=source['cfo_bins'],
                min_active_cfo_separation_bins=min([abs(other['cfo_bins']-source['cfo_bins']) for other in active],default=None),
                actual_start_span_symbols=float(np.ptp([other['start_sample'] for other in j['truth']])/samples_per_symbol))
            for m in METHODS:base[m+'_delivered']=t['methods'][m]['delivered'];base[m+'_ser']=t['methods'][m]['ser']
            for name in ('exact_all_symbol_interval','extended_all_symbol_interval'):
                for field,value in t[name].items():base[name+'_'+field]=value
            for entry in t['lambda_diagnostic']:
                lambda_trial_rows.append(dict(job_id=j['job_id'],family=s['family'],k=s['k'],repeat=s['repeat'],
                    target_index=t['target_index'],position=t['position'],width_ratio=s['width_ratio'],
                    individual_sir_db=s.get('individual_sir_db'),angle_low=s.get('angle_low'),
                    online_lambda=t['lambda_sp'],diagnostic_cap=t['diagnostic_cap'],**entry))
            packet_rows.append(base)
    write_csv(OUT/'per_target.csv',packet_rows)
    write_csv(OUT/'lambda_diagnostics_per_trial.csv',lambda_trial_rows)
    summary=dict(complete=COMPLETE,completed_jobs=len(jobs),expected_jobs=len(manifest['jobs']),targets=len(packet_rows),
        main_snr_db=manifest['main_snr_db'],isolated_calibration=isolated,revision=manifest['revision'],
        source_positions=10,actual_24_node_data=False,conditional_controlled_synchronization=True,
        no_outcome_based_scene_filter=True,no_geometric_channel_rotation=True,no_waveform_regeneration=True,
        temporal_main_bursts_per_cell=24,geometry_target_trials_per_cell=32,fairness_trials_per_position=128,
        geometry_missing_cells=[r for r in manifest['geometry_availability'] if r['eligible_target_sources']==0],
        per_position_gain_summary={m:dict(positions=sum(r['baseline']==m for r in GAIN_ROWS),
            positions_lower_than_baseline=sum(r['baseline']==m and r['pdr_gain']<0 for r in GAIN_ROWS),
            mean_gain=float(np.mean([r['pdr_gain'] for r in GAIN_ROWS if r['baseline']==m]))) for m in ('mrc','pcube','maloragw')},
        figures=FIGURES,figure_sha256={f['name']:hashlib.sha256((OUT/'figures'/(f['name']+'.pdf')).read_bytes()).hexdigest() for f in FIGURES},
        renderer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    policy_path=OUT/'certified_candidate_policy.json'
    summary['candidate_policy']=json.loads(policy_path.read_text()) if policy_path.exists() else None
    summary['outcome_details']=findings(jobs,summary)
    (OUT/'results_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    files=[OUT/'figures'/(f['name']+'.pdf') for f in FIGURES]
    subprocess.run(['pdfunite',*[str(p) for p in files],str(OUT/'all_boundary_fairness_figures.pdf')],check=True)
    thumbs=[]
    for f in FIGURES:
        im=Image.open(OUT/'figures'/(f['name']+'.png')).convert('RGB')
        tile=Image.new('RGB',(740,460),'white');im.thumbnail((720,420));tile.paste(im,((740-im.width)//2,25))
        ImageDraw.Draw(tile).text((8,4),f['name'],fill='black');thumbs.append(tile)
    sheet=Image.new('RGB',(1480,460*((len(thumbs)+1)//2)),'#e6e6e6')
    for i,tile in enumerate(thumbs):sheet.paste(tile,((i%2)*740,(i//2)*460))
    sheet.save(OUT/'all_figures_overview.png')
    lines=['# 碰撞边界与逐位置公平性：本轮完整结果','',
        f'状态：{"完整" if COMPLETE else "部分预览"}；{len(jobs)}/{len(manifest["jobs"])} 场景；{len(packet_rows)} 个目标包。',
        f'统一目标SNR={manifest["main_snr_db"]:g} dB；SF10/BW125k/1Msps/32B implicit/CR4/5。',
        '现有22个源包来自10个位置。所有图均为原始双通道IQ离线叠加、受控准确起点/CFO；不代表24节点空口实测。',
        '正式SP保持默认有界策略；40仅用于离线诊断。PCube使用已确认V3，其余基线保持当前实现。',
        '时间扫描每格24次配对；空间每个K/角度/SIR格32个目标试验；公平性每位置每条件128次。',
        '热图统一0–1色标。粉色框仅表示观察到的PDR≥90%，不是理论保证；置信区间和源覆盖另行报告。',
        '完整λ扫描含失败包；任一λ成功是离线真值辅助诊断，不能作为正式接收性能。','',
        '[全部图PDF](all_boundary_fairness_figures.pdf) | [总览](all_figures_overview.png)','',
        '## 单包校准','',json.dumps(isolated,ensure_ascii=False),'','## 图表','']
    for f in FIGURES:lines.append(f'- [{f["name"]}](figures/{f["name"]}.pdf)：{f["title"]}')
    lines+=['','## 可复现与审阅文件','',
        '`manifest.json`在解码前固定全部场景与源选择；`code_snapshot/`保存版本；`jobs/`保存逐包结果。',
        '`cell_summary.csv`含PDR/区间/样本量；`position_pdr.csv`含各位置分母；`position_gains.csv`保留负增益；',
        '`lambda_grid_summary.csv`含每个λ的有效与成功数；`lambda_diagnostics_per_trial.csv`含逐次未筛选扫描；`per_target.csv`含所有目标与失败包。',
        '本轮统计不把随机初相/补噪重复视作独立部署；最小角度关联不能独自解释节点全部差异。']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('figures','figure_sha256')},indent=2))


if __name__=='__main__':main()
