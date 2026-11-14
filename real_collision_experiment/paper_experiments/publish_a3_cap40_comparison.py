"""Publish paired cap-4/cap-40 A3 results and an explicitly selected raw repeat."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import csv,hashlib,json,shutil,subprocess
from collections import defaultdict
import numpy as np
from real_collision_experiment.paper_experiments import run_native_iq_heatmaps as n
from real_collision_experiment.paper_experiments.render_a3_density_lambda import render

CAP4=ROOT/'real_usrp_outputs/revision_a3_actual_density_cap4_20261102'
CAP40=ROOT/'real_usrp_outputs/revision_a3_actual_density_cap40_20261102'
DEST=ROOT/'real_usrp_outputs/revision_heatmaps_A3_C1_guard_v2'
BACKUP='backup_a3_before_cap40_single_repeat_20261102'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(root,cap):
    manifest=json.loads((root/'manifest_A3_density_delay.json').read_text())
    assert manifest['lambda_global_max']==cap
    assert manifest['timing_axis']=='actual_arrival_density'
    for name,sha in manifest['code_sha256'].items():
        assert digest(root/'code_snapshot'/name)==sha
    data={}
    for spec in manifest['jobs']:
        job=json.loads((root/'jobs'/(n.a.job_key(spec)+'.json')).read_text())
        assert job['revision_hash']==manifest['revision_hash']
        data[spec['k'],spec['arrival_density'],spec['repeat']]=job
    assert len(data)==256
    return manifest,data


def write_csv(path,rows):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def backup(root):
    directory=root/BACKUP
    directory.mkdir(exist_ok=True)
    paths=list((root/'figures').glob('A3*'))+list(root.glob('A3*.md'))
    paths += [root/name for name in ('all_figures_10.pdf','all_figures_12.pdf','validation.json')]
    for path in paths:
        if not path.is_file():continue
        target=directory/path.relative_to(root)
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():shutil.copy2(path,target)


def stats(rows,cap):
    x=np.array([r[f'lambda_cap{cap}'] for r in rows])
    bounds=np.array([r[f'individual_bound_cap{cap}'] for r in rows])
    return dict(packets=len(rows),minimum=float(x.min()),maximum=float(x.max()),
        span=float(np.ptp(x)),std=float(x.std()),
        at_global_cap=int(np.isclose(x,cap,rtol=0,atol=1e-9).sum()),
        at_individual_cap=int(np.isclose(x,bounds,rtol=0,atol=1e-9).sum()),
        unique_values=len(set(x)))


def main():
    m4,jobs4=records(CAP4,4);m40,jobs40=records(CAP40,40)
    assert set(jobs4)==set(jobs40)
    packets=[];cells=defaultdict(lambda:dict(packets=0,success_cap4=0,success_cap40=0,gained=0,lost=0))
    for key,j4 in sorted(jobs4.items()):
        j40=jobs40[key]
        for field in ('truth','noise_budget','timing','config','calibration'):
            assert j4[field]==j40[field],(key,field)
        assert j40['noise_budget']['min_residual_covariance_eigenvalue']>=0
        assert len(j4['targets'])==len(j40['targets'])==key[0]
        for a,b in zip(j4['candidate_estimates'],j40['candidate_estimates']):
            for field in ('channel_sp','L_u','theta_total','power_sp','noise_sigma2_sp','cfo_bins_sp','sto_samples_sp'):
                assert a[field]==b[field],(key,field)
        for a,b in zip(j4['targets'],j40['targets']):
            assert a['target_index']==b['target_index']
            for target,cap in ((a,4),(b,40)):
                assert np.isfinite(target['lambda_sp'])
                assert 0<=target['lambda_sp']<=target['lambda_cap']+1e-9<=cap+1e-9
                estimate=j4['candidate_estimates'][target['target_index']]
                reference_cap=max(0.,(estimate['L_u']-.05)/max(1-estimate['L_u'],1e-12))
                assert np.isclose(target['lambda_cap'],min(cap,reference_cap))
            k,rho,repeat=key
            ok4=a['methods']['sp']['delivered'];ok40=b['methods']['sp']['delivered']
            packets.append(dict(k=k,density=rho,repeat=repeat,target_index=a['target_index'],
                source_position=j4['truth'][a['target_index']]['position'],
                lambda_cap4=a['lambda_sp'],lambda_cap40=b['lambda_sp'],
                individual_bound_cap4=a['lambda_cap'],individual_bound_cap40=b['lambda_cap'],
                delivered_cap4=ok4,delivered_cap40=ok40))
            cell=cells[k,rho];cell['packets']+=1;cell['success_cap4']+=ok4;cell['success_cap40']+=ok40
            cell['gained']+=ok40 and not ok4;cell['lost']+=ok4 and not ok40
    assert len(packets)==1792
    k10=[r for r in packets if r['k']==10];assert len(k10)==640
    scores=[]
    for repeat in range(16):
        rows=[r for r in k10 if r['repeat']==repeat]
        s4,s40=stats(rows,4),stats(rows,40)
        scores.append(dict(repeat=repeat,global_cap_hits=s4['at_global_cap']+s40['at_global_cap'],
            normalized_std=s4['std']/4+s40['std']/40,
            **{f'{name}_cap{cap}':value for cap,s in ((4,s4),(40,s40)) for name,value in s.items()}))
    # User requested a varied illustration with fewer upper-bound values.
    # Use the same repeat for both caps, with no filtering by decode outcome.
    scores.sort(key=lambda s:(s['global_cap_hits'],-s['normalized_std'],s['repeat']))
    repeat=scores[0]['repeat']
    selection=dict(selected_repeat=repeat,repeat_indexing='zero based',
        criterion='Minimize total global-cap hits across the two 40-value maps; ties maximize std(cap4)/4 + std(cap40)/40',
        illustrative_selection=True,representative_population_claim=False,
        no_filter_on_decode_success=True,all_10_packets_at_all_4_densities=True,
        same_repeat_for_both_caps=True,ranking=scores)
    for root in (CAP4,n.OUT,DEST):backup(root)
    render(CAP4,repeat=repeat);render(CAP40,repeat=repeat)
    original_label=n.h.LABELS['sp']
    try:
        n.h.LABELS['sp']=r'SP-Decoder, $\lambda_{max}=40$'
        n.h.render('A3_density_delay',CAP40,sp_policy=n.GUARDED_PAIR_POLICY)
    finally:
        n.h.LABELS['sp']=original_label
    totals={}
    for cap in (4,40):
        totals[f'cap{cap}']=dict(global_cap=cap,packets=len(packets),
            successes=sum(r[f'delivered_cap{cap}'] for r in packets),
            k10_successes=sum(r[f'delivered_cap{cap}'] for r in k10),
            selected_repeat=stats([r for r in k10 if r['repeat']==repeat],cap))
    assert totals['cap4']['successes']==1065
    cell_rows=[dict(k=k,density=rho,**cell,pdr_cap4=cell['success_cap4']/cell['packets'],
        pdr_cap40=cell['success_cap40']/cell['packets']) for (k,rho),cell in sorted(cells.items())]
    for root in (n.OUT,DEST):
        figures=root/'figures'
        c1_before={p.name:digest(p) for p in figures.glob('C1*') if p.is_file()}
        for source,cap,suffix in ((CAP4,4,''),(CAP40,40,'_cap40')):
            for name in ('A3_density_lambda_k10','A3_density_delay_sp'):
                for ext in ('pdf','png','svg'):
                    shutil.copy2(source/'figures'/f'{name}.{ext}',figures/f'{name}{suffix}.{ext}')
            for name in ('A3_density_lambda_k10_per_packet','A3_density_lambda_k10_summary',
                         'A3_density_lambda_k10_selected_repeat','A3_density_delay_metrics'):
                shutil.copy2(source/'figures'/f'{name}.csv',figures/f'{name}{suffix}.csv')
            for name in ('A3_density_lambda_k10','A3_density_delay'):
                metadata=json.loads((source/'figures'/f'{name}_figure_manifest.json').read_text())
                metadata.update(result_root=str(source),global_lambda_bound=cap,
                    published_basename=(name if 'lambda' in name else name+'_sp')+suffix,
                    selection=selection if 'lambda' in name else None)
                metadata['figures']=[metadata['published_basename']+'.pdf']
                n.a.write_json(figures/f'{name}{suffix}_figure_manifest.json',metadata)
        n.a.write_json(root/'manifest_A3_density_delay_cap40.json',dict(m40,external_result_root=str(CAP40)))
        write_csv(root/'A3_cap4_cap40_packet_comparison.csv',packets)
        write_csv(root/'A3_cap4_cap40_cell_comparison.csv',cell_rows)
        write_csv(root/'A3_lambda_repeat_selection.csv',scores)
        n.a.write_json(root/'A3_lambda_repeat_selection.json',selection)
        main_pdfs=[figures/f'{stage}_{method}.pdf' for stage in n.h.STAGES
                   for method in (n.h.METHODS if stage.startswith('C1') else ('sp',))]
        main_pdfs.append(figures/'A3_density_lambda_k10.pdf')
        control_pdfs=[figures/'A3_density_delay_sp_cap40.pdf',figures/'A3_density_lambda_k10_cap40.pdf']
        comparison=[figures/'A3_density_delay_sp.pdf',figures/'A3_density_lambda_k10.pdf',*control_pdfs]
        for name,paths in (('all_figures_10.pdf',main_pdfs),('all_figures_12.pdf',main_pdfs+control_pdfs),
                           ('A3_cap4_cap40_comparison.pdf',comparison)):
            subprocess.run(['pdfunite',*[str(p) for p in paths],str(root/name)],check=True)
        assert c1_before=={p.name:digest(p) for p in figures.glob('C1*') if p.is_file()}
        summary=dict(totals=totals,paired_scenes=256,paired_targets=1792,
            identical_IQ_timing_noise_and_references=True,reference_reliability_bounds_preserved=True,
            PDR_uses_all_16_repeats=True,lambda_maps_use_one_paired_repeat=True,
            selection=selection,cap4_root=str(CAP4),cap40_root=str(CAP40),
            default_published_cap=4,comparison_cap=40,previous_cap10_retained_as_history=True,
            gained=sum(r['delivered_cap40'] and not r['delivered_cap4'] for r in packets),
            lost=sum(r['delivered_cap4'] and not r['delivered_cap40'] for r in packets),
            unchanged_C1_sha256=c1_before,
            figure_sha256={p.name:digest(p) for p in comparison},
            revision_cap4=m4['revision_hash'],revision_cap40=m40['revision_hash'])
        n.a.write_json(root/'A3_cap4_cap40_comparison.json',summary)
        validation_path=root/'validation.json'
        if validation_path.exists():
            validation=json.loads(validation_path.read_text())
            validation.update(extra_pdf_sha256={'A3_density_lambda_k10.pdf':digest(figures/'A3_density_lambda_k10.pdf')},
                A3_lambda_display_mode='single_paired_repeat',A3_lambda_selected_repeat=repeat,
                A3_current_comparison_cap=40,A3_current_comparison_report='A3_cap4_cap40_comparison.json')
            n.a.write_json(validation_path,validation)
        note=(f'# A3 cap 4 versus cap 40: current figures\n\n'
            f'The comparison global lambda bound is now 40 (previously 10). '
            f'All 256 paired scenes and 1792 targets were rerun; PDR uses all 16 repeats.\n\n'
            f'Both lambda maps show raw values from repeat {repeat} (zero based), '
            f'with all 10 packets at all four densities. These are an intentionally selected '
            f'illustration, not population means. The selection minimizes the combined number '
            f'of global-bound values, then maximizes the sum of normalized standard deviations. '
            f'No packet or repeat was selected by decoding success. All 16 candidates and '
            f'their scores are in A3_lambda_repeat_selection.csv.\n\n'
            f'Cap 4 selected map: {totals["cap4"]["selected_repeat"]}\n\n'
            f'Cap 40 selected map: {totals["cap40"]["selected_repeat"]}\n\n'
            f'Current outputs: figures/A3_density_lambda_k10.svg, '
            f'figures/A3_density_lambda_k10_cap40.svg, '
            f'figures/A3_density_delay_sp_cap40.pdf, A3_cap4_cap40_comparison.pdf, '
            f'and all_figures_12.pdf. Files with cap10 in their names are historical. '
            f'Previous active figures are preserved in {BACKUP}.\n')
        (root/'A3_CAP40_SINGLE_REPEAT.md').write_text(note)
        doc=root/'A3_ACTUAL_DENSITY.md'
        if doc.exists():
            text=doc.read_text()
            marker='<!-- CURRENT_CAP40_SINGLE_REPEAT -->'
            if marker not in text:
                doc.write_text(marker+'\nCurrent figures use cap 4 versus cap 40 and raw values from '
                    f'paired repeat {repeat}. See [current results](A3_CAP40_SINGLE_REPEAT.md). '
                    'The earlier cap-10 / mean-only descriptions below are historical.\n\n'+text)
    shutil.copy2(Path(__file__),CAP40/'code_snapshot'/Path(__file__).relative_to(ROOT))
    shutil.copy2(Path(render.__code__.co_filename),CAP40/'code_snapshot'/Path(render.__code__.co_filename).relative_to(ROOT))
    print(json.dumps(dict(totals=totals,selection=selection),indent=2))


if __name__=='__main__':main()
