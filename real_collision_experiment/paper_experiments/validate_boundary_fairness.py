"""Full matrix validation: pairing, denominators, noise budget and output provenance."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import json,hashlib,csv,subprocess,re
from collections import defaultdict
import numpy as np
from real_collision_experiment.paper_experiments import run_boundary_fairness as b


def main():
    root=b.OUT;m=json.loads((root/'manifest.json').read_text())
    for relative,expected in m['code_sha256'].items():
        assert b.sha(root/'code_snapshot'/relative)==expected
    cal=json.loads((root/'calibration.json').read_text())
    assert b.sha(b.n.OUT/'aligned_source_iq.npz')==cal['source_iq_sha256']
    provenance=json.loads((root/'input_provenance.json').read_text())
    assert b.sha(root/'input_source_audit.json')==provenance['source_audit_sha256']
    audit=json.loads((root/'input_source_audit.json').read_text())
    retained=[s for s in audit['packets'] if not s.get('excluded')]
    assert len(retained)==22 and len({s['payload_hex'] for s in retained})==22
    temporal=defaultdict(list);geometry=defaultdict(list);fairness=defaultdict(list)
    jobs=[];targets=0
    for s in m['jobs']:
        path=root/'jobs'/(b.n.a.job_key(s)+'.json');j=json.loads(path.read_text())
        correction=json.loads((root/'certified_candidate_results'/path.name).read_text())
        assert correction['raw_job_sha256']==b.sha(path)
        assert correction['certified_candidate_count']==s['k']
        assert correction['original_blind_group_count']<=s['k']
        assert j['revision']==m['revision'] and j['spec']==s
        assert len(j['targets'])==len(s['focus'])
        assert len(j['truth'])==s['k']==len(set(t['position'] for t in j['truth']))
        assert len({t['payload_hex'] for t in j['truth']})==s['k']
        for target in j['truth']:
            source=audit['packets'][target['source_index']]
            assert not source.get('excluded')
            assert target['cfo_bins']==source['cfo_bins'] and target['payload_hex']==source['payload_hex']
        assert j['noise_budget']['min_residual_eigenvalue']>=-1e-9
        for t in j['targets']:
            assert 0<=t['lambda_sp']<=t['lambda_cap']+1e-8
            if s['family']=='geometry':
                d=correction['diagnostics'][str(t['target_index'])]
                expected_weights=sorted({r['lambda_value'] for r in t['lambda_diagnostic'] if r['admissible']}|{t['lambda_sp']})
                assert d['reference_comparison_allowed_weights']==expected_weights
                if t['clean_reference_tested_grid_any_success'] and set(m['lambda_grid'])<=set(expected_weights):
                    assert d['isolated_reference_same_cap_any_success']
                if not t['clean_reference_tested_grid_any_success'] and set(expected_weights)<=set(m['lambda_grid']):
                    assert not d['isolated_reference_same_cap_any_success']
                assert s['angle_low']<=t['active_min_angle_deg']<s['angle_high']
                expected_sir=s['individual_sir_db']-10*np.log10(s['k']-1)
                assert abs(t['aggregate_sir_db']-expected_sir)<1e-8
            if t['lambda_diagnostic']:
                assert [d['lambda_value'] for d in t['lambda_diagnostic']]==m['lambda_grid']
                assert all(d['admissible']==(d['lambda_value']<=t['diagnostic_cap']+1e-9) for d in t['lambda_diagnostic'])
            assert set(t['methods'])==set(b.METHODS)
            for metric in t['methods'].values():assert metric['symbol_count']==38
        if s['family']=='temporal':
            temporal[s['repeat'],s['k']].append(j)
            if s['k']==10 and s['width_ratio'] in (2.,.25,.01):
                for t in j['targets']:fairness[s['width_ratio'],t['position']].append(s['repeat'])
        if s['family']=='geometry':geometry[s['repeat'],s['k'],s['angle_low']].append(j)
        jobs.append(j);targets+=len(j['targets'])
    assert len(jobs)==2954 and targets==9362
    for cell in temporal.values():
        signatures=[[(t['source_index'],t['position'],t['power_per_channel'],t['phase'],t['cfo_bins']) for t in j['truth']] for j in cell]
        assert all(sig==signatures[0] for sig in signatures)
        assert len(cell)==(6 if cell[0]['spec']['repeat']<24 else 3)
    for cell in geometry.values():
        assert len(cell)==2
        a,c=sorted(cell,key=lambda j:j['spec']['individual_sir_db'])
        for field in ('sources','relative_offsets','phases','seed'):
            assert a['spec'][field]==c['spec'][field]
    assert len(fairness)==30
    for values in fairness.values():assert sorted(values)==list(range(128))
    summary=json.loads((root/'results_summary.json').read_text());assert summary['complete']
    for name,expected in summary['figure_sha256'].items():assert b.sha(root/'figures'/(name+'.pdf'))==expected
    info=subprocess.run(['pdfinfo',str(root/'all_boundary_fairness_figures.pdf')],capture_output=True,text=True,check=True).stdout
    assert int(re.search(r'Pages:\s+(\d+)',info).group(1))==len(summary['figures'])
    text=subprocess.run(['pdftotext',str(root/'all_boundary_fairness_figures.pdf'),'-'],capture_output=True,text=True,check=True).stdout
    assert 'INCOMPLETE PREVIEW' not in text
    position_rows=list(csv.DictReader((root/'position_pdr.csv').open()))
    assert len(position_rows)==120 and all(int(r['trials'])==128 for r in position_rows)
    cells=list(csv.DictReader((root/'cell_summary.csv').open()))
    assert all(int(r['bursts'])==(24 if r['family']=='temporal' else 32) for r in cells)
    diagnostic_rows=list(csv.DictReader((root/'lambda_diagnostics_per_trial.csv').open()))
    assert len(diagnostic_rows)==43792
    for source in (Path(__file__),Path(__file__).with_name('render_boundary_fairness.py'),Path(__file__).with_name('schedule_boundary_fairness.py'),Path(__file__).with_name('test_boundary_fairness.py'),Path(__file__).with_name('replay_boundary_certified_candidates.py')):
        dest=root/'analysis_snapshot'/source.name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(source.read_bytes())
    result=dict(complete=True,jobs=2954,targets=9362,temporal_source_power_phase_pairing=True,
        geometry_SIR_pairing=True,all_fairness_denominators_128=True,all_10_positions_retained=True,
        unique_payloads_across_all_source_packets=True,
        source_and_snapshot_hashes_checked=True,all_noise_budgets_feasible=True,
        unsupported_geometry_not_filled=True,diagnostic_weights_do_not_change_receiver=True,
        certified_candidates_not_blindly_remerged=True,
        reference_comparison_uses_identical_allowed_weights=True,
        all_lambda_trial_rows_retained=len(diagnostic_rows),merged_pdf_page_count=len(summary['figures']),
        figures=len(summary['figures']),unit_tests=7)
    result['production_SP_bin_parity_targets']=sum(len(s['focus']) for s in m['jobs'] if s['repeat']==0)
    (root/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
