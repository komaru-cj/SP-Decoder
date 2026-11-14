"""Validate and promote the user-approved actual-density A3 and lambda plots."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import json,hashlib,shutil
import numpy as np
from real_collision_experiment.paper_experiments import run_native_iq_heatmaps as n
from real_collision_experiment.paper_experiments.render_a3_density_lambda import render as render_lambda

EXPERIMENT=ROOT/'real_usrp_outputs/revision_a3_actual_density'
BACKUP='backup_a3_nominal_density_20261030'


def main():
    import argparse
    global EXPERIMENT
    parser=argparse.ArgumentParser();parser.add_argument('--experiment',type=Path,default=EXPERIMENT)
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args();EXPERIMENT=args.experiment
    canonical=n.OUT;old=canonical/BACKUP
    manifest=json.loads((EXPERIMENT/'manifest_A3_density_delay.json').read_text())
    uncapped=manifest.get('lambda_fixed_cap_removed',False)
    fixed_cap=manifest.get('lambda_global_max',None if uncapped else 4.)
    compare_to_cap4=uncapped or fixed_cap!=4.
    cap4_root=canonical/'backup_a3_lambda_cap4_20261030'
    cap4_jobs={}
    if compare_to_cap4:
        cap4_manifest=json.loads((cap4_root/'manifest_A3_density_delay.json').read_text())
        cap4_jobs={(s['k'],s['arrival_density'],s['repeat']):n.a.job_key(s) for s in cap4_manifest['jobs']}
    assert manifest['timing_axis']=='actual_arrival_density' and len(manifest['jobs'])==256
    for name,sha in manifest['code_sha256'].items():
        assert hashlib.sha256((EXPERIMENT/'code_snapshot'/name).read_bytes()).hexdigest()==sha
    rows=[];maxerr=0.;successes=0;source_set=set();paired={};comparison=[];above4=0
    for s in manifest['jobs']:
        key=n.a.job_key(s);j=json.loads((EXPERIMENT/'jobs'/(key+'.json')).read_text())
        before=json.loads((old/'jobs'/(s['original_timing_job']+'.json')).read_text())
        assert j['revision_hash']==manifest['revision_hash']
        assert j['noise_budget']['min_residual_covariance_eigenvalue']>=0
        assert j['config']==before['config'] and j['sp_policy']==before['sp_policy']
        assert j['config']['implicit_header'] and j['config']['payload_len']==32
        expected_fields=('source_index','position','cfo_bins','power_per_channel','payload_hex','symbol_bins','scale','constant_phase_rad')
        for a,b in zip(j['truth'],before['truth']):
            assert {k:a[k] for k in expected_fields}=={k:b[k] for k in expected_fields}
        before_starts=np.array([t['start_sample'] for t in before['truth']],dtype=float)
        starts=np.array([t['start_sample'] for t in j['truth']],dtype=float)
        W=float(np.ptp(starts)/8192)
        assert np.ptp(starts)==round((s['k']-1)/s['arrival_density']*8192)
        error=abs((s['k']-1)/W/s['arrival_density']-1);maxerr=max(error,maxerr)
        assert error<.0003
        # Full ordering is allowed to tie after sample quantization, but cannot reverse.
        order=np.argsort(before_starts,kind='stable');assert np.all(np.diff(starts[order])>=0)
        normalized_old=(before_starts-before_starts.min())/np.ptp(before_starts)
        normalized_new=(starts-starts.min())/np.ptp(starts)
        # Original starts were already sample-rounded once; use a two-sample tolerance.
        assert np.max(abs(normalized_old-normalized_new))<=2/min(np.ptp(before_starts),np.ptp(starts))
        signature=[t['source_index'] for t in j['truth']]
        master_key=(s['repeat'],s['k'])
        if master_key in paired:assert signature==paired[master_key]
        else:paired[master_key]=signature
        source_set.update(signature)
        for t in j['targets']:
            assert np.isfinite(t['lambda_sp']) and np.isfinite(t['lambda_cap'])
            assert 0<=t['lambda_sp']<=t['lambda_cap']+1e-8
            e=j['candidate_estimates'][t['target_index']]
            reference_cap=max(0.,(e['L_u']-.05)/max(1-e['L_u'],1e-12))
            assert np.isclose(t['lambda_cap'],reference_cap if uncapped else min(fixed_cap,reference_cap))
            if uncapped:
                assert e['lambda_fixed_global_cap_removed_sp'] and e['lambda_global_max_sp'] is None
            else:assert t['lambda_cap']<=fixed_cap+1e-8
            above4+=t['lambda_sp']>4+1e-9
        if compare_to_cap4:
            old_key=cap4_jobs[s['k'],s['arrival_density'],s['repeat']]
            bounded=json.loads((cap4_root/'jobs'/(old_key+'.json')).read_text())
            assert bounded['truth']==j['truth'] and bounded['noise_budget']==j['noise_budget'] and bounded['timing']==j['timing']
            for a,b in zip(bounded['candidate_estimates'],j['candidate_estimates']):
                for key_field in ('channel_sp','L_u','theta_total','power_sp','noise_sigma2_sp','cfo_bins_sp','sto_samples_sp'):
                    assert a[key_field]==b[key_field],key_field
            for a,b in zip(bounded['targets'],j['targets']):
                comparison.append(dict(k=s['k'],density=s['arrival_density'],repeat=s['repeat'],
                    target=b['target_index'],old_lambda=a['lambda_sp'],new_lambda=b['lambda_sp'],
                    old_delivered=a['methods']['sp']['delivered'],new_delivered=b['methods']['sp']['delivered']))
        successes+=sum(t['methods']['sp']['delivered'] for t in j['targets'])
        rows.append((key,j))
    assert len(rows)==256 and sum(len(j['targets']) for _,j in rows)==1792
    assert not source_set.intersection({3,7,8,13})
    assert len({n.a.source_bank()[i]['position'] for i in source_set})==10
    for repeat in range(16):
        master=paired[repeat,10]
        for k in (4,6,8):assert paired[repeat,k]==master[:k]
    # C1 remains byte-identical at the record and plot levels.
    for stage in ('C1_snr_sir','C1_angle_sir'):
        m=json.loads((canonical/f'manifest_{stage}.json').read_text())
        for s in m['jobs']:
            name=n.a.job_key(s)+'.json'
            assert (canonical/'jobs'/name).read_bytes()==(old/'jobs'/name).read_bytes()
        for f in (canonical/'figures').glob(stage+'_*'):
            assert f.read_bytes()==(old/'figures'/f.name).read_bytes()
    render_lambda(EXPERIMENT)
    validation=dict(scenes=256,targets=1792,successes=successes,density_levels=manifest['density_levels'],
        density_definition=manifest['density_definition'],max_relative_density_error=maxerr,
        unchanged_C1=True,paired_source_payload_power_and_phase=True,
        signed_start_order_preserved_up_to_sample_quantization=True,
        absolute_jitter_preserved=False,source_sha256=manifest['source_sha256'],
        sources=sorted(source_set),positions=10,lambda_values=640,original_backup=BACKUP,
        revision_hash=manifest['revision_hash'])
    validation.update(fixed_cap_4_removed=uncapped,global_lambda_max=fixed_cap,
        reference_reliability_bound_preserved=True,weights_above_4=int(above4),
        same_IQ_and_references_as_cap4_checked=compare_to_cap4)
    if compare_to_cap4:
        assert above4>0
        import csv
        with (EXPERIMENT/'A3_lambda_cap4_comparison.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(comparison[0]));writer.writeheader();writer.writerows(comparison)
        validation['old_successes']=sum(r['old_delivered'] for r in comparison)
        validation['gained']=sum(r['new_delivered'] and not r['old_delivered'] for r in comparison)
        validation['lost']=sum(r['old_delivered'] and not r['new_delivered'] for r in comparison)
    n.a.write_json(EXPERIMENT/'a3_density_validation.json',validation)
    if args.validate_only:
        print(json.dumps(validation,indent=2));return
    if compare_to_cap4:shutil.copy2(EXPERIMENT/'A3_lambda_cap4_comparison.csv',canonical/'A3_lambda_cap4_comparison.csv')
    # Retire only the old A3 records, leaving the 512 C1 records untouched.
    retire_root=canonical/'backup_a3_nocap_before_cap_comparison_20261102'
    if not retire_root.exists():retire_root=cap4_root if uncapped else old
    old_manifest=json.loads((canonical/'manifest_A3_density_delay.json').read_text())
    retired=retire_root/'retired_A3_jobs';retired.mkdir(exist_ok=True)
    for spec in old_manifest['jobs']:
        src=canonical/'jobs'/(n.a.job_key(spec)+'.json')
        if src.exists():
            dst=retired/src.name
            if dst.exists():
                assert src.read_bytes()==dst.read_bytes()
            else:src.rename(dst)
    for key,j in rows:n.a.write_json(canonical/'jobs'/(key+'.json'),j)
    manifest.update(generation_code_snapshot='code_snapshot/a3_actual_density',
        original_arguments=manifest.pop('arguments',{}),
        arguments=dict(timing_axis='actual_arrival_density',density_levels=manifest['density_levels'],
            absolute_jitter_preserved=False,source_result_root=str(EXPERIMENT)))
    n.a.write_json(canonical/'manifest_A3_density_delay.json',manifest)
    shutil.copytree(EXPERIMENT/'code_snapshot',canonical/'code_snapshot/a3_actual_density',dirs_exist_ok=True)
    for name in ('publish_a3_actual_density.py','render_a3_density_lambda.py','publish_native_iq_heatmaps.py'):
        src=Path(__file__).parent/name;dst=canonical/'code_snapshot/a3_actual_density'/src.relative_to(ROOT)
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    for f in (EXPERIMENT/'figures').iterdir():shutil.copy2(f,canonical/'figures'/f.name)
    shutil.copy2(EXPERIMENT/'a3_density_validation.json',canonical/'a3_density_validation.json')
    print(json.dumps(validation,indent=2))


if __name__=='__main__':main()
