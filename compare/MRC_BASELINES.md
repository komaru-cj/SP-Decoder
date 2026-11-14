# MRC+CIC and MRC+CoRa

Updated 2026-10-28 for the resubmission experiments.

Both baselines combine the physical receive channels using
`w = conjugate(h / ||h||)` once per target packet. The supplied start/CFO/STO
is retained. A supplied physical MRC reference can be reused; otherwise the
existing physical-preamble estimator obtains `h` without payload truth.
Weights stay fixed throughout the target frame.

- CIC estimates its preamble RSSI on that same combined input, then retains
  ICSS intersection, the existing RSSI filter, ten-window SED, and FEC/CRC.
- CoRa estimates peak magnitude on the combined input, then retains the
  published PMD/HPD table, consecutive-symbol Bayesian classifier, and TnB
  BEC/CRC. The published model is unchanged.
- Runtime includes MRC preparation and combination, including failed attempts.
- Baseline result keys are `mrc_cic` and `mrc_cora`. Presentation labels are
  MRC+CIC and MRC+CoRa. Upstream source/model files are unchanged.

## Existing entry points

`PaperComparisonContext.decode_cic` now produces `mrc_cic`. The formal receiver,
AWGN sweeps, native-front-end ablation, runtime drivers, and active plot method
maps use the new key. The old synthetic `compare/CIC/evaluate_cic.py` also
applies MRC instead of selecting a branch per symbol.

`CoRaDetector.detect` prepares target MRC and runs the unchanged scalar CoRa
core. All CoRa runners use this entry point and output `mrc_cora`. New run
cache files have suffix `.mrc_cora.json`; tables use `mrc_cora_prr_tps` and
`mrc_cora_fig11` names. Feature diagnostics also use the combined signal.

Existing IQ, anonymous fine-sync databases, and old numerical results are
preserved. Receiver reports with legacy single-antenna baselines must be
recomputed into a new reports directory (or explicitly overwritten) before
generating new MRC+CIC figures. Changing a plot label does not upgrade data.
The archived legacy Fig.11 timing-fingerprint reconstruction requires matching
regenerated baseline inputs; it is not the resubmission workflow.

## Validation

The baseline/receiver suite passed 26 tests. Four new integration checks cover
CRC-valid CIC and CoRa/TnB recovery with a stronger spatially orthogonal
competitor, own-preamble MRC estimation, and fractional start/STO/CFO invariance
after target-frame cropping. The analysis/statistics suite passed 17 tests.

A real-IQ smoke run used `run_03015131`: the first four anonymous candidates
plus four previously CRC-valid candidates. Both enhanced receivers recovered
CRC-valid packets, used identical MRC weights for each target, and reported
MRC timing. Results are in
`real_collision_experiment/analysis/mrc_baseline_smoke/real_iq_smoke.json`.
This subset verifies execution only and is not a performance estimate.

The complete experiment tables/figures have not yet been recomputed.

Five additional A/B/C tests validate generated-frame CRC recovery, measured
channel/CFO preservation, paired seeds, CSS timing/CFO aliases and channel-assisted
offline identity scoring. Together with the baseline/analysis suites, 48 tests
cover the completed implementation.
