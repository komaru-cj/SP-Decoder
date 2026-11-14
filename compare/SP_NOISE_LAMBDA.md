# Single-lambda noise-competition experiment

Current SP is `pair_and_noise_reference_guard_v2`, documented in
[`SP_REFERENCE_GUARD.md`](SP_REFERENCE_GUARD.md): one preamble-selected path,
aligned MRC reference/power, explicit guards, and coordinate-correct fallback.
The predecessor `pair_and_noise_two_packet_v1` combines noise competition, a two-track
gate and expanded finite candidates. `pair_only_legacy` is retained for historical
reproduction and ablation. The unrestricted policy described first below is
the earlier comparison variant, not the current main algorithm.

The experimental policy is `pair_and_noise_max_v1`, implemented in
[`sp_noise_competition.py`](../sp_noise_competition.py). It configures one weight
per packet from preamble statistics. Payload samples and CRC outcomes do not
select or retry lambda. The SP decision remains `|P|² − lambda |Q|²`.

**Validation status:** the first version improves several two-user, low-SIR
conditions but substantially regresses seven-user reception (79.46% to 62.95%
PDR on the frozen A set). It is not a validated replacement for the old
configuration. The user selected the two-track safeguard described below.
The implementation and regenerated results are kept identifiable as a separate
experimental revision; the frozen original results are preserved.

## Noise maximum

Assume that each empty FFT bin has independent orthogonal complex Gaussian
projections with variance `n = noise_sigma2`. Then, for `t >= 0`,

`Pr(|P|² − lambda |Q|² > t) = exp(-t/n)/(1+lambda)`.

A union bound over `B=M−1` bins gives the nonnegative threshold

`tau(lambda) = n max(0, log(B/alpha) − log(1+lambda))`.

The fixed default `alpha=0.05` is a per-symbol, all-empty-bin false-alarm budget
under this model; it is independent of the existing target-protection
`gamma=0.05`. It is not a packet error budget. The union bound does not require
independence between different bins. The exact single-bin tail requires white
Gaussian noise and independent P/Q within a bin; unmodeled collision components
do not inherit that guarantee.

With estimated target power `S` and reliability `L`, use

`mu = S L − lambda S(1−L) + n(1−lambda)`

`v = n² + 2n S L + lambda²[n² + 2n S(1−L)]`

`R_noise(lambda) = (mu − tau(lambda))/sqrt(v)`.

This standardized target margin is a structural surrogate. The noise threshold
has the stated model bound, but the target moment approximation and reference
uncertainty proxy do not supply an overall SER/PDR guarantee.

## Selection

Maximize `min(min_v R_pair_uv(lambda), R_noise(lambda))` over a finite set.
Keep the original pair-specific flip/stationary points, polarity midpoint,
endpoints and cap fractions. Add geometric checkpoints beginning at 1/16 and
pair/noise crossing points bracketed by those checkpoints. Break exact ties in
favor of smaller lambda. No online dense grid or CRC search is used.

The reference cap `(L−gamma)/(1−L)` remains. When enabled, the experimental policy removes
the extra constant cap of four; an explicit `--sp-lambda-max` still caps the
search. Isolated packets and insufficiently reliable references still select
zero. The historical direct helper `choose_lambda_sp(...,
noise_bin_count=None)` retains the old pair-only calculation so that old
mechanism analyses can be reproduced. Receiver attachment supplies `cfg.m−1`
when `noise_competition=True`.

The unrestricted comparison variant can be enabled explicitly with
`--sp-lambda-policy pair_and_noise_max_v1`; it is not the main policy.
`--sp-lambda-max` can impose an additional experimental cap. The frozen replay
script explicitly enables the new policy; it does not change production
defaults. Report reuse checks compare the requested and recorded policies to
prevent mixing old/new results.

## Reproduction and provenance

- `real_collision_experiment/analysis/evaluate_noise_lambda.py`: 272-scene
  two-user diagnostic; saves original P/Q spectra for audit.
- `real_collision_experiment/paper_experiments/replay_revision_abc_noise.py`:
  regenerates all frozen A/B/C/pilot waveforms, reconfigures and decodes SP,
  and preserves non-SP baseline results. C uses frozen anonymous candidates
  and calibration, never truth synchronization; production SP synchronization
  refinement still runs. Every source truth and every preamble channel and
  uncertainty estimate must reproduce. This is a controlled payload-policy
  comparison, not a new frontend acquisition experiment or fresh runtime
  benchmark.
- Outputs: `real_usrp_outputs/revision_abc_noise_lambda_prototype` and
  `real_usrp_outputs/revision_abc_noise_lambda_v1`; original output
  `real_usrp_outputs/revision_abc` is not overwritten.
- Tests check the modeled noise maximum by simulation, the finite candidate
  coverage against a dense diagnostic grid, a monotone pair-risk case, and
  receiver batch/isolated-target behavior.

Remaining issue: at high concurrency, the target bin can contain other users'
spectral components. The target-only-plus-thermal-noise model can therefore be
optimistic even after adding an explicit noise maximum. Increasing lambda can
penalize those valid mixed target bins. This limitation must be addressed before
claiming that the new selector improves reception generally.

## User-approved two-track gate

Enable `--sp-lambda-policy pair_and_noise_two_packet_v1` to use the noise-aware
selector only when exactly one detected competitor overlaps the target payload.
Other targets retain the legacy selector and a cap no greater than four. An
explicit global cap may reduce either branch further. The pair branch retains
the reference cap and chooses its actual weight from estimated powers,
direction uncertainty and noise; it does not use a constant large weight.
This was the v1 receiver default and initial heatmap policy. V2 keeps this
bounded multiuser branch and further guards isolated/single-competitor targets.

Count means the supplied anonymous overlap tracks, not transmitted truth K or
the total number of candidates elsewhere in a capture. Detection misses and
duplicate tracks can affect this decision. The gate does not infer hidden
users, nor does it add a new track deduplication rule.

`analysis/summarize_two_packet_gate.py` performs an exact cached branch
comparison: all 1536 current scenes have uniform per-target branch decisions,
so the corresponding previously decoded complete scene can be reused. Mixed
branch scenes fail closed and require fresh decoding. This reproduces A's
79.46% and ten-user density's 88.75% while retaining the pair-policy outcomes;
the cache assembly is not claimed as a new waveform/decoder run.

A more general dominant-interferer gate is a possible next step, not yet
implemented. Pair coefficients A/B and the flip scale -A/B quantify suppression
pressure, but the flip scale is a model-dependent demand estimate, not a safe
upper bound. Reference reliability, thermal noise and remaining multiuser
components still limit useful weights. A strict flip-feasibility veto can lose
successful packets in the current small-angle data and is not enabled.
