#!/usr/bin/env python3
"""Publish compact revision figures only from complete frozen input matrices."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/compact_revision_mpl')
from pathlib import Path
import sys,json,csv,hashlib,shutil,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image,ImageOps,ImageDraw
from real_collision_experiment.paper_experiments import run_compact_revision_20261106 as c
OUT=c.OUT;FIG=OUT/'figures';TABLE=OUT/'tables'
METHODS=c.METHODS;LABELS=['SP-Decoder','MRC','PCube','MaLoRaGW'];COLORS=['#16856a','#d88418','#2878b5','#a14e91'];MARKERS=['o','s','^','D']
ANGLE_LABELS=['0–2','2–5','5–10','10–20','20–40','40–90'];LOWS=[0,2,5,10,20,40]
FIGS=[];COUNTS=[]

def csvout(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def save(fig,name):
    images=[(ax,ax.images[0]) for ax in fig.axes if ax.images]
    if images:
        ax,im=images[-1];fig.colorbar(im,ax=ax,fraction=.05,pad=.04,label='PDR')
    fig.tight_layout()
    for ext in ('png','pdf','svg'):fig.savefig(FIG/f'{name}.{ext}',dpi=200,bbox_inches='tight')
    FIGS.append((name,fig))

def wilson(s,n):
    p=s/n;z=1.96;d=1+z*z/n;mid=(p+z*z/(2*n))/d;h=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return max(0,mid-h),min(1,mid+h)

def curve(ax,x,groups,xlabels=None):
    for m,label,color,marker in zip(METHODS,LABELS,COLORS,MARKERS):
        y=[];lo=[];hi=[]
        for group in groups:
            n=len(group);s=sum(r['metrics'][m]['delivered'] for r in group)
            a,b=wilson(s,n);y.append(s/n);lo.append(s/n-a);hi.append(b-s/n)
        ax.errorbar(x,y,yerr=[lo,hi],label=label,color=color,marker=marker,ms=4,lw=1.2,capsize=2)
    if xlabels is not None:ax.set_xticks(x,xlabels)
    ax.set_ylim(-.025,1.025);ax.set_ylabel('Conditional PDR');ax.grid(alpha=.2)

def heat(ax,matrix,xlabels,ylabels,title):
    values=np.array(matrix,float);cmap=plt.get_cmap('viridis').copy();cmap.set_bad('#dedede')
    im=ax.imshow(values,origin='lower',aspect='auto',vmin=0,vmax=1,cmap=cmap)
    ax.set_xticks(range(len(xlabels)),xlabels);ax.set_yticks(range(len(ylabels)),ylabels);ax.set_title(title)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            v=values[i,j];ax.text(j,i,'N/A' if np.isnan(v) else f'{v:.2f}',ha='center',va='center',fontsize=8,color='white' if not np.isnan(v) and v<.5 else 'black')
    return im

def render_boundary():
    # Fig13 is a rearrangement of the already paired, audited boundary matrix.
    boundary=list(csv.DictReader((c.b.OUT/'cell_summary.csv').open()))
    def bcell(family,method,k,**kwargs):
        return next((r for r in boundary if r['family']==family and r['method']==method and int(r['k'])==k and all(r.get(key) and float(r[key])==v for key,v in kwargs.items())),None)
    fig,axes=plt.subplots(1,3,figsize=(12.4,3.35))
    for method,label,color,marker in zip(METHODS,LABELS,COLORS,MARKERS):
        rr=[bcell('temporal',method,6,width_ratio=w) for w in c.b.WIDTHS]
        x=[float(r['mean_concurrency']) for r in rr];y=np.array([float(r['pdr']) for r in rr]);lo=np.array([float(r['ci_low']) for r in rr]);hi=np.array([float(r['ci_high']) for r in rr])
        axes[0].errorbar(x,y,yerr=[y-lo,hi-y],color=color,marker=marker,ms=4,label=label,capsize=2)
        rr=[bcell('geometry',method,6,individual_sir_db=-5,angle_low=lo) for lo in LOWS]
        y=np.array([float(r['pdr']) for r in rr]);lo=np.array([float(r['ci_low']) for r in rr]);hi=np.array([float(r['ci_high']) for r in rr])
        axes[1].errorbar(range(6),y,yerr=[y-lo,hi-y],color=color,marker=marker,ms=4,capsize=2)
    axes[0].set(xlabel='Mean active frames during target payload',ylabel='Conditional PDR',title='(a) K=6, equal received power',ylim=(-.025,1.025));axes[0].legend(fontsize=8)
    axes[1].set(xlabel='Minimum active angle bin (°)',ylabel='Conditional PDR',title='(b) K=6, individual SIR=-5 dB',ylim=(-.025,1.025));axes[1].set_xticks(range(6),ANGLE_LABELS)
    def matrix(method,sir):
        return [[float(r['pdr']) if (r:=bcell('geometry',method,k,individual_sir_db=sir,angle_low=lo)) else np.nan for k in c.b.KS] for lo in LOWS]
    heat(axes[2],matrix('sp',-5),c.b.KS,ANGLE_LABELS,'(c) SP, individual SIR=-5 dB');axes[2].set(xlabel='Concurrent frames K',ylabel='Minimum active angle bin (°)')
    save(fig,'fig13_main_collision_boundary')
    for name,methods,sir in [('A13_1_strong_baselines',METHODS[1:],-5),('A13_2_equal_power',METHODS,0)]:
        fig,axes=plt.subplots(1,len(methods),figsize=(3.3*len(methods),3.4))
        for ax,method in zip(axes,methods):
            heat(ax,matrix(method,sir),c.b.KS,ANGLE_LABELS,LABELS[METHODS.index(method)]);ax.set_xlabel('Concurrent frames K')
        axes[0].set_ylabel('Minimum active angle bin (°)');save(fig,name)



def main():
    FIG.mkdir(parents=True,exist_ok=True);TABLE.mkdir(exist_ok=True)
    m=json.loads((OUT/'manifest_main.json').read_text());rows=[json.loads((OUT/'jobs'/(c.key(s)+'.json')).read_text()) for s in m['specs']]
    assert len(rows)==4400
    pilotm=json.loads((OUT/'manifest_pilot.json').read_text());pilot=[json.loads((OUT/'jobs'/(c.key(s)+'.json')).read_text()) for s in pilotm['specs']]
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
    for r,s in zip(rows,m['specs']):assert r['spec']==s
    def select(family,snr=None,sir=None,low=None):
        return [r for r in rows if r['spec']['family']==family and (snr is None or r['spec']['snr_db']==snr) and (sir is None or r['spec']['individual_sir_db']==sir) and (low is None or r['spec']['angle_low']==low)]
    fig,axes=plt.subplots(1,3,figsize=(12.4,3.35))
    curve(axes[0],m['snrs'],[select('snr',snr=s,sir=0) for s in m['snrs']]);axes[0].set(xlabel='Target SNR (dB)',title='(a) Equal power, angle 20–40°');axes[0].set_xticks(m['snrs'])
    for ax,sir,title in zip(axes[1:],[-5,0],['(b) Strong interferer','(c) Equal power']):
        curve(ax,range(6),[select('angle',sir=sir,low=lo) for lo in LOWS],ANGLE_LABELS);ax.set(xlabel='Channel-angle bin (°)',title=f'{title}, SNR {m["s_good"]} dB')
    axes[0].legend(fontsize=8);save(fig,'fig12_main_robustness')
    for family,name,xvals,xlabels in [('snr','A12_1_snr_sir',m['snrs'],m['snrs']),('angle','A12_2_angle_sir',LOWS,ANGLE_LABELS)]:
        fig,axes=plt.subplots(1,4,figsize=(13.5,3.4))
        for ax,method,label in zip(axes,METHODS,LABELS):
            matrix=[]
            for sir in m['sirs']:
                line=[]
                for xx in xvals:
                    group=select(family,sir=sir,**({'snr':xx} if family=='snr' else {'low':xx}))
                    assert len(group)==100
                    val=np.mean([r['metrics'][method]['delivered'] for r in group]);line.append(val)
                    COUNTS.append(dict(family=family,x=xx,sir=sir,method=method,trials=len(group),pdr=val))
                matrix.append(line)
            heat(ax,matrix,xlabels,m['sirs'],label);ax.set_xlabel('Target SNR (dB)' if family=='snr' else 'Channel-angle bin (°)')
        axes[0].set_ylabel('Individual-interferer SIR (dB)');save(fig,name)
    csvout(TABLE/'fig12_cells.csv',COUNTS)
    tab=[]
    strata=[('SNR <= calibrated s0; all SIR', [r for r in select('snr') if r['spec']['snr_db']<=m['s0']]),
            ('Angle <10 degrees; all SIR',[r for r in select('angle') if r['spec']['angle_low']<10]),
            ('Angle20–40; SIR=-5; s_good',select('angle',sir=-5,low=20)),
            ('All formal grid conditions',rows)]
    for label,group in strata:
        n=len(group);sp=sum(r['metrics']['sp']['delivered'] for r in group);mr=sum(r['metrics']['mrc']['delivered'] for r in group)
        rescue=sum(r['metrics']['sp']['delivered'] and not r['metrics']['mrc']['delivered'] for r in group)
        harm=sum(not r['metrics']['sp']['delivered'] and r['metrics']['mrc']['delivered'] for r in group)
        tab.append(dict(condition=label,n=n,sp_pdr=sp/n,mrc_pdr=mr/n,rescue_rate=rescue/n,harm_rate=harm/n,fallback_rate=sum(r['lambda_sp']==0 for r in group)/n))
    csvout(TABLE/'T12_rescue_harm_fallback.csv',tab)
    flat=[]
    for r in rows:
        s=r['spec'];flat.append(dict(job=c.key(s),family=s['family'],repeat=s['repeat'],snr=s['snr_db'],sir=s['individual_sir_db'],angle_low=s['angle_low'],source_target=s['sources'][0],source_interferer=s['sources'][1],physical_angle=r['physical_angle'],lambda_sp=r['lambda_sp'],guard=r['guard'],**{method+'_pdr':int(r['metrics'][method]['delivered']) for method in METHODS},**{method+'_ser':r['metrics'][method]['ser'] for method in METHODS}))
    csvout(TABLE/'per_target.csv',flat)

    render_boundary()

    # Reference statistics retain every oracle-labelled payload chirp in each selected stratum.
    snrlevels=[m['s0']-3,m['s0'],m['s_good']]
    noisegroups=[(f'{s} dB',[r for r in pilot if r['spec']['snr_db']==s]) for s in snrlevels]
    sirgroups=[(f'{s} dB',select('angle',sir=s)) for s in m['sirs']]
    refstats=[];fig,axes=plt.subplots(1,2,figsize=(9,3.4))
    for ax,groups,title in zip(axes,[noisegroups,sirgroups],['(a) Isolated packet, varying SNR','(b) Mixed preamble, varying SIR']):
        for label,group in groups:
            values=np.sort([q['delta_deg'] for r in group for q in r['reference']]);ax.step(values,np.arange(1,len(values)+1)/len(values),where='post',label=label)
            refstats.append(dict(family='isolated' if groups is noisegroups else 'collision',level=label,packets=len(group),source_packets=len({r['spec']['sources'][0] for r in group}),chirps=len(values),median=np.median(values),p90=np.percentile(values,90),p95=np.percentile(values,95)))
        ax.set(xlabel='Projective deviation from preamble reference (°)',ylabel='Empirical CDF',xlim=(0,90),ylim=(0,1),title=title);ax.legend(fontsize=8);ax.grid(alpha=.2)
    save(fig,'fig10_11_main_reference_cdf');csvout(TABLE/'reference_summary.csv',refstats)
    fig,axes=plt.subplots(1,2,figsize=(9,3.4))
    for ax,groups,title in zip(axes,[noisegroups,sirgroups],['(a) SNR strata','(b) SIR strata']):
        for label,group in groups:
            arr=np.array([[q['delta_deg'] for q in r['reference']] for r in group]);x=np.linspace(0,1,arr.shape[1]);line=ax.plot(x,np.median(arr,axis=0),label=label)[0]
            ax.fill_between(x,np.percentile(arr,10,axis=0),np.percentile(arr,90,axis=0),color=line.get_color(),alpha=.12)
        ax.set(xlabel='Normalized payload position',ylabel='Projective deviation (°)',title=title,ylim=(0,90));ax.legend(fontsize=8);ax.grid(alpha=.2)
    save(fig,'A10_11_reference_trajectories')
    fig,ax=plt.subplots(figsize=(5,3.5));ss=m['pilot'];ax.plot([r['snr'] for r in ss],[r['pdr'] for r in ss],'o-');ax.axhline(.9,color='.6',ls=':');ax.axvline(m['s0'],color='#d88418',ls='--',label=f's0={m["s0"]} dB');ax.axvline(m['s_good'],color='#16856a',ls='--',label=f's_good={m["s_good"]} dB');ax.set(xlabel='Target SNR (dB)',ylabel='Isolated MRC PDR',ylim=(0,1.05),title='All 22 retained source packets; 88 trials / SNR');ax.legend();save(fig,'diagnostic_single_packet_calibration')

    # Dense objective audit targets the proposal, before protection may force lambda=0.
    audits=[];examples=[]
    def objective(e,grid):
        n=e['noise_sigma2_sp'];S=e['power_sp'];L=e['L_u'];p=S*L;q=S*(1-L)
        threshold=n*np.maximum(0,np.log(1023/.05)-np.log1p(grid))
        noise=(p-grid*q+n*(1-grid)-threshold)/np.sqrt(n*n+2*n*p+grid*grid*(n*n+2*n*q))
        pairs=[(r['A_under']+grid*r['B_under'])/np.sqrt(np.maximum(r['C0']+grid*grid*r['C2'],1e-30)) for r in e['lambda_pair_rows_sp']]
        pair=np.min(pairs,axis=0) if pairs else np.full(grid.shape,np.inf)
        return np.minimum(pair,noise),pair,noise
    for r in rows:
        e=r['estimate'];cap=e['lambda_cap_sp'];points=e['lambda_candidate_points_sp'];candidate=np.array([p['lambda'] for p in points])
        if cap<=0 or e.get('lambda_guard_proposed_objective_sp') is None:
            audits.append(dict(job=c.key(r['spec']),cap=cap,candidates=len(points),relative_objective_gap=0.,trivial=True,guard=r['guard']));continue
        grid=np.unique(np.r_[0,np.geomspace(max(1e-12,cap*1e-9),cap,8192),candidate]);dense=objective(e,grid)[0]
        candidate_values=objective(e,candidate)[0]
        assert np.allclose(candidate_values,[p['objective'] for p in points],rtol=1e-9,atol=1e-9)
        best=np.max(candidate_values);assert abs(best-e['lambda_guard_proposed_objective_sp'])<1e-8
        gap=(np.max(dense)-best)/max(1,abs(np.max(dense)))
        audits.append(dict(job=c.key(r['spec']),cap=cap,candidates=len(points),relative_objective_gap=float(gap),trivial=False,guard=r['guard']))
        if r['guard']=='guarded_pair_weight' and r['lambda_sp']>0:examples.append(r)
    csvout(TABLE/'finite_candidate_audit.csv',audits)
    assert examples,'No enabled guard example; do not fabricate a candidate illustration'
    examples.sort(key=lambda r:(len(r['estimate']['lambda_candidate_points_sp']),c.key(r['spec'])))
    example=examples[len(examples)//2];e=example['estimate'];grid=np.linspace(0,e['lambda_cap_sp'],1500);value,pair,noise=objective(e,grid)
    fig,ax=plt.subplots(figsize=(6,3.5));ax.plot(grid,pair,label='Pair margin');ax.plot(grid,noise,label='Noise margin');ax.plot(grid,value,color='black',ls='--',label='Lower envelope');pts=e['lambda_candidate_points_sp'];ax.scatter([p['lambda'] for p in pts],[p['objective'] for p in pts],s=15,color='#d88418',label='Finite candidates');ax.axvline(e['lambda_sp'],color='#16856a',ls=':',label='Online selected λ');ax.set(xlabel='λ',ylabel='Standardized surrogate margin',title='Finite candidate search: measured mixed-preamble parameters');ax.legend(fontsize=8);save(fig,'A7_finite_candidate_search')
    c.write(OUT/'candidate_summary.json',dict(rows=len(audits),enabled_examples=len(examples),max_relative_gap=max(r['relative_objective_gap'] for r in audits),candidate_count_quantiles=np.percentile([r['candidates'] for r in audits],[0,50,90,100]).tolist(),example_job=c.key(example['spec']),example_rule='Median candidate count among nonzero enabled guard configurations; tie by job hash, no payload outcome selection',scope='Proposal objective coverage, not PDR optimality; post-proposal guards may deliberately select zero.'))

    # Tables from complete blind and serial timing runs.
    bm=json.loads((OUT/'manifest_blind.json').read_text());blind=[json.loads((OUT/'blind_jobs'/(c.key(s)+'.json')).read_text()) for s in bm['specs']]
    controlled={c.key(s):json.loads((OUT/'blind_controlled_jobs'/(c.key(s)+'.json')).read_text()) for s in bm['specs']}
    bcm=json.loads((OUT/'manifest_blind_calibration.json').read_text());blind_cal=[json.loads((OUT/'blind_jobs'/(c.key(s)+'.json')).read_text()) for s in bcm['specs']]
    bt=[]
    for k in (2,4,6):
        for snr in (m['s0'],m['s_good']):
            for span in (0.,.1,.5,1.,2.):
                rr=[r for r in blind if r['spec']['k']==k and r['spec']['snr_db']==snr and r['spec']['span_symbols']==span];targets=[t for r in rr for t in r['targets']];n=len(targets)
                known=[t for r in rr for t in controlled[c.key(r['spec'])]['targets']]
                bt.append(dict(k=k,snr=snr,start_span_symbols=span,scenes=len(rr),targets=n,mean_candidates=np.mean([r['candidate_count'] for r in rr]),matched_track_fraction=np.mean([t['track_matched'] for t in targets]),sp_core_pdr=np.mean([t['delivered']['sp_core'] for t in targets]),sp_refined_pdr=np.mean([t['delivered']['sp_sync_refine'] for t in targets]),mrc_shared_frontend_pdr=np.mean([t['delivered']['mrc'] for t in targets]),known_acquisition_sp_pdr=np.mean([t['sp']['delivered'] for t in known]),known_acquisition_mrc_pdr=np.mean([t['mrc']['delivered'] for t in known])))
    csvout(TABLE/'blind_frontend_diagnostic.csv',bt)
    bct=[]
    for snr in (m['s0'],m['s_good']):
        rr=[r for r in blind_cal if r['spec']['snr_db']==snr];targets=[t for r in rr for t in r['targets']]
        bct.append(dict(snr=snr,targets=len(targets),matched_track_fraction=np.mean([t['track_matched'] for t in targets]),sp_core_pdr=np.mean([t['delivered']['sp_core'] for t in targets]),sp_refined_pdr=np.mean([t['delivered']['sp_sync_refine'] for t in targets]),mrc_shared_frontend_pdr=np.mean([t['delivered']['mrc'] for t in targets])))
    csvout(TABLE/'blind_isolated_control.csv',bct)
    timing=json.loads((OUT/'timing.json').read_text());tt=[]
    for k in c.b.KS:
        for method in METHODS:
            rr=[r for r in timing['rows'] if r['k']==k and r['method']==method and not r['warmup']]
            tt.append(dict(k=k,method=method,bursts=len(rr),median_ms=np.median([r['milliseconds_per_burst'] for r in rr]),p90_ms=np.percentile([r['milliseconds_per_burst'] for r in rr],90),median_configuration_ms=np.median([r['configuration_ms'] for r in rr])))
    csvout(TABLE/'T13_serial_latency.csv',tt)
    fig,axes=plt.subplots(1,2,figsize=(12,3.1))
    for ax in axes:ax.axis('off')
    cols=['Condition','N','SP','MRC','Rescue','Harm','λ=0'];cells=[[r['condition'],r['n'],*[f'{100*r[k]:.2f}%' for k in ('sp_pdr','mrc_pdr','rescue_rate','harm_rate','fallback_rate')]] for r in tab]
    table=axes[0].table(cellText=cells,colLabels=cols,loc='center',colWidths=[.4,.07,.09,.09,.09,.09,.09]);table.auto_set_font_size(False);table.set_fontsize(7);table.scale(1,1.9);axes[0].set_title('T12: observed packet rescue / harm / fallback')
    cells=[[k,*[f'{next(r["median_ms"] for r in tt if r["k"]==k and r["method"]==method):.1f}' for method in METHODS]] for k in c.b.KS]
    table=axes[1].table(cellText=cells,colLabels=['K',*LABELS],loc='center');table.auto_set_font_size(False);table.set_fontsize(8);table.scale(1,1.6);axes[1].set_title('T13: median serial decoder time (ms / burst)')
    save(fig,'tables_T12_T13')
    with PdfPages(OUT/'all_new_figures.pdf') as pdf:
        for name,fig in FIGS:pdf.savefig(fig,bbox_inches='tight');plt.close(fig)
    thumbs=[]
    for name,_ in FIGS:
        im=Image.open(FIG/f'{name}.png').convert('RGB');im.thumbnail((900,360));thumb=Image.new('RGB',(920,395),'white');thumb.paste(im,((920-im.width)//2,25));ImageDraw.Draw(thumb).text((10,5),name,fill='black');thumbs.append(thumb)
    overview=Image.new('RGB',(1840,395*((len(thumbs)+1)//2)),'#eeeeee')
    for i,im in enumerate(thumbs):overview.paste(im,((i%2)*920,(i//2)*395))
    overview.save(OUT/'overview.png')
    c.write(OUT/'results_summary.json',dict(main_trials=len(rows),pilot_trials=len(pilot),blind_scenes=len(blind),blind_isolated_controls=bct,s0=m['s0'],s_good=m['s_good'],T12=tab,reference=refstats,figures=[name for name,_ in FIGS],finite_candidate_audit=json.loads((OUT/'candidate_summary.json').read_text())))
    print(json.dumps(dict(figures=len(FIGS),main_trials=len(rows),T12=tab),indent=2),flush=True)

if __name__=='__main__':main()
