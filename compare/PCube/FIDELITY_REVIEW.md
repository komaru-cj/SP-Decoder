# PCube reproduction fidelity review

Historical audit of the pre-V3 implementation. The user subsequently approved
`accepted_cluster_soft_extension_v3` as the formal default; see
`REPAIR_EXPERIMENT.md`. The old gate discussed below is retained only as an
explicit ablation. This audit and its measurements are preserved as evidence.

Reviewed against the local primary paper `compare/PCube/PCube.pdf`, especially
Sections 4.2–4.6 and 5.3. This review does not change receiver behavior, job
results, source selection, or published figures.

## Finding

The current heatmap decoder is a local two-receiver approximation with a
demonstrated decision-rule artifact. Its anomalous cells should not yet be
interpreted as performance properties of the original PCube system.

### Correct core operation

`compare/real_packet_decoders.py:751` implements Eq. (8),
`Z = FFT_Rx1 * conj(FFT_Rx2)`, with the matching preamble phase convention.
Both channels use the same target timing/CFO compensation and physical antenna
coordinates. The heatmap runner supplies controlled start/CFO to every receiver;
it estimates PCube's PDoA from noisy overlapping physical preambles, not truth
channels or decoded payloads. It does not feed SP's whitened signal or lambda
into PCube. A direct common-phase cancellation numerical check gives maximum
phase residual below 4e-16 rad.

This cancellation applies to a common transmitted symbol phase. It does not
eliminate inter-user cross terms when signals overlap in one FFT bin, or
independent receiver noise.

### Confirmed local decision-rule defect

At `compare/real_packet_decoders.py:763`, the decoder accepts only candidate
phases within **0.5 rad** of the target preamble PDoA. It maximizes rotated real
cross-product evidence in that set; if the set is empty, it instead minimizes
phase distance over all candidates. A newly admitted unrelated peak can change
the branch and prevent selection of a stronger true peak outside the gate.

Section 4.5 describes grouping demodulated symbols in the I-Q plane and matching
a cluster to the separated target preamble. The paper does not specify the
current 0.5-rad gate, the current empty-set fallback, or the exact statistical
clustering algorithm. The implementation processes each window independently;
it does not form a packet-spanning PDoA cluster as illustrated by the paper.
Thus the concrete local rule is an undocumented approximation, not a recovered
author-specified algorithm.

The comment at lines 758–762 additionally overstates Eq. (9): that equation
defines weighted **complex rotation and summation across receive pairs**, after
which the paper applies Section 4.5's PDoA grouping. It does not define a
maximum-positive-real-bin detector. For one pair, rotation changes phase but
provides no multi-pair interference reduction. The paper explicitly calls its
two-Rx method Section 4.5 decoding without pair combining.

### Same-waveform evidence

The native-IQ `2–5 degree / SIR=10 / SNR=-10` cell contains five failures, all
targeting source 5. Each has one wrong payload symbol. Every true peak is in
the detected candidate set, has the greatest total antenna energy, and has
greater rotated real evidence than the selected wrong peak. True-peak phase
distances are 0.518, 0.502, 0.603, 0.507, and 0.511 rad. The local hard gate
excludes all five.

For SNR=-20, repeat 2, payload symbol 12, the true peak is selected at SIR=-20
with phase distance 0.575 rad, but rejected at SIR=0/+10 with smaller distance
0.530/0.531 rad, despite being the strongest energy peak. The candidate set
changes which gate/fallback branch runs. Across that SNR row the measured SER
improves as SIR rises (29.11%, 22.86%, 12.99%, 6.58%) while PDR is 2/16,0/16,
0/16,0/16. Remaining error positions and FEC protection also affect CRC success.

These traces are in `real_usrp_outputs/revision_heatmaps_native_iq/`:
`pcube_angle_diagnostic.json`, `pcube_peak_diagnostic.json`, and
`pcube_nonmonotonic_diagnostic.json`. Frame-incomplete source 8 is excluded.

### Candidate extraction also needs an explicit reproduction contract

The shared peak helper imposes local maxima, energy >=6 times median energy,
energy >=1% of the strongest peak, and a maximum of 64 candidates. These are
local choices, not recovered PCube parameters. The strongest-peak-relative
cutoff can remove weak users in strong near-far conditions. The five failures
above are downstream grouping failures, so this cutoff does not explain those
specific errors. Changing it requires separate candidate-recall evidence.

### Two divergent repository implementations

The active heatmap path is `PaperComparisonContext.decode_pcube`. The older
`compare/PCube/evaluate_pcube.py` has no 0.5-rad gate and uses strongest rotated
positive real evidence directly; it also has different candidate extraction
and preamble/SFD averaging. Running that script is therefore not a reproduction
of the heatmap decoder. Neither selection rule is fully specified by the
paper's Eq. (9). A production correction should unify these paths or clearly
retire the legacy path.

### Evaluation limits that are not implementation bugs

Only two recorded antennas are available, so there is one Rx pair. The paper's
eight-antenna diversity, and its reported two-Rx comparison selecting the best
pair from the eight-antenna recordings, cannot be reproduced with these IQs.
The native data uses SF10/BW125k/CR4/5/32B implicit/no LDRO. The paper defaults
to SF10/BW250k/CR4/8 and reports LDR operation. All current methods fairly use
the same native PHY, but these experiments are not numerical replications of
the paper's published PRR.

The horizontal angle is the projective angle between full complex channel
vectors; PCube specifically observes inter-antenna phase difference. Amplitude
ratios can change the former without the same change in PDoA. In addition,
the first two bins each contain one distinct source pair and only 16 trials
per cell. These facts preclude demanding strictly ordered angle-bin PDR.

## Correction boundary

Do not fix this by choosing a phase threshold that makes the plotted PDR
monotonic. First specify a consistent phase grouping/matching rule grounded in
Section 4.5, including candidate extraction, phase uncertainty, and empty or
ambiguous groups. The paper leaves these implementation details unspecified;
agree on the local reproduction contract before changing production code.
No truth channels, payload labels, CRC-driven threshold search, or hidden MRC
protection branch should be introduced to recover baseline results.

The new isolated-IQ diagnostic driver is
`real_collision_experiment/analysis/audit_pcube_fidelity.py`. Its ungated
rotated-real and nearest-phase rules are explicitly diagnostic ablations,
not approved replacements for PCube. Results are written separately as
`pcube_fidelity_controls.json`, preserving the current heatmaps.

## Completed isolated controls

550 cases use the same 22 frame-complete source packets: 22 unmodified-source
controls and eight fixed-seed noise realizations per source at each SNR. Added
noise respects the measured embedded source-noise covariance. All methods see
the identical IQ and estimated physical preamble; success requires both CRC
and exact expected payload, with labels used only for scoring.

| Input | Current PCube | Fixed MRC | Diagnostic ungated rotated real | Diagnostic nearest phase |
|---|---:|---:|---:|---:|
| Original source IQ | 22/22 | 22/22 | 22/22 | 22/22 |
| SNR=-20 | 38/176 | 91/176 | 56/176 | 13/176 |
| SNR=-10 | 173/176 | 176/176 | 175/176 | 101/176 |
| SNR=0 | 176/176 | 176/176 | 176/176 | 134/176 |

At -20 dB, 56 cases succeed under MRC but fail under current PCube (three cases
go the other way). There are 131 wrong symbols whose true detected peak is
outside the local phase gate, spread across 89 cases. At -10 dB, two of the
three failed packets reject the strongest true peak at distances 0.530 and
0.511 rad. The third failure has another cause. Thus gate rejection is real,
but does not explain the entire gap.

The ungated rule recovers some packets but remains worse than MRC in isolated
low-SNR operation. Cross-products include signal-noise and noise-noise terms;
single-pair product detection is not equivalent to coherent MRC. However,
these ablations do not establish the performance of a faithful packet-level
PCube clustering implementation. The nearest-phase rule can select noise or
leakage candidates with accidentally close phase, even at SNR=0. Neither rule
is an adequate automatic replacement solely on these tests.

Results: `real_usrp_outputs/revision_heatmaps_native_iq/pcube_fidelity_controls.json`
and `pcube_fidelity_control_rows.json`. The receiver hash is recorded in the
former. The 13 existing standard-decoder/native-front-end tests pass; they
validate current code behavior, not paper fidelity. The existing gate test
explicitly encodes the local gate choice, so its passing cannot validate that
choice against the paper.
