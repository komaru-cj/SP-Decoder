"""Bundle reviewed figures, tables and reproducibility material without duplicate IQ."""
from pathlib import Path
import json,zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'real_usrp_outputs/collision_boundary_fairness_20261102'


if __name__=='__main__':
    validation=json.loads((OUT/'validation.json').read_text())
    summary=json.loads((OUT/'results_summary.json').read_text())
    assert validation['complete'] and summary['complete']
    paths=[p for p in OUT.iterdir() if p.is_file() and p.suffix in ('.csv','.json','.md','.png','.pdf')]
    paths += [p for directory in ('figures','code_snapshot','analysis_snapshot') for p in (OUT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    archive=OUT/'all_figures_tables_and_protocol.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(paths):z.write(p,p.relative_to(OUT))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(json.dumps(dict(archive=str(archive),files=len(paths),bytes=archive.stat().st_size,
        figures=len(summary['figures']),targets=validation['targets']),indent=2))
