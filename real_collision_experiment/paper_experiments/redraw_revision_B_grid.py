#!/usr/bin/env python3
"""Redraw only the requested B grids using the approved two-track policy."""
from pathlib import Path
import sys
import csv
import hashlib
import json
import shutil
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from real_collision_experiment.paper_experiments import run_revision_abc as abc
from real_collision_experiment.paper_experiments import render_revision_abc as render
from sp_noise_competition import TWO_PACKET_POLICY


def main():
    source = ROOT / 'real_usrp_outputs/revision_abc_noise_lambda_v1'
    original = ROOT / 'real_usrp_outputs/revision_abc'
    out = original / 'figures'
    specs = [s for s in json.loads((source / 'manifest_B.json').read_text())['jobs']
             if s['family'] == 'B_grid']
    jobs, evidence = [], []
    for spec in specs:
        key = abc.job_key(spec)
        path = source / 'jobs' / (key + '.json')
        job = json.loads(path.read_text())
        old = json.loads((original / 'jobs' / path.name).read_text())
        # Every candidate in these controlled two-packet scenes selects the
        # noise branch of the approved gate. No fresh decoding is needed.
        assert len(job['candidate_estimates']) == 2
        assert all(e['overlapping_interferer_count_sp'] == 1 for e in job['candidate_estimates'])
        assert job['truth'] == old['truth'] and job['spec'] == old['spec']
        for a, b in zip(job['targets'], old['targets']):
            for method in a['methods']:
                if method != 'sp':
                    assert a['methods'][method] == b['methods'][method]
        jobs.append(job)
        evidence.append(dict(job=key, source=str(path.relative_to(ROOT)),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    assert len(jobs) == 768
    rows, _, _ = render.summarize(jobs)
    backup = out / ('backup_B_grid_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    backup.mkdir()
    names = [f'B_grid_{metric}.{suffix}' for metric in ('pdr', 'ser')
             for suffix in ('pdf', 'png', 'svg')]
    for name in names + ['B_grid_metrics.csv', 'figure_manifest.json', 'B_grid_redraw_manifest.json']:
        if (out / name).exists():
            shutil.copy2(out / name, backup / name)
    render.plt.rcParams.update({'font.size': 9, 'pdf.fonttype': 42, 'svg.fonttype': 'none'})
    for metric in ('pdr', 'ser'):
        render.draw_grid(rows, out, metric)
    render.write_csv(out / 'B_grid_metrics.csv', rows)
    metadata = dict(policy=TWO_PACKET_POLICY, scenes=len(jobs),
        scope='Replot cached SP noise-branch results, valid for all two-track B-grid scenes; unchanged baselines reused; no new decoding/capture.',
        backup=str(backup.relative_to(ROOT)), sources=evidence,
        metrics_csv='B_grid_metrics.csv',
        artifacts={name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in names})
    abc.write_json(out / 'B_grid_redraw_manifest.json', metadata)
    manifest_path = out / 'figure_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest.setdefault('artifact_overrides', {})['B_grid_pdr_and_ser'] = dict(
        policy=TWO_PACKET_POLICY, manifest='B_grid_redraw_manifest.json',
        metrics_csv='B_grid_metrics.csv', original_backup=str(backup.relative_to(out)))
    manifest['mixed_artifact_policies'] = True
    manifest['metrics_note'] = ('B_grid_metrics.csv describes the redrawn two-track grids; '
        'all_metrics.csv and other figures retain the original frozen policy.')
    abc.write_json(manifest_path, manifest)
    print(json.dumps(dict(scenes=len(jobs), backup=str(backup),
        pdfs=[str(out / name) for name in names if name.endswith('.pdf')]), indent=2))


if __name__ == '__main__':
    main()
