"""Compare the fixed-scene PCube trials without modifying paper figures."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/pcube_repair_mpl')
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'real_usrp_outputs/revision_heatmaps_native_iq'


def main():
    versions={v:json.loads((BASE/f'pcube_repair_{v}'/'paired_results.json').read_text())['rows']
              for v in ('v1','v2','v3')}
    fig,axes=plt.subplots(2,4,figsize=(15,7),layout='constrained')
    for row,family in enumerate(('C1_snr_sir','C1_angle_sir')):
        xs=(-30.,-20.,-10.,0.) if row==0 else (0.,2.,5.,10.)
        ys=(-20.,-10.,0.,10.)
        labels=['-30','-20','-10','0'] if row==0 else ['0–2','2–5','5–10','10–20']
        for col,(version,method,title) in enumerate((('v1','legacy','Legacy local PCube'),
                ('v1','repair','Soft groups (v1)'),('v2','repair','Target / noise (v2)'),
                ('v3','repair','Conservative extension (v3)'))):
            totals=np.zeros((4,4));n=np.zeros((4,4))
            for r in versions[version]:
                if r['heldout'] or r['spec']['family']!=family:continue
                s=r['spec'];x=s['snr_db'] if row==0 else s['angle_low']
                ix=xs.index(x);iy=ys.index(s['sir_db'])
                totals[iy,ix]+=r['methods'][method]['delivered'];n[iy,ix]+=1
            assert np.all(n==16)
            values=totals/n;ax=axes[row,col]
            im=ax.imshow(values,origin='lower',vmin=0,vmax=1,cmap='viridis',aspect='auto')
            for iy,ix in np.ndindex(values.shape):
                ax.text(ix,iy,f'{values[iy,ix]:.3f}',ha='center',va='center',
                        color='black' if values[iy,ix]>.6 else 'white',fontsize=10)
            ax.set(xticks=range(4),xticklabels=labels,yticks=range(4),yticklabels=[str(int(y)) for y in ys],
                   xlabel='SNR (dB)' if row==0 else 'Channel separation (degrees)',ylabel='SIR (dB)',
                   title=f'{title} — {int(totals.sum())}/256')
    fig.colorbar(im,ax=axes.ravel().tolist(),label='PDR',shrink=.8)
    fig.suptitle('Same measured-IQ superpositions, same 16 trials per cell; experimental grouping choices')
    out=BASE/'pcube_repair_v3'/'figures';out.mkdir(exist_ok=True)
    for ext in ('pdf','png','svg'):fig.savefig(out/f'C1_pcube_repair_comparison.{ext}',dpi=180)
    plt.close(fig)


if __name__=='__main__':main()
