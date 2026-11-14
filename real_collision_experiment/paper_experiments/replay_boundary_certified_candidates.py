"""Remove blind alias re-merging from an already certified controlled candidate list.

All methods receive the same one-candidate-per-transmission start/CFO list.
No source ID, clean direction, decoded payload or CRC enters this adapter.
Original results remain immutable; every correction is an auditable sidecar.
"""
from pathlib import Path
import sys,os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import argparse,json,hashlib,time
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
from real_collision_experiment.paper_experiments import run_boundary_fairness as b

POLICY='controlled_one_certified_candidate_per_transmission_v1'


class CertifiedContext(b.PaperComparisonContext):
    def _build_physical_candidate_groups(self):
        super()._build_physical_candidate_groups()
        self.blind_alias_groups=[list(g) for g in self._physical_groups]
        count=len(self.estimates)
        order=sorted(range(count),key=lambda i:float(self.estimates[i]['start_sample']))
        self._physical_groups=[[i] for i in order]
        self._physical_group_by_index=[0]*count
        for group,i in enumerate(order):self._physical_group_by_index[i]=group
        self._physical_group_representatives=order


def replay(spec,revision,code_sha):
    key=b.n.a.job_key(spec);path=b.OUT/'jobs'/(key+'.json')
    if not path.exists():return 'missing'
    raw=path.read_bytes();job=json.loads(raw)
    if job.get('revision')!=revision:return 'missing'
    raw_sha=hashlib.sha256(raw).hexdigest();out=b.OUT/'certified_candidate_results'/(key+'.json')
    if out.exists():
        before=json.loads(out.read_text())
        if before['raw_job_sha256']==raw_sha and before['adapter_sha256']==code_sha:return 'cached'
    starts=np.array([t['start_sample'] for t in job['truth']])
    gaps=np.diff(np.sort(starts))
    tolerance=max(4*b.n.CFG.osr,.125*b.n.CFG.samples_per_symbol)
    possible_alias_merge=bool(len(gaps) and gaps.min()<=tolerance)
    default_groups=len(starts);metrics={};diagnostics={}
    unresolved=[]
    if spec['family']=='geometry':
        for target in job['targets']:
            weights=sorted({d['lambda_value'] for d in target['lambda_diagnostic'] if d['admissible']}|{target['lambda_sp']})
            assert 0. in weights
            diagnostics[str(target['target_index'])]=dict(
                isolated_reference_same_cap_any_success=bool(target['clean_reference_mrc']['delivered']),
                reference_comparison_allowed_weights=weights,
                reference_comparison='same target observation and allowed weights; only the reference changes')
            if not target['clean_reference_mrc']['delivered']:unresolved.append(target)
    if possible_alias_merge or unresolved:
        samples,truth,noise=b.synthesize(spec)
        assert truth==job['truth'] and noise==job['noise_budget']
        physical,white,estimates,sigma,W,cal=b.n.a.controlled_inputs(samples,truth,b.n.CFG)
        physical=np.asarray(physical,dtype=np.complex64)
        cache=b.IntegerPayloadCache()
        if possible_alias_merge:
            context=CertifiedContext(physical,estimates,b.n.CFG,frontend_method='pcube',payload_spectrum_cache=cache)
            default_groups=len(context.blind_alias_groups)
        if default_groups<len(starts):
            # Both methods use the same preamble estimator in this controlled input.
            other=CertifiedContext(physical,estimates,b.n.CFG,frontend_method='maloragw',payload_spectrum_cache=cache)
            for target in job['targets']:
                u=target['target_index']
                metrics[str(u)]={
                    'pcube':b.n.h.payload_metric(context.decode_pcube(estimates[u])['symbol_bins'],truth[u],b.n.CFG),
                    'maloragw':b.n.h.payload_metric(other.decode_maloragw(estimates[u])['symbol_bins'],truth[u],b.n.CFG)}
        if unresolved:
            for target in unresolved:
                u=target['target_index'];e=estimates[u]
                spectra=np.asarray([cache.spectra_for(physical,e,b.n.CFG,s) for s in range(b.n.CFG.payload_symbol_count)])
                white_spectra=np.einsum('ab,sbk->sak',W,spectra)
                h=W@b.CHANNELS[truth[u]['source_index']];h/=np.linalg.norm(h)
                orth=np.array([-np.conj(h[1]),np.conj(h[0])])
                p=abs(np.einsum('a,sak->sk',h.conj(),white_spectra))**2
                q=abs(np.einsum('a,sak->sk',orth.conj(),white_spectra))**2
                weights=diagnostics[str(u)]['reference_comparison_allowed_weights']
                recovered=False
                for weight in weights:
                    if b.n.h.payload_metric(np.argmax(p-weight*q,axis=1).tolist(),truth[u],b.n.CFG)['delivered']:
                        recovered=True;break
                diagnostics[str(u)]['isolated_reference_same_cap_any_success']=bool(recovered)
    result=dict(policy=POLICY,revision=revision,adapter_sha256=code_sha,raw_job_sha256=raw_sha,
        certified_candidate_count=len(starts),original_blind_group_count=default_groups,
        corrected=bool(metrics),targets=metrics,diagnostics=diagnostics,
        no_source_identity_or_payload_used_by_adapter=True)
    b.n.a.write_json(out,result)
    return 'corrected' if metrics else 'unchanged'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    b.initialize();m=json.loads((b.OUT/'manifest.json').read_text());code_sha=b.sha(__file__)
    done=0;counts={};started=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers,initializer=b.initialize) as pool:
        fs=[pool.submit(replay,s,m['revision'],code_sha) for s in m['jobs']]
        for i,f in enumerate(as_completed(fs),1):
            result=f.result();counts[result]=counts.get(result,0)+1
            if i%64==0 or i==len(fs):print(f'CERTIFIED {i}/{len(fs)}; {counts}; elapsed={time.perf_counter()-started:.0f}s',flush=True)
    (b.OUT/'certified_candidate_policy.json').write_text(json.dumps(dict(policy=POLICY,adapter_sha256=code_sha,
        counts=counts,complete='missing' not in counts,raw_jobs_unchanged=True),indent=2)+'\n')


if __name__=='__main__':main()
