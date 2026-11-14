#!/usr/bin/env python3
"""Exact cached branch comparison for the user-approved two-track gate.

This is valid only when every candidate in a scene takes the same branch.
Mixed-branch scenes fail closed and must be decoded again. No new waveform,
detector or decoding performance is claimed by this cache assembly.
"""
from pathlib import Path
import sys
import hashlib
import json
from collections import defaultdict
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sp_noise_competition import TWO_PACKET_POLICY
from real_collision_experiment.paper_experiments.run_revision_abc import write_json


def main():
    old = ROOT / 'real_usrp_outputs/revision_abc'
    full = ROOT / 'real_usrp_outputs/revision_abc_noise_lambda_v1'
    out = ROOT / 'real_usrp_outputs/revision_abc_noise_two_packet_v1'
    grouped = defaultdict(list)
    branch_counts = defaultdict(int)
    sources = []
    for path in sorted((full / 'jobs').glob('*.json')):
        new = json.loads(path.read_text())
        original = json.loads((old / 'jobs' / path.name).read_text())
        branches = {e['overlapping_interferer_count_sp'] == 1 for e in new['candidate_estimates']}
        if len(branches) > 1:
            raise ValueError(f'{path.name}: mixed branches require a fresh decoder run')
        use_noise = branches == {True}
        chosen = new if use_noise else original
        spec = new['spec']
        for before, after in zip(original['targets'], chosen['targets']):
            grouped[(spec['family'], spec['k'], spec['snr_db'], spec.get('sir_db'), spec.get('angle_low'))].append(
                dict(old=before['methods']['sp']['delivered'],
                     gated=after['methods']['sp']['delivered']))
        branch_counts[('noise_pair' if use_noise else 'legacy_non_pair')] += 1
        chosen_path = path if use_noise else old / 'jobs' / path.name
        sources.append(dict(job=path.stem, source=str(chosen_path.relative_to(ROOT)),
            sha256=hashlib.sha256(chosen_path.read_bytes()).hexdigest(),
            branch='noise_pair' if use_noise else 'legacy_non_pair'))
    aggregates = []
    for key, rows in grouped.items():
        family, k, snr, sir, angle = key
        aggregates.append(dict(family=family, k=k, snr_db=snr, sir_db=sir,
            angle_low=angle, packets=len(rows),
            old_pdr=float(np.mean([r['old'] for r in rows])),
            gated_pdr=float(np.mean([r['gated'] for r in rows]))))
    write_json(out / 'summary.json', dict(policy=TWO_PACKET_POLICY,
        scope='Exact selection of previously decoded scene branches, not fresh decoding. All scenes have uniform per-candidate gate decisions.',
        gate='one detected payload-overlapping competitor per target; no truth count, power or payload used',
        scenes=len(sources), branches=dict(branch_counts), aggregates=aggregates))
    write_json(out / 'source_audit.json', sources)
    print(json.dumps(dict(scenes=len(sources), branches=dict(branch_counts)), indent=2))


if __name__ == '__main__':
    main()
