# Single-path SP reference and weight guard, v2

Current receiver/batch default: `pair_and_noise_reference_guard_v2`.
The current paper heatmaps were redrawn on 2026-10-30 using 22 frame-complete native measured
packet-IQ sources, with the original 1 Msps / 32-byte implicit-header PHY.
See `real_usrp_outputs/revision_heatmaps_native_iq/README.md`. Numerical
development results below describe the earlier static-channel simulations;
they are not the current measured-IQ plot values. The algorithm was unchanged
for the native-IQ redraw; implicit-header decoding was completed for that PHY.
The user explicitly selected a single SP decision path. There is no preliminary
MRC CRC trial, CRC-selected weight, true-channel input, or heatmap-cell rule.
Configuration uses supplied anonymous synchronization, preamble observations,
and noise statistics. Conditional simulations still supply controlled start/CFO.

For a target with more than one observed payload-overlapping competitor, the
existing bounded multiuser branch is unchanged, including its preamble channel,
weight, and cap no greater than four. These guards apply to isolated or
single-competitor targets, not transmitted truth K.

## Reference and power consistency

The single-competitor branch uses the same CFO-compensated physical-preamble
channel estimator as the physical MRC baseline. Its reference in white
coordinates is `h_w = W h_physical`; its strength is `||h_w||²`, on the same
CFO-aligned FFT scale as payload decisions. This avoids the fractional-CFO
response of the previous uncorrected five-bin complex sum.

The old estimated uncertainty cone is conservatively recentered:
`theta_new = min(pi/2, theta_old + angle(h_old, h_w))`.
This triangle-inequality construction contains the old estimated cone; it
does not turn the empirical old cone into a calibrated statistical guarantee.

## Preamble-only range guards

First compute the existing noise-aware finite-candidate proposal. Enable its
nonzero weight only when all three checks pass:

1. `U < L`: the estimated reference cones admit separation. Direction overlap
   alone does not force large penalties, even when a normalized negative
   pair margin would numerically improve at a large weight.
2. The competing packet confidently dominates the target in estimated total
   strength. With `n = sigma_FFT² / N_preamble`, use the approximation
   `SE² = 4 n² + 2 n (S_u + S_v)` and require
   `S_v - S_u > Phi^-1(1-alpha/2) SE`, with the existing `alpha=0.05`.
   The variance comes from two independent two-channel complex Gaussian
   preamble-average estimates. Actual phase-aligned medians, common mixed
   observations, and structured interference do not satisfy that model
   exactly; this is an approximate confidence safeguard, not a rigorous
   hypothesis-test guarantee. No extra threshold was selected per cell.
3. The proposed joint pair/noise proxy margin is positive. This prevents
   accepting a merely less-negative surrogate as evidence of recovery.

If any check fails, choose zero once, before payload decoding. Positivity alone
is insufficient, which is why all three conditions are retained. These checks
can sacrifice some SP recoveries near the boundary; report those losses too.

## Physical MRC fallback in white coordinates

Setting lambda to zero on a whitened channel direction is generally not the
physical MRC baseline. With `y_w = W y`, use decision vector
`d = W^-H h_physical`, since `d^H y_w = h_physical^H y`.
Normalizing this decision vector changes all bin scores by one common scale.

`channel_sp` remains the whitened signal reference for geometry and uncertainty
statistics. `mrc_decision_channel_sp` separately records the zero-weight
combiner, used by both the production decoder and controlled replay. Cache
keys include the actual decision direction. Thus fallback can reproduce the
baseline at the supplied synchronization without mixing the two coordinates.
The existing bounded synchronization retries remain; lambda is fixed. During
these retries the zero-weight physical-MRC combiner is held fixed.

## Implementation and evaluation

- `sp_reference_guard.py`: configuration, guards, and coordinate mapping.
- `evaluate_sp_dechirp_real_pos.attach_sp_reliability_and_lambda`: explicit
  `reference_guard=True` plus physical input and its whitener. Historical
  helper defaults remain unchanged for reproducible archived experiments.
- `sp_node01_receiver.py`: current CLI default and cached payload decisions.
- `paper_experiments/replay_guarded_heatmaps.py`: fresh C1 replay; identical
  bounded A3 branch reuse is explicitly labeled and separately checked fresh.
- `analysis/validate_sp_reference_guard.py`: production equality checks on
  128 new-seed scenes and 16 freshly regenerated multiuser A3 scenes.

Original development grid: 512 scenes, SP 285 correct packets versus MRC 207;
no MRC-correct packet was lost. Previous SP delivered 271. New-seed development
check: 128 scenes, SP 70 versus MRC 52, previous SP 67, no MRC-correct packet
lost. These share the measured source bank and are not independent deployments.
They are empirical results, not a universal non-regression theorem. Some cells
lose SP-only recoveries compared with v1; see the per-cell records.

Versioned output: `real_usrp_outputs/revision_heatmaps_A3_C1_guard_v2`.
Original figures and reports are retained. Existing real-IQ Fig13/14/15 are
not overwritten, and their old v1 audit does not validate this v2 policy.
