"""Validate paired cap-4/cap-10 A3 reruns and publish the separate cap-10 figures."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import json,csv,hashlib,shutil,subprocess
from collections import defaultdict
import numpy as np
from real_collision_experiment.paper_experiments import run_native_iq_heatmaps as n

CAP4=ROOT/'real_usrp_outputs/revision_a3_actual_density_cap4_20261102'
CAP10=ROOT/'real_usrp_outputs/revision_a3_actual_density_cap10_20261102'
DEST=ROOT/'real_usrp_outputs/revision_heatmaps_A3_C1_guard_v2'


def records(root):
    manifest=json.loads((root/'manifest_A3_density_delay.json').read_text())
    data={}
    for spec in manifest['jobs']:
        j=json.loads((root/'jobs'/(n.a.job_key(spec)+'.json')).read_text())
        assert j['revision_hash']==manifest['revision_hash']
        data[spec['k'],spec['arrival_density'],spec['repeat']]=j
    assert len(data)==256
    return manifest,data


def main():
    m4,cap4=records(CAP4);m10,cap10=records(CAP10)
    assert m4['lambda_global_max']==4 and m10['lambda_global_max']==10
    assert set(cap4)==set(cap10)
    historical=n.OUT/'backup_a3_lambda_cap4_20261030'
    oldm,old=records(historical)
    packet_rows=[];cells=defaultdict(lambda:dict(packets=0,success_cap4=0,success_cap10=0,gained=0,lost=0))
    for key,j4 in cap4.items():
        j10=cap10[key];previous=old[key]
        for field in ('truth','noise_budget','timing','config'):assert j4[field]==j10[field]==previous[field]
        for a,b in zip(j4['candidate_estimates'],j10['candidate_estimates']):
            for field in ('channel_sp','L_u','theta_total','power_sp','noise_sigma2_sp','cfo_bins_sp','sto_samples_sp'):
                assert a[field]==b[field]
        for a,b,c in zip(j4['targets'],j10['targets'],previous['targets']):
            assert a['methods']['sp']==c['methods']['sp'] and a['lambda_sp']==c['lambda_sp']
            assert 0<=a['lambda_sp']<=a['lambda_cap']+1e-9<=4+1e-9
            assert 0<=b['lambda_sp']<=b['lambda_cap']+1e-9<=10+1e-9
            k,rho,repeat=key;position=j4['truth'][a['target_index']]['position']
            delivered4=a['methods']['sp']['delivered'];delivered10=b['methods']['sp']['delivered']
            packet_rows.append(dict(k=k,density=rho,repeat=repeat,source_position=position,target_index=a['target_index'],
                lambda_cap4=a['lambda_sp'],lambda_cap10=b['lambda_sp'],delivered_cap4=delivered4,delivered_cap10=delivered10))
            cell=cells[k,rho];cell['packets']+=1;cell['success_cap4']+=delivered4;cell['success_cap10']+=delivered10
            cell['gained']+=delivered10 and not delivered4;cell['lost']+=delivered4 and not delivered10
    assert len(packet_rows)==1792
    totals={}
    for label,maximum in (('cap4',4),('cap10',10)):
        rows=packet_rows;k10=[r for r in rows if r['k']==10]
        totals[label]=dict(cap=maximum,packets=1792,successes=sum(r['delivered_'+label] for r in rows),
            k10_packets=640,k10_successes=sum(r['delivered_'+label] for r in k10),
            max_lambda=max(r['lambda_'+label] for r in rows),mean_lambda=float(np.mean([r['lambda_'+label] for r in rows])))
    assert totals['cap4']['successes']==1065
    figure_names={
        'A3_density_delay_sp':'A3_density_delay_sp_cap10',
        'A3_density_lambda_k10':'A3_density_lambda_k10_cap10'}
    hashes={}
    for root in (n.OUT,DEST):
        directory=root/'figures'
        for original,published in figure_names.items():
            for ext in ('pdf','png','svg'):
                source=CAP10/'figures'/(original+'.'+ext);target=directory/(published+'.'+ext)
                shutil.copy2(source,target);hashes[target.name]=hashlib.sha256(target.read_bytes()).hexdigest()
        for name in ('A3_density_lambda_k10_per_packet.csv','A3_density_lambda_k10_summary.csv','A3_density_delay_metrics.csv'):
            target=directory/(Path(name).stem+'_cap10.csv');shutil.copy2(CAP10/'figures'/name,target)
        metadata=json.loads((CAP10/'figures/A3_density_lambda_k10_figure_manifest.json').read_text())
        assert metadata['mean_only'] and metadata['global_lambda_bound']==10
        metadata.update(external_result_root=str(CAP10),result_root=str(CAP10),published_figures=list(figure_names.values()))
        n.a.write_json(directory/'A3_density_lambda_k10_cap10_figure_manifest.json',metadata)
        with (root/'A3_cap4_cap10_packet_comparison.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(packet_rows[0]));w.writeheader();w.writerows(packet_rows)
        cell_rows=[dict(k=k,density=rho,**v,pdr_cap4=v['success_cap4']/v['packets'],pdr_cap10=v['success_cap10']/v['packets'])
                   for (k,rho),v in sorted(cells.items())]
        with (root/'A3_cap4_cap10_cell_comparison.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(cell_rows[0]));w.writeheader();w.writerows(cell_rows)
        pdfs=[directory/'A3_density_delay_sp.pdf',directory/'A3_density_lambda_k10.pdf',
              directory/'A3_density_delay_sp_cap10.pdf',directory/'A3_density_lambda_k10_cap10.pdf']
        subprocess.run(['pdfunite',*[str(p) for p in pdfs],str(root/'A3_cap4_cap10_comparison.pdf')],check=True)
        subprocess.run(['pdfunite',str(root/'all_figures_10.pdf'),str(pdfs[2]),str(pdfs[3]),str(root/'all_figures_12.pdf')],check=True)
    summary=dict(totals=totals,paired_scenes=256,paired_targets=1792,
        identical_IQ_timing_noise_and_references=True,cap4_reproduces_historical_results=True,
        mean_only_lambda_figures=True,scene_count_per_mean=16,all_targets_included=True,
        gained=sum(r['delivered_cap10'] and not r['delivered_cap4'] for r in packet_rows),
        lost=sum(r['delivered_cap4'] and not r['delivered_cap10'] for r in packet_rows),
        cap4_root=str(CAP4),cap10_root=str(CAP10),default_published_cap=4,
        reference_reliability_bounds_preserved=True,figure_sha256=hashes,
        code_revision_cap4=m4['revision_hash'],code_revision_cap10=m10['revision_hash'])
    for root in (n.OUT,DEST):n.a.write_json(root/'A3_cap4_cap10_comparison.json',summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
