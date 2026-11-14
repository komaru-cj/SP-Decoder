#!/usr/bin/env python3
"""Paper-width plots with a single common setup for both main comparisons."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/unified_study_mpl')
from pathlib import Path
import sys,json,csv,hashlib,shutil,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image,ImageDraw
from scipy.stats import beta
from real_collision_experiment.paper_experiments import unified_study_20261114 as u
c=u.c;b=u.b;OUT=u.OUT;METHODS=c.METHODS;LABELS=['SP-Decoder','MRC','PCube','MaLoRaGW'];COLORS=['#137b61','#d08a26','#427db2','#a16cad'];FIGS=[];CELLS=[]

def csvout(name,rows):
    folder=OUT/'data';folder.mkdir(exist_ok=True)
    with (folder/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def save(fig,name):
    fig.tight_layout(rect=getattr(fig,'_paper_rect',(0,0,1,1)))
    for ext in ['png','pdf','svg']:fig.savefig(OUT/'figures'/f'{name}.{ext}',dpi=230,bbox_inches='tight')
    FIGS.append((name,fig))

def wilson(success,n):
    p=success/n;z=1.96;d=1+z*z/n;centre=(p+z*z/(2*n))/d;h=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return 100*max(0,centre-h),100*min(1,centre+h)

def stats(group,method):
    n=len(group);success=sum(r['metrics'][method]['delivered'] for r in group);lo,hi=wilson(success,n)
    return 100*success/n,lo,hi,100*float(np.mean([r['metrics'][method]['ser'] for r in group]))

def bar_comparison(ax,levels,groups,xlabel,title,ser=False):
    width=.19;x=np.arange(len(levels))
    for i,method in enumerate(METHODS):
        values=np.array([stats(g,method) for g in groups]);y,lo,hi,se=values.T
        if ser:y=se
        ax.bar(x+(i-1.5)*width,y,width,color=COLORS[i],edgecolor='white',lw=.4,label=LABELS[i],zorder=3)
        if not ser:ax.errorbar(x+(i-1.5)*width,y,yerr=np.maximum([y-lo,hi-y],0),fmt='none',ecolor='.25',capsize=1.3,lw=.5,zorder=4)
    ax.set_xticks(x,levels);ax.set(xlabel=xlabel,ylabel='Mean target SER (%)' if ser else 'Target PDR (%)',title=title,ylim=(0,106));ax.set_yticks([0,25,50,75,100]);ax.grid(alpha=.15,axis='y',zorder=0)

def curves(ax,levels,groups,xlabel,title,ser=False):
    x=np.asarray(levels,dtype=float) if all(isinstance(v,(int,float,np.number)) for v in levels) else np.arange(len(levels))
    for i,method in enumerate(METHODS):
        values=np.array([stats(g,method) for g in groups]);y,lo,hi,se=values.T
        if ser:ax.plot(x,se,marker=['o','s','^','D'][i],ms=3,color=COLORS[i],lw=1.8 if i==0 else 1.1,label=LABELS[i])
        else:ax.errorbar(x,y,yerr=np.maximum([y-lo,hi-y],0),marker=['o','s','^','D'][i],ms=3,color=COLORS[i],lw=1.8 if i==0 else 1.1,capsize=1,label=LABELS[i])
    ax.set_xticks(x,levels);ax.set(xlabel=xlabel,ylabel='Mean target SER (%)' if ser else 'Target PDR (%)',title=title,ylim=(0,106));ax.set_yticks([0,25,50,75,100]);ax.grid(alpha=.15)

def shared_legend(fig,ax):fig.legend(*ax.get_legend_handles_labels(),ncol=4,loc='upper center',bbox_to_anchor=(.5,1.10),frameon=False,fontsize=8)

def main():
    (OUT/'figures').mkdir(exist_ok=True,parents=True);u.initialize();protocol=json.loads((OUT/'protocol.json').read_text());data={}
    for stage in ['main','snr','angle','density','safety']:
        manifest=json.loads((OUT/f'manifest_{stage}.json').read_text());rr=[]
        for s in manifest['specs']:
            r=json.loads((OUT/'jobs'/(c.key(s)+'.json')).read_text());assert r['spec']==s;rr.append(r)
        data[stage]=rr
    assert [len(data[s]) for s in ['main','snr','angle']]==[1500,900,700]
    assert len(data['density'])==600
    assert len(data['safety'])==1200
    cm=json.loads((OUT/'manifest_calibration.json').read_text());calibration=[json.loads((OUT/'jobs'/(c.key(s)+'.json')).read_text()) for s in cm['specs']]
    assert len(calibration)==88
    def group(k=2,sir=-10):return [r for r in data['main'] if r['spec']['k']==k and r['spec']['individual_sir_db']==sir]
    sirgroups=[group(sir=sir) for sir in u.SIRS];kgroups=[group(k=k,sir=-5) for k in u.KS]
    widths=[2.,1.,.5,.25,.1,.05];dgroups=[[r for r in data['density'] if r['spec']['width_ratio']==width] for width in widths]
    lows=[0,2,5,10,20,40,60];agroups=[[r for r in data['angle'] if r['spec']['angle_low']==lo] for lo in lows];alabels=['0–2','2–5','5–10','10–20','20–40','40–60','60–90']
    assert all(len(g)==100 for g in sirgroups+kgroups)
    plt.rcParams.update({'font.size':8,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.right':False,'axes.spines.top':False})
    fig,axes=plt.subplots(1,2,figsize=(7.2,3.0))
    bar_comparison(axes[0],[int(s) for s in u.SIRS],sirgroups,'Per-interferer SIR (dB)','(a) Interference tolerance\nChannel angle 10–60°')
    bar_comparison(axes[1],alabels,agroups,'Measured channel-angle bin (°)','(b) Spatial operating range\nInterferer SIR −10 dB')
    fig.suptitle('Common setup: SNR 0 dB; K=2; nominal start separation 0.2 symbol',fontsize=8,y=.99)
    fig.legend(*axes[0].get_legend_handles_labels(),ncol=4,loc='upper center',bbox_to_anchor=(.5,.94),frameon=False,fontsize=8)
    fig._paper_rect=(0,0,1,.84);save(fig,'MAIN_same_setup_performance')

    # Requested line+bar view uses the same strong-interference experiment, not a fallback-only slice.
    fig,ax=plt.subplots(figsize=(7.2,2.8));x=np.arange(len(u.SIRS));rescue=[];harm=[];paired=[]
    for level,g in zip(u.SIRS,sirgroups):
        n=len(g);r=sum(q['metrics']['sp']['delivered'] and not q['metrics']['mrc']['delivered'] for q in g);h=sum(not q['metrics']['sp']['delivered'] and q['metrics']['mrc']['delivered'] for q in g)
        sp=stats(g,'sp')[0];mr=stats(g,'mrc')[0];assert abs(sp-mr-100*(r-h)/n)<1e-9
        rescue.append(100*r/n);harm.append(100*h/n);paired.append(dict(sir=level,n=n,sp_pdr=sp,mrc_pdr=mr,rescue_rate=100*r/n,harm_rate=100*h/n))
    ax.bar(x,rescue,.55,color='#9fcdbd',label='Rescued by SP',zorder=2)
    if any(harm):ax.bar(x,-np.array(harm),.55,color='#c44c63',label='Lost by SP',zorder=2)
    for method,color,marker,ls,label in [('sp',COLORS[0],'o','-','SP PDR'),('mrc','#404040','s','--','MRC PDR')]:
        y=[stats(g,method)[0] for g in sirgroups];ax.plot(x,y,marker=marker,ls=ls,color=color,label=label,lw=1.7,zorder=4)
    ax.set_xticks(x,[int(s) for s in u.SIRS]);ax.set(xlabel='Per-interferer SIR (dB)',ylabel='Fraction of all target packets (%)',title='Paired recovery: same SNR 0 dB, K=2, source bank and timing',ylim=(-max(5,max(harm)+3),106));ax.axhline(0,color='.6',lw=.7);ax.grid(alpha=.15,axis='y');fig.legend(*ax.get_legend_handles_labels(),ncol=4,loc='upper center',bbox_to_anchor=(.5,1.09),frameon=False,fontsize=8);save(fig,'VALUE_pdr_and_rescue');csvout('paired_rescue.csv',paired)

    # Reviewer boundary checks change only the named variable; no arbitrary -8dB slice.
    snrs=sorted({r['spec']['snr_db'] for r in data['snr']}|{0.});sgroups=[[r for r in data['snr'] if r['spec']['snr_db']==snr] if snr!=0 else group(sir=-10) for snr in snrs]
    lows=[0,2,5,10,20,40,60];agroups=[[r for r in data['angle'] if r['spec']['angle_low']==lo] for lo in lows];alabels=['0–2','2–5','5–10','10–20','20–40','40–60','60–90']
    fig,axes=plt.subplots(1,2,figsize=(7.2,2.8));curves(axes[0],[int(s) for s in snrs],sgroups,'Target SNR (dB)','(a) Noise boundary: K=2, SIR −10 dB');curves(axes[1],alabels,agroups,'Measured channel-angle bin (°)','(b) Spatial boundary: K=2, SNR 0 dB');shared_legend(fig,axes[0]);save(fig,'APP_review_boundary_PDR')
    fig,axes=plt.subplots(1,2,figsize=(7.2,2.8));curves(axes[0],[int(s) for s in snrs],sgroups,'Target SNR (dB)','(a) Noise boundary: K=2, SIR −10 dB',True);curves(axes[1],alabels,agroups,'Measured channel-angle bin (°)','(b) Spatial boundary: K=2, SNR 0 dB',True);shared_legend(fig,axes[0]);save(fig,'APP_review_boundary_SER')
    fig,ax=plt.subplots(figsize=(4.0,2.8));curves(ax,u.KS,[group(k=k,sir=-10) for k in u.KS],'Concurrent packets K','Stronger-interferer check: SNR 0, SIR −10 dB');ax.legend(fontsize=7);save(fig,'APP_K_at_stronger_interference')
    fig,ax=plt.subplots(figsize=(4.0,2.8));curves(ax,u.KS,kgroups,'Concurrent packets K','Collision-order boundary: SNR 0, SIR −5 dB');ax.legend(fontsize=7);save(fig,'APP_K_at_moderate_interference')
    fig,axes=plt.subplots(1,2,figsize=(7.2,2.8));bar_comparison(axes[0],['2','1','0.5','0.25','0.1','0.05'],dgroups,'Start span W / payload duration (denser →)','(a) Temporal overlap: fixed K=6');bar_comparison(axes[1],u.KS,kgroups,'Concurrent packets K','(b) Add interferers: fixed per-packet power');shared_legend(fig,axes[0]);fig.suptitle('Load-limit checks: SNR 0 dB; SIR/interferer −5 dB; link angles 10–60°',fontsize=8,y=1.22);save(fig,'APP_density_and_order_limits')

    # Equal-power controls test fallback where MRC has nonzero PDR. Keep actual harms.
    safety_snr=[[r for r in data['safety'] if r['spec']['family']=='safety_snr' and r['spec']['snr_db']==snr] if snr!=0 else group(sir=0) for snr in snrs]
    safety_angle=[[r for r in data['safety'] if r['spec']['family']=='safety_angle' and r['spec']['angle_low']==lo] for lo in lows[:3]]
    assert all(len(g)==100 for g in safety_snr+safety_angle)
    fig,axes=plt.subplots(2,2,figsize=(7.2,5.4))
    curves(axes[0,0],[int(s) for s in snrs],safety_snr,'Target SNR (dB)','(a) Noise safety: channel angles 10–60°')
    bar_comparison(axes[0,1],alabels[:3],safety_angle,'Measured channel-angle bin (°)','(b) Small-angle safety: SNR 0 dB')
    curves(axes[1,0],[int(s) for s in snrs],safety_snr,'Target SNR (dB)','(c) Same noise cases: symbol errors',True)
    bar_comparison(axes[1,1],alabels[:3],safety_angle,'Measured channel-angle bin (°)','(d) Same small-angle cases: symbol errors',True)
    fig.suptitle('Guard checks: K=2; equal received power (SIR 0 dB); nominal start gap 0.2 symbol',fontsize=8,y=.99)
    fig.legend(*axes[0,0].get_legend_handles_labels(),ncol=4,loc='upper center',bbox_to_anchor=(.5,.955),frameon=False,fontsize=8)
    fig._paper_rect=(0,0,1,.90);save(fig,'APP_guard_safety_PDR_SER')

    for family,levels,groups in [('nearfar',list(u.SIRS),sirgroups),('density',widths,dgroups),('K_main',list(u.KS),kgroups),('snr',snrs,sgroups),('angle',lows,agroups),('K_stronger',list(u.KS),[group(k=k,sir=-10) for k in u.KS]),('safety_snr',snrs,safety_snr),('safety_angle',lows[:3],safety_angle)]:
        for level,g in zip(levels,groups):
            for method in METHODS:
                p,lo,hi,ser=stats(g,method);CELLS.append(dict(family=family,level=level,method=method,n=len(g),pdr=p,pdr_low=lo,pdr_high=hi,ser=ser))
    csvout('all_cells.csv',CELLS)
    flat=[]
    for stage,rr in data.items():
        for r in rr:
            s=r['spec'];angles=[b.n.a.angle_deg(b.CHANNELS[s['sources'][0]],b.CHANNELS[v]) for v in s['sources'][1:]]
            flat.append(dict(stage=stage,job=c.key(s),repeat=s['repeat'],k=s['k'],snr=s['snr_db'],individual_sir=s['individual_sir_db'],aggregate_sir=s['individual_sir_db']-10*np.log10(s['k']-1),minimum_active_angle=min(angles),maximum_active_angle=max(angles),target_source=s['sources'][0],target_position=b.POSITIONS[s['sources'][0]],lambda_sp=r['lambda_sp'],guard=r['guard'],**{method+'_delivered':int(r['metrics'][method]['delivered']) for method in METHODS},**{method+'_ser':r['metrics'][method]['ser'] for method in METHODS}))
    csvout('all_targets.csv',flat)
    density_stats=[]
    for width,gg in zip(widths,dgroups):
        conc=[]
        for r in gg:
            s=r['spec'];starts=np.rint((3+np.array(s['relative_offsets'])*s['width_ratio']*b.n.CFG.payload_symbol_count)*b.n.CFG.samples_per_symbol)
            conc.append(b.overlap_summary(starts,b.n.CFG,0)['mean_concurrency'])
        density_stats.append(dict(width_ratio=width,mean_concurrency=float(np.mean(conc)),trials=len(gg)))
    csvout('density_actual_concurrency.csv',density_stats)
    csvout('isolated_SNR0_calibration.csv',[dict(source=r['spec']['sources'][0],repeat=r['spec']['repeat'],delivered=r['metrics']['mrc']['delivered'],ser=r['metrics']['mrc']['ser']) for r in calibration])
    # Validate physical controls and reproducibility rather than only file existence.
    masters=protocol['masters']
    assert all(r['spec']['snr_db']==0 for r in data['main'])
    for r in data['main']+data['snr']:
        s=r['spec'];master=masters[s['repeat']]
        assert s['sources']==master['sources'][:s['k']] and s['phases']==master['phases'][:s['k']]
        assert np.allclose(np.array(s['relative_offsets'])*2,master['offsets'][:s['k']],rtol=0,atol=1e-14)
        assert all(10<=b.n.a.angle_deg(b.CHANNELS[s['sources'][0]],b.CHANNELS[v])<60 for v in s['sources'][1:])
    for rr in data.values():
        for r in rr:
            assert r['noise_budget']['min_residual_eigenvalue']>=-1e-8*r['noise_budget']['variance']
            if r['lambda_sp']==0 and 'mrc_decision_channel_sp' in r['estimate']:assert r['metrics']['sp']==r['metrics']['mrc']
    for r in data['density']:
        s=r['spec'];master=masters[s['repeat']];off=np.array(master['offsets']);expected=(off-off.min())/np.ptp(off)
        assert s['sources']==master['sources'] and s['phases']==master['phases']
        assert np.allclose(s['relative_offsets'],expected) and s['snr_db']==0 and s['individual_sir_db']==-5
    for name,h in protocol['algorithm_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h
    c.write(OUT/'validation.json',dict(complete=True,power_and_order_trials=1500,snr_trials=900,angle_trials=700,density_trials=600,safety_trials=1200,total_collision_trials=4900,isolated_calibration_trials=88,common_primary_snr_db=0,common_primary_k=2,common_primary_nominal_start_gap_symbols=.2,nearfar_preserves_source_phase_and_starts_across_SIR=True,geometry_sweep_fixed_SNR_and_SIR=True,same_load_study_master_sources_phases=True,nested_order_starts_preserved=True,density_changes_only_normalized_start_span=True,noise_psd_valid=True,source_iq_sha256=protocol['raw_iq_sha256'],no_algorithm_change=True))
    with PdfPages(OUT/'all_unified_figures.pdf') as pdf:
        for name,fig in FIGS:pdf.savefig(fig,bbox_inches='tight');plt.close(fig)
    subprocess.run(['pdfunite',str(OUT/'figures/MAIN_same_setup_performance.pdf'),str(OUT/'figures/VALUE_pdr_and_rescue.pdf'),str(OUT/'main_options.pdf')],check=True)
    shutil.copy2(OUT/'figures/MAIN_same_setup_performance.pdf',OUT/'PRIMARY_replacement.pdf')
    thumbs=[]
    for name,_ in FIGS:
        im=Image.open(OUT/'figures'/f'{name}.png').convert('RGB');im.thumbnail((1000,420));canvas=Image.new('RGB',(1020,450),'white');canvas.paste(im,((1020-im.width)//2,25));ImageDraw.Draw(canvas).text((10,5),name,fill='black');thumbs.append(canvas)
    ov=Image.new('RGB',(2040,450*((len(thumbs)+1)//2)),'#eeeeee')
    for i,im in enumerate(thumbs):ov.paste(im,((i%2)*1020,(i//2)*450))
    ov.save(OUT/'overview.png')
    for src in ('unified_study_20261114.py','render_unified_study_20261114.py'):
        dst=OUT/'code_snapshot'/src;dst.parent.mkdir(exist_ok=True);shutil.copy2(Path(__file__).with_name(src),dst)
    c.write(OUT/'summary.json',dict(main_setup=dict(snr=0,k=2,start_separation_symbols=.2,nearfar_angle_interval=[10,60],spatial_sweep_sir=-10),isolated_calibration_successes=sum(r['metrics']['mrc']['delivered'] for r in calibration),figures=[name for name,_ in FIGS],cells=CELLS,paired_recovery=paired,density_concurrency=density_stats))
    print(json.dumps(dict(complete=True,figures=len(FIGS),isolated_calibration_successes=sum(r['metrics']['mrc']['delivered'] for r in calibration)),indent=2),flush=True)

if __name__=='__main__':main()
