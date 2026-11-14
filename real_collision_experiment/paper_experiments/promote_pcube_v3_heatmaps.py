"""Publish user-approved PCube V3 scores from same-IQ paired trials.

Only PCube metrics change. Every other metric, source, lambda and IQ provenance
is retained from the immutable pre-adoption backup. No decoding is fabricated:
the trial's 512 native-IQ re-decodes were validated against these exact scenes.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import hashlib,json,shutil
from real_collision_experiment.paper_experiments import run_native_iq_heatmaps as n

BACKUP_NAME='backup_pcube_legacy_before_v3_20261030'


def main():
    out=n.OUT;backup=out/BACKUP_NAME;trial=out/'pcube_repair_v3'
    if json.loads((out/'manifest_A3_density_delay.json').read_text()).get('timing_axis')=='actual_arrival_density':
        assert json.loads((out/'manifest_C1_snr_sir.json').read_text())['pcube_policy']==n.DEFAULT_PCUBE_POLICY
        print('PCube V3 already adopted; preserving the newer actual-density A3.')
        return
    n.initialize()
    assert n.AUDIT==json.loads((out/'source_audit.json').read_text())
    manifest=json.loads((trial/'run_manifest.json').read_text())
    assert manifest['policy']==n.DEFAULT_PCUBE_POLICY
    assert manifest['source_sha256']==n.AUDIT['source_file_sha256']
    assert manifest['files']['compare/PCube/soft_grouping.py']==hashlib.sha256((ROOT/'compare/PCube/soft_grouping.py').read_bytes()).hexdigest()
    results=json.loads((trial/'paired_results.json').read_text())
    paired={n.a.job_key(r['spec']):r for r in results['rows'] if not r['heldout']}
    assert len(paired)==512
    revision=hashlib.sha256((n.a.revision_hash()+Path(n.__file__).read_text()+json.dumps(n.AUDIT,sort_keys=True)).encode()).hexdigest()
    jobs=[];manifests=[];gained=lost=changed=0
    totals={}
    for stage in n.h.STAGES:
        m=json.loads((backup/f'manifest_{stage}.json').read_text())
        old_revision=m['revision_hash']
        m.update(revision_hash=revision,pcube_policy=n.DEFAULT_PCUBE_POLICY,
            pcube_update=dict(kind='same_IQ_PCUBE_only_redecode',from_revision=old_revision,
                trial='pcube_repair_v3/paired_results.json',backup=BACKUP_NAME))
        before_sum=after_sum=0
        for spec in m['jobs']:
            key=n.a.job_key(spec);j=json.loads((backup/'jobs'/(key+'.json')).read_text())
            before=json.loads(json.dumps(j))
            if stage.startswith('C1'):
                r=paired[key]
                assert r['spec']==spec and r['noise_budget']==j['noise_budget']
                assert r['sources']==[t['source_index'] for t in j['truth']]
                assert len(j['targets'])==1 and j['targets'][0]['target_index']==spec['focus'][0]
                t=j['targets'][0];old=t['methods']['pcube'];new=r['methods']['repair']
                assert old==r['methods']['legacy']
                a,b=old['delivered'],new['delivered']
                gained+=b and not a;lost+=a and not b;changed+=old!=new
                before_sum+=a;after_sum+=b
                t['methods']['pcube']=new
                t['pcube_grouping']=r['grouping']
            j.update(revision_hash=revision,pcube_policy=n.DEFAULT_PCUBE_POLICY,
                pcube_update=dict(kind='PCube_only_same_IQ_score_update' if stage.startswith('C1') else 'unmodified_A3_metrics',
                    from_revision=before['revision_hash'],backup=BACKUP_NAME))
            # Strip only explicitly changed metadata/PCube fields and compare
            # the complete remaining object, including every other decision.
            check=json.loads(json.dumps(j))
            for k in ('revision_hash','pcube_policy','pcube_update'):check.pop(k,None);before.pop(k,None)
            if stage.startswith('C1'):
                for a,b in zip(check['targets'],before['targets']):
                    a['methods'].pop('pcube');b['methods'].pop('pcube');a.pop('pcube_grouping',None)
            assert check==before,key
            jobs.append((key,j))
        if stage.startswith('C1'):totals[stage]=dict(before=before_sum,after=after_sum,packets=256)
        manifests.append((stage,m))
    assert len(jobs)==768 and gained==15 and lost==0
    assert totals=={'C1_snr_sir':dict(before=95,after=105,packets=256),
                   'C1_angle_sir':dict(before=83,after=88,packets=256)}
    for key,j in jobs:n.a.write_json(out/'jobs'/(key+'.json'),j)
    for stage,m in manifests:n.a.write_json(out/f'manifest_{stage}.json',m)
    snapshots=['real_collision_experiment/paper_experiments/run_native_iq_heatmaps.py',
        'real_collision_experiment/paper_experiments/run_revision_abc.py',
        'real_collision_experiment/paper_experiments/run_resubmission_heatmaps.py',
        'real_collision_experiment/paper_experiments/promote_pcube_v3_heatmaps.py',
        'real_collision_experiment/paper_experiments/publish_native_iq_heatmaps.py',
        'compare/real_packet_decoders.py','compare/PCube/soft_grouping.py','compare/PCube/evaluate_pcube.py']
    for name in snapshots:
        dst=out/'code_snapshot'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dst)
    validation=dict(policy=n.DEFAULT_PCUBE_POLICY,user_approved=True,revision_hash=revision,
        scenes=768,pcube_same_IQ_redecodes=512,gained=gained,lost=lost,changed_pcube_metrics=changed,
        unchanged_other_methods=True,unchanged_A3=True,unchanged_sources_and_lambda=True,
        source_sha256=n.AUDIT['source_file_sha256'],trial_manifest=manifest,totals=totals,backup=BACKUP_NAME)
    n.a.write_json(out/'pcube_adoption_validation.json',validation)
    n.h.write_csv(out/'C1_pcube_before_after.csv',[
        dict(stage=r['spec']['family'],job=n.a.job_key(r['spec']),
            x=r['spec']['snr_db'] if r['spec']['family']=='C1_snr_sir' else r['spec']['angle_low'],
            sir=r['spec']['sir_db'],old_delivered=r['methods']['legacy']['delivered'],
            v3_delivered=r['methods']['repair']['delivered'],
            old_ser=r['methods']['legacy']['ser'],v3_ser=r['methods']['repair']['ser']) for r in paired.values()])
    for stage in n.h.STAGES:n.h.render(stage,out,sp_policy=n.GUARDED_PAIR_POLICY)
    print(json.dumps(validation['totals'],indent=2))


if __name__=='__main__':main()
