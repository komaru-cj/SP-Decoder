# CoRa reproduction for the real-collision datasets

The resubmission baseline is now **MRC+CoRa** (`mrc_cora`). The detector first
estimates/reuses a physical target-preamble channel, applies fixed MRC to the
target frame, and estimates the expected peak magnitude on that combined
signal. The complete CoRa Bayesian and TnB-BEC paths described below follow.
Timing includes MRC. New caches use `*.mrc_cora.json`; result table names use
`mrc_cora_prr_tps`/`mrc_cora_fig11`. Existing single-antenna `cora` results are
historical and have not been converted or relabeled.

This directory contains a runnable reproduction of the complete CoRa decode
path used for the requested comparison.  The implementation is based on the
paper and the authors' v2 artifact (Zenodo record `14582713`), whose original
Python sources and published `200 x 200` posterior grid are preserved under
`upstream/cora_v2`.  The exact TnB dependency at commit `bb33e98` is preserved
under `upstream/TnB_bb33e98`.

The experiment path is:

1. read the common, schedule-free anonymous fine-sync database supplied to all
   methods by the formal experiment;
2. estimate expected FFT peak magnitude from all eight preamble symbols;
3. evaluate every FFT bin with CoRa's PMD and half-period-inversion HPD;
4. quantize onto the authors' published 200-by-200 Bayesian table and apply
   the consecutive-symbol posterior in Equation (2);
5. choose the maximum posterior over all `2**SF` bins, without peak
   preselection; and
6. apply the full TnB BEC candidate-column enumeration and CRC closure before
   validating the 20-byte application payload.

The common sync database replaces only native packet discovery for the formal
fair-comparison protocol.  It is excluded from every method's decoder work
time.  No CoRa detector or TnB BEC stage is removed or replaced.

Run all 32 requested points (including 24 nodes) with:

```bash
PYTHONPATH=. python3 compare/CoRa/run_real_collision.py
```

The two plot-ready supplemental CSVs use the exact schemas of their resident
comparison databases:

- `real_collision_experiment/analysis/fig9_10_12_5s/fig9_10_mrc_cora_prr_tps.csv`
- `real_collision_experiment/analysis/outdoor_fig13_5s/fig_13_mrc_cora_prr_tps.csv`

Indoor Fig.9--12 points retain their 5-second shared-sync window. Outdoor
Fig.13 SF8/SF10 points use the matching 10-second shared-sync database under
`analysis/outdoor_fig13_10s`; their output rows explicitly record
`strict_window_s=10.0`.

Candidate-level audits and the common 32-row table are in `results/`.

The published Fig. 11 result uses every independent collision group in the
5-second shared-sync database at orders 2/4/8/12/16. Rebuild its six baseline
methods and scenes with:

```bash
PYTHONPATH=. python3 real_collision_experiment/analysis/build_fig11_real_run_intervals.py \
  --orders 2,4,8,12,16 --scenes-per-order 100000 --analysis-window-s 5 \
  --reports real_collision_experiment/analysis/fig9_10_12_5s/reports \
  --fine-sync-dir real_collision_experiment/analysis/fig9_10_12_5s/fine_sync \
  --out-dir real_collision_experiment/analysis/fig11_real_run_intervals
```

Then add CoRa with:

```bash
PYTHONPATH=. python3 compare/CoRa/run_fig11_intervals.py \
  --fig11-dir real_collision_experiment/analysis/fig11_real_run_intervals \
  --fine-sync-dir real_collision_experiment/analysis/fig9_10_12_5s/fine_sync \
  --reports-dir real_collision_experiment/analysis/fig9_10_12_5s/reports
```

This appends CoRa-compatible raw and summary rows to the existing Fig. 11
databases, writes separate `cora_fig11_*` supplements and audit metadata, and
regenerates the PNG/PDF/SVG comparison figure with CoRa included.

Rebuild the evidence used by the CoRa failure-mechanism discussion with the
same three directories:

```bash
PYTHONPATH=. python3 compare/CoRa/analyze_fig11_failures.py \
  --fig11-dir real_collision_experiment/analysis/fig11_real_run_intervals \
  --fine-sync-dir real_collision_experiment/analysis/fig9_10_12_5s/fine_sync \
  --reports-dir real_collision_experiment/analysis/fig9_10_12_5s/reports
```

The resulting `mrc_cora_fig11_failure_analysis.json` separates shared-front-end
coverage, CoRa PMD/HPD mis-ranking, explicit-header BEC failure, payload CRC
failure after BEC, and the bounded recovery contributed by TnB.

## Archived legacy Fig. 11 (10s / 15 scenes per order)

The historical comparison under
`real_usrp_outputs/1fig11_real_run_intervals_2_4_8_12_16_scenes` uses a
different 10-second Oracle-associated candidate setting and its historical
detected-plus-mismatch PRR denominator. Add CoRa to that archived figure with:

```bash
PYTHONPATH=. python3 compare/CoRa/run_fig11_legacy_intervals.py \
  --fig11-dir real_usrp_outputs/1fig11_real_run_intervals_2_4_8_12_16_scenes \
  --fine-sync-dir windows/analysis/fig9_10_12_preview/fine_sync \
  --reports-dir windows/analysis/fig9_10_12_preview/reports
```

The companion audit records the recovered legacy candidate IDs and flags the
few scenes whose historical baseline timing trace had been superseded.
