# PCube grouping repair and adoption

The user has approved V3 (`accepted_cluster_soft_extension_v3`) as the formal
default and requested the C1 heatmaps be updated. Both receiver and standalone
driver now use it. `legacy_fixed_gate` is an explicit ablation; V1 and V2 remain
experimental. The sections below document development before this approval.

The primary paper specifies PDoA grouping and matching but does not give its
clustering algorithm. This is a transparent local implementation of those
missing details, not the authors' code or a claim of exact reproduction.

## Frozen first proposal

1. Retain the existing physical FFTs and candidate extraction. No front-end,
   source selection, packet PHY, peak threshold, or FEC change is combined with
   this grouping experiment.
2. Compute Eq.8 complex products and their circular phases. From each antenna's
   median FFT power, estimate noise power as median/log(2). Approximate each
   peak's phase variance from signal-noise and noise-noise terms of the product.
3. Keep each detected overlapping packet's calibrated preamble PDoA as its
   identity anchor. Use estimated preamble channel powers as mixture priors.
   Add a uniform phase noise group with fixed prior 0.05. Reference uncertainty
   scales with the available preamble length.
4. Pool evidence over all payload windows to estimate each phase group's excess
   scatter. Use amplitude weights normalized within each window and preamble-
   length shrinkage toward zero excess scatter. Perform at most 12 updates,
   stopping if the variance change is below 1e-6 rad^2. There is no gate at
   0.5 rad and no empty-cluster decision switch.
5. In each window, select the candidate maximizing product magnitude times its
   posterior target-group membership. The same rule handles ambiguous groups.

The variance approximation, power priors, uniform group, shrinkage and soft
decision are local engineering choices, beyond what the original paper spells
out. In particular, this proposal uses noisy physical measurements and the
entire packet's unlabeled phase observations, but never truth channels,
expected symbols, CRC-guided alternatives, SP lambda, or MRC protection.

## Evaluation contract

The first proposal is frozen before examining its aggregate results. Evaluate:

- The previous 550 isolated measured-IQ controls, with exact same noise seeds.
- All 512 original native-IQ C1 scenes. Reconstruct the same source selection,
  phases and noise, assert original truth metadata equality, and assert every
  legacy metric equals its frozen report.
- 128 additional C1 scenes with seeds offset by 161803399, fixed before their
  results are examined. Source eligibility, PHY, cells and scoring stay equal.
- Report gained and lost packets as well as aggregate PDR/SER; never choose
  decoder policies separately per cell or according to ground truth/CRC.

Outputs are separate from formal figures:
`real_usrp_outputs/revision_heatmaps_native_iq/pcube_repair_v1/` and
`pcube_repair_controls.json` alongside the original control report.
Hashes of the implementation and evaluator are recorded in the run manifest.
The opt-in result requires review before formal baseline adoption.

## Follow-up proposals

V1 completed all original scenes and 128 new scenes. It improves the original
SNR/SIR total 95→105 and angle/SIR total 83→111, but loses six previously
successful original packets, including three at 0–2 degrees/SIR=0. Its first
new-seed SNR/SIR total decreases 27→26. Do not adopt solely on total gain.

V2 (`target_noise_soft_pdoa_v2`) removes competition with other packet phase
groups and retains rotated-real evidence multiplied by target/noise membership.
It shares V1's fixed noise prior and packet-scatter estimator. It improves the
original totals 95→100 and 83→87, but its separate new-seed SNR/SIR test
decreases 27→23. This does not meet the desired conservative repair behavior.
Its new seeds use offset 141421357; V1 uses 161803399. These tests must each be
compared against their paired legacy result, not directly against each other.

V3 (`accepted_cluster_soft_extension_v3`) is a smaller change. It preserves the
legacy rotated-real ranking for every candidate inside the old accepted
0.5-rad region. Previously excluded candidates can compete using rotated-real
evidence multiplied by V1 target-group membership. There is one spectrum
decision and no CRC-based choice between decoder outputs. If all positive
evidence vanishes, choose the nearest circular phase. This reduces false
rejection but intentionally retains a plateau for already accepted peaks;
it does not claim to eliminate every boundary discontinuity or implement the
authors' unspecified clustering exactly. Fixed new-seed offset: 173205081.

During development all versions were opt-in. Separate `pcube_repair_v1/v2/v3` folders keep
paired original and new-seed results. V1 and V2 code snapshots were archived
before subsequent edits. No version is selected separately per cell.

V3 completed 640 C1 scenes with zero old-success losses and zero cells with
PDR regression. Its original totals are 95→105 and 83→88; new-seed totals are
24→24 and 19→20. Isolated SNR=-20 controls improve 38→56/176, with 19 gains
and one individual loss; there is no universal individual-packet guarantee.
V3 was recommended for review and has now been approved as the formal default.
The prior default and figures are archived in `backup_pcube_legacy_before_v3_20261030`.
Full trial evidence and comparison plots:
`real_usrp_outputs/revision_heatmaps_native_iq/pcube_repair_v3/RESULTS.md`.
