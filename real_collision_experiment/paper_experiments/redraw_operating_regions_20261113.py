#!/usr/bin/env python3
"""Compact operating-region figures, paired rescue bars, and audited timing."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/redesign_20261113_mpl')
from pathlib import Path
import sys,json,csv,hashlib,shutil,zipfile,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from PIL import Image,ImageDraw
from real_collision_experiment.paper_experiments import audit_redesign_20261113 as a
c=a.c;OUT=a.OUT;OLD=ROOT/'real_usrp_outputs/compact_revision_20261106';BOUND=c.b.OUT
METHODS=c.METHODS;LABELS=['SP-Decoder','MRC','PCube','MaLoRaGW'];COLORS=['#137b61','#cc7a12','#397fc1','#9a5ca6'];MARKERS=['o','s','^','D'];FIGS=[];DATA=[]

def csvout(name,rows):
    p=OUT/'data'/name;p.parent.mkdir(exist_ok=True,parents=True)
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def save(fig,name):
    fig.tight_layout()
    for ext in ('pdf','svg','png'):fig.savefig(OUT/'figures'/f'{name}.{ext}',dpi=230,bbox_inches='tight')
    FIGS.append((name,fig))

def wilson(success,n):
    p=success/n;z=1.96;den=1+z*z/n;center=(p+z*z/(2*n))/den;h=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return 100*max(0,center-h),100*min(1,center+h)

def metrics(group,method):
    n=len(group);s=sum(r['metrics'][method]['delivered'] for r in group);lo,hi=wilson(s,n)
    return 100*s/n,lo,hi,n

def dotinterval(ax,x,y,lo,hi,method,label=False):
    i=METHODS.index(method)
    ax.errorbar(x,y,yerr=[np.array(y)-lo,np.array(hi)-y],fmt='none',color=COLORS[i],alpha=.38,capsize=2,lw=.8)
    ax.plot(x,y,marker=MARKERS[i],color=COLORS[i],lw=2.2 if method=='sp' else 1.2,ms=5 if method=='sp' else 4,label=LABELS[i] if label else None,zorder=5 if method=='sp' else 3)

def rows_from(root,manifest_name,field='specs'):
    m=json.loads((root/manifest_name).read_text());return m,[json.loads((root/'jobs'/(c.key(s)+'.json')).read_text()) for s in m[field]]

def main():
    (OUT/'figures').mkdir(exist_ok=True,parents=True)
    plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
    em,extreme=rows_from(OUT,'manifest_extreme.json');nm,nested=rows_from(OUT,'manifest_nested.json');mm,moderate=rows_from(OUT,'manifest_nested_moderate.json');om,old=rows_from(OLD,'manifest_main.json');pm,pilot=rows_from(OLD,'manifest_pilot.json')
    assert len(extreme)==800 and len(old)==4400 and len(nested)==128 and len(moderate)==128
    bc=list(csv.DictReader((BOUND/'cell_summary.csv').open()))
    def egroup(snr,sir):return [r for r in extreme if r['spec']['snr_db']==snr and r['spec']['individual_sir_db']==sir]
    def ogroup(family,**kw):return [r for r in old if r['spec']['family']==family and all(r['spec'][k]==v for k,v in kw.items())]
    def bgroup(method,k,lo=40,sir=-5):return next(r for r in bc if r['family']=='geometry' and r['method']==method and int(r['k'])==k and float(r['angle_low'])==lo and float(r['individual_sir_db'])==sir)

    # P3: two matched stress sweeps, without near-collinear or noise-floor pooling.
    fig,axes=plt.subplots(1,3,figsize=(7.2,2.7));sirs=[-20,-10,0,10]
    for method in METHODS:
        vals=[metrics(egroup(0,sir),method) for sir in sirs]
        y,lo,hi,_=np.array(vals).T
        dotinterval(axes[0],range(4),y,lo,hi,method,True)
        for ax,group in [(axes[1],moderate),(axes[2],nested)]:
            vals=[metrics([r for r in group if r['spec']['k']==k],method) for k in (2,4,6,8)]
            y,lo,hi,_=np.array(vals).T;dotinterval(ax,[2,4,6,8],y,lo,hi,method)
    axes[0].set_xticks(range(4),sirs);axes[0].set(xlabel='SIR (dB)',ylabel='Target PDR (%)',title='(a) Near–far tolerance\nK=2; SNR 0 dB; angle 10–60°')
    for ax,label,angle in [(axes[1],'(b)','20–40°'),(axes[2],'(c)','40–90°')]:
        ax.set_xticks([2,4,6,8]);ax.set(xlabel='Concurrent packets K',title=f'{label} Fixed target, add interferers\nSNR 10 dB; min. angle {angle}')
    for ax in axes:ax.set_ylim(-3,105);ax.set_yticks([0,25,50,75,100]);ax.grid(alpha=.15)
    fig.legend(*axes[0].get_legend_handles_labels(),fontsize=8,ncol=4,loc='upper center',bbox_to_anchor=(.5,1.08),frameon=False)
    save(fig,'P3_operating_ranges')

    # P4: rows prevent four near-equal PDRs from covering one another.
    scenarios=[('Noise-limited','SNR −20, SIR 0 dB\nangle 20–40°, K=2',ogroup('snr',snr_db=-20,individual_sir_db=0)),
        ('Nearly collinear','SNR −8, SIR −5 dB\nangle 0–2°, K=2',ogroup('angle',angle_low=0,individual_sir_db=-5)),
        ('Moderate separation','SNR −8, SIR −5 dB\nangle 10–20°, K=2',ogroup('angle',angle_low=10,individual_sir_db=-5)),
        ('Strong-interferer recovery','SNR 0, SIR −10 dB\nangle 10–60°, K=2',egroup(0,-10)),
        ('Six-packet moderate angle','SNR 10, SIR −5 dB\nangle 20–40°, K=6',None),
        ('Higher-order limit','SNR 10, SIR −5 dB\nangle 40–90°, K=8',None)]
    fig,axes=plt.subplots(2,3,figsize=(7.2,4.6),sharey=True)
    for idx,(ax,(name,setting,group)) in enumerate(zip(axes.flat,scenarios)):
        for i,method in enumerate(METHODS):
            if group is None:
                population=moderate if idx==4 else nested
                val,lo,hi,n=metrics([r for r in population if r['spec']['k']==(6 if idx==4 else 8)],method)
            else:val,lo,hi,n=metrics(group,method)
            ax.errorbar(val,i,xerr=[[val-lo],[hi-val]],fmt=MARKERS[i],color=COLORS[i],capsize=3,ms=7 if i==0 else 5,lw=2 if i==0 else 1.1)
            ax.text(val,i+.20,f'{val:.1f}%',ha='center',va='top',fontsize=8,color=COLORS[i])
            DATA.append(dict(scenario=name,setting=setting.replace('\n','; '),method=method,pdr=val,ci_low=lo,ci_high=hi,n=n))
        ax.set(xlim=(-5,105),ylim=(3.6,-.65),xlabel='Target PDR (%)',title=f'{name}\n{setting}',xticks=[0,50,100]);ax.set_yticks(range(4),LABELS);ax.grid(alpha=.15,axis='x')
        ax.text(.98,.02,f'n={n}',transform=ax.transAxes,ha='right',va='bottom',fontsize=6.5,color='.4')
    save(fig,'P4_advantage_failure_scenarios');csvout('scenario_comparison.csv',DATA)

    # P5: reference-use purpose is visible in quantiles and packet position.
    fig,axes=plt.subplots(1,2,figsize=(7.2,2.8));snrs=sorted({r['spec']['snr_db'] for r in pilot});q50=[];q90=[];reference_quantiles=[];reference_positions=[]
    for snr in snrs:
        v=[q['delta_deg'] for r in pilot if r['spec']['snr_db']==snr for q in r['reference']];q50.append(np.median(v));q90.append(np.percentile(v,90));reference_quantiles.append(dict(snr=snr,packets=88,symbols=len(v),median=q50[-1],p90=q90[-1]))
    axes[0].plot(snrs,q90,'o-',color='#9a5ca6',label='90th percentile');axes[0].plot(snrs,q50,'s--',color='#397fc1',label='Median');axes[0].axvline(om['s_good'],color='.5',ls=':',lw=1)
    axes[0].set(xlabel='Isolated-packet input SNR (dB)',ylabel='Observed direction deviation (°)',title='(a) Noise limits reference consistency');axes[0].legend(fontsize=7)
    for label,group,color,ls in [('Isolated', [r for r in pilot if r['spec']['snr_db']==om['s_good']], '#404040','--'),('Collision',ogroup('angle',individual_sir_db=-10),'#137b61','-')]:
        arr=np.array([[q['delta_deg'] for q in r['reference']] for r in group]);x=np.linspace(0,1,38)
        for j,pos in enumerate(x):reference_positions.append(dict(condition=label,position=pos,packets=len(group),median=float(np.median(arr[:,j])),p90=float(np.percentile(arr[:,j],90))))
        axes[1].plot(x,np.median(arr,axis=0),color=color,ls=ls,label=f'{label}: median')
        axes[1].plot(x,np.percentile(arr,90,axis=0),color=color,ls=ls,lw=2,label=f'{label}: P90')
    axes[1].set(xlabel='Normalized payload position',ylabel='Observed direction deviation (°)',title='(b) Payload consistency under collision\nSNR −8 dB; interferer SIR −10 dB',ylim=(0,10));axes[1].legend(fontsize=7,ncol=2,loc='lower left')
    for ax in axes:ax.grid(alpha=.15)
    save(fig,'P5_reference_validity');csvout('reference_quantiles.csv',reference_quantiles);csvout('reference_positions.csv',reference_positions)

    # T12: exact paired decomposition, same percentage axis and no invisible zero-harm series.
    fig,axes=plt.subplots(1,2,figsize=(7.2,2.8));paired=[]
    groups=[('Near sensitivity; SIR 0 dB',om['snrs'],[ogroup('snr',snr_db=s,individual_sir_db=0) for s in om['snrs']],'Target SNR (dB)'),
            ('Interference sweep; SNR −8 dB',[-10,-5,0,5],[ogroup('angle',angle_low=20,individual_sir_db=s) for s in [-10,-5,0,5]],'Individual-interferer SIR (dB)')]
    for ax,(title,levels,gg,xlabel) in zip(axes,groups):
        sp=[];mr=[];resc=[];harm=[]
        for level,group in zip(levels,gg):
            n=len(group);sv=sum(r['metrics']['sp']['delivered'] for r in group);mv=sum(r['metrics']['mrc']['delivered'] for r in group)
            rescue=sum(r['metrics']['sp']['delivered'] and not r['metrics']['mrc']['delivered'] for r in group);damage=sum(not r['metrics']['sp']['delivered'] and r['metrics']['mrc']['delivered'] for r in group)
            assert sv-mv==rescue-damage
            sp.append(100*sv/n);mr.append(100*mv/n);resc.append(100*rescue/n);harm.append(100*damage/n)
            paired.append(dict(panel=title,level=level,n=n,sp_pdr=sp[-1],mrc_pdr=mr[-1],rescue=resc[-1],harm=harm[-1]))
        x=np.arange(len(levels));ax.bar(x,resc,width=.5,color='#95c7b8',alpha=.85,label='Rescued by SP')
        if any(harm):
            ax.bar(x,-np.array(harm),width=.5,color='#c95665',label='Lost by SP')
            for xx,h in zip(x,harm):
                if h:ax.text(xx,-h-1,f'−{h:.0f}%',ha='center',va='top',fontsize=8,color='#b33d4d')
        ax.plot(x,sp,'o-',color=COLORS[0],lw=2,label='SP PDR');ax.plot(x,mr,'s--',color='#404040',lw=1.5,label='MRC PDR')
        ax.set_xticks(x,levels);ax.set(xlabel=xlabel,ylabel='Fraction of all target packets (%)',title=title+'\nangle 20–40°',ylim=(-10,105));ax.axhline(0,color='.6',lw=.7);ax.grid(alpha=.15,axis='y')
    legend={}
    for ax in axes:
        handles,labels=ax.get_legend_handles_labels()
        for handle,label in zip(handles,labels):legend.setdefault(label,handle)
    fig.legend(list(legend.values()),list(legend),fontsize=8,ncol=4,loc='upper center',bbox_to_anchor=(.5,1.10),frameon=False)
    save(fig,'T12_pdr_rescue_harm');csvout('T12_paired_decomposition.csv',paired)

    # Additional extreme slice and collision statistics stay compact in the appendix.
    fig,axes=plt.subplots(1,2,figsize=(7.2,2.8))
    for ax,snr in zip(axes,[-10,0]):
        for method in METHODS:
            vals=np.array([metrics(egroup(snr,sir),method) for sir in sirs]);dotinterval(ax,range(4),vals[:,0],vals[:,1],vals[:,2],method,True)
        ax.set_xticks(range(4),sirs);ax.set(xlabel='Individual-interferer SIR setting (dB)',ylabel='PDR (%)',title=f'Target SNR={snr} dB; angle 10–60°',ylim=(-3,105));ax.legend(fontsize=8);ax.grid(alpha=.15)
    save(fig,'A1_complete_extreme_sweep')

    # Fair timing: same FFT producer, same score function, same PHY output.
    tm=json.loads((OUT/'timing_matched.json').read_text());records=[r for r in tm['records'] if not r['warmup']];timingrows=[]
    for r in records:
        for method in ['mrc','sp']:timingrows.append(dict(k=r['k'],repeat=r['repeat'],method=method,**{k:v for k,v in r['methods'][method].items() if k!='cache'}))
    csvout('T13_matched_timings.csv',timingrows)
    fig,axes=plt.subplots(1,2,figsize=(7.2,3.0));ks=list(c.b.KS)
    for method,color,marker in [('mrc','#404040','s'),('sp',COLORS[0],'o')]:
        y=[];lo=[];hi=[]
        for k in ks:
            vv=[r['methods'][method]['micro_ms']*1000/(k*38) for r in records if r['k']==k];y.append(np.median(vv));lo.append(np.percentile(vv,10));hi.append(np.percentile(vv,90))
        axes[0].plot(ks,y,marker=marker,color=color,label='SP' if method=='sp' else 'MRC');axes[0].fill_between(ks,lo,hi,color=color,alpha=.12)
    axes[0].set(xlabel='Concurrent packets K',ylabel='Ranking time (µs / payload symbol)',title='(a) Incremental signed-ranking cost\nIdentical precomputed FFT and argmax path',ylim=(0,None));axes[0].set_xticks(ks);axes[0].legend();axes[0].grid(alpha=.15)
    parts=['configuration_ms','fft_ms','score_ms','phy_ms'];partcolors=['#d8ae5b','#6f9ebd','#40967d','#a39ca7']
    max_stack=0
    for i,k in enumerate(ks):
        for shift,method in [(-.18,'mrc'),(.18,'sp')]:
            bottom=0
            for part,color in zip(parts,partcolors):
                value=np.median([r['methods'][method][part] for r in records if r['k']==k]);axes[1].bar(i+shift,value,bottom=bottom,width=.32,color=color,edgecolor='white',lw=.4,hatch='//' if method=='sp' else None);bottom+=value
            max_stack=max(max_stack,bottom)
    axes[1].set_xticks(range(5),ks);axes[1].set(xlabel='Concurrent packets K (MRC left / SP hatched right)',ylabel='Per-burst stage time (ms)',title='(b) Matched payload path, own references\nComponents show per-stage medians')
    axes[1].set_ylim(0,1.38*max_stack)
    axes[1].legend([Patch(facecolor=co) for co in partcolors],['Reference/config','Shared FFT kernel','Ranking','FEC/CRC'],fontsize=8,ncol=2,loc='upper left');axes[1].grid(alpha=.15,axis='y')
    save(fig,'T13_audited_overhead')
    # Compact appendix keeps the measured losses instead of all-zero table columns.
    with PdfPages(OUT/'redesigned_figures.pdf') as pdf:
        for name,fig in FIGS:pdf.savefig(fig,bbox_inches='tight');plt.close(fig)
    subprocess.run(['pdfunite',*[str(OUT/'figures'/f'{name}.pdf') for name in ['P3_operating_ranges','P5_reference_validity','T12_pdr_rescue_harm']],str(OUT/'recommended_main_figures.pdf')],check=True)
    six=ROOT/'real_usrp_outputs/six_packet_fig1_fig3_20261104/strong_interference/fig1_fig3_six_packet.pdf'
    subprocess.run(['pdfunite',str(six),str(OUT/'recommended_main_figures.pdf'),str(OUT/'main_with_mechanism.pdf')],check=True)
    subprocess.run(['pdfunite',str(six),str(OUT/'redesigned_figures.pdf'),str(OUT/'all_with_mechanism.pdf')],check=True)
    thumbs=[]
    for name,_ in FIGS:
        im=Image.open(OUT/'figures'/f'{name}.png').convert('RGB');im.thumbnail((1050,430));canvas=Image.new('RGB',(1070,460),'white');canvas.paste(im,((1070-im.width)//2,25));ImageDraw.Draw(canvas).text((12,6),name,fill='black');thumbs.append(canvas)
    ov=Image.new('RGB',(2140,460*((len(thumbs)+1)//2)),'#eeeeee')
    for i,im in enumerate(thumbs):ov.paste(im,((i%2)*1070,(i//2)*460))
    ov.save(OUT/'overview.png')
    cells=[]
    for snr in [-10,0]:
        for sir in sirs:
            for method in METHODS:
                val,lo,hi,n=metrics(egroup(snr,sir),method);cells.append(dict(snr=snr,sir=sir,method=method,n=n,pdr=val,ci_low=lo,ci_high=hi))
    csvout('extreme_cells.csv',cells)
    csvout('nested_cells.csv',[dict(angle=angle,k=k,method=method,pdr=metrics([r for r in pop if r['spec']['k']==k],method)[0],n=32) for angle,pop in [('20–40',moderate),('40–90',nested)] for k in (2,4,6,8) for method in METHODS])
    summary=dict(new_extreme_trials=len(extreme),new_nested_trials=len(nested)+len(moderate),algorithm_changed=False,old_main_algorithm_hashes_match=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in om['code_sha256'].items()),
        timing_parity_results=tm['verified_packet_method_results'],figures=[n for n,_ in FIGS],scenario_data=DATA,t12=paired)
    c.write(OUT/'summary.json',summary)
    print(json.dumps(dict(figures=len(FIGS),new_trials=len(extreme),timing_parity=tm['verified_packet_method_results']),indent=2))

if __name__=='__main__':main()
