# Real-capture comparison decoders

PCube now defaults to the user-approved V3 policy
`accepted_cluster_soft_extension_v3`. The real receiver and standalone PCube
driver share `PaperComparisonContext.decode_pcube`. V3 preserves the historical
accepted-peak ranking and softly admits outside candidates supported by noisy,
packet-wide PDoA grouping. These clustering details are disclosed local choices
not specified by the original paper. The old fixed gate remains available only
through `grouping_policy='legacy_fixed_gate'` for explicit ablations.
See [PCube/FIDELITY_REVIEW.md](PCube/FIDELITY_REVIEW.md) for the historical audit
and [PCube/REPAIR_EXPERIMENT.md](PCube/REPAIR_EXPERIMENT.md) for all trial results.
The adopted V3 gains 15 packets without losses in 512 original C1 scenes;
128 new scenes gain one without losses. Isolated low-SNR controls improve in
aggregate with one individual loss, so there is no per-packet guarantee.

The real B210 receiver imports `compare/real_packet_decoders.py` and reports
the following six result rows for every experiment:

1. `lorawan` (standard single-channel LoRaWAN PHY receiver)
2. `mrc`
3. `mrc_cic` (MRC+CIC)
4. `pcube`
5. `maloragw`
6. `sp` (SP-Decoder)

The separate `compare/CoRa` runner now reports `mrc_cora` (MRC+CoRa).
Both enhanced baselines use fixed, unit-norm target MRC on the physical
receive channels. Weights come from the supplied physical preamble reference,
or the same physical-preamble estimator used by MRC. CIC RSSI and CoRa PMD
amplitude references are recomputed after combining. ICSS/SED and the full
CoRa posterior/TnB-BEC paths are retained. MRC work is included in timing.

The former `cic`/`cora` result rows are historical single-antenna results.
They must be recomputed before use in the revised paper. New result keys and
CoRa `*.mrc_cora.json` files prevent old cached numbers from being relabeled.
See [MRC_BASELINES.md](MRC_BASELINES.md) for validation and migration details.

`sp_core`, `sp_sync_refine`, `sp_repair`, `ch0`, and `ch1` are retained as
mechanism/ablation diagnostics; they are not additional Fig. 9/10 baselines.

## Evaluation boundary

The formal Fig. 9/10/12 receiver defaults to
`--comparison-frontend-scope common`. SP supplies the common candidate identity
and pre-payload fine start/CFO/STO. LoRaWAN, MRC, and CIC keep that
synchronization fixed. PCube and MaLoRaGW use it only as a seed for one bounded,
paper-native preamble/sync-word/SFD local start-CFO refinement (`0.125` symbol
matching tolerance); PCube operates on its physical Rx pair and MaLoRaGW on PCA
projection streams. The refinement never reads payload, FEC/CRC, manifest,
expected payload, SP lambda, or SP residuals, and falls back to the database
seed if no local estimate matches. Every method then runs its own parameter
estimation, payload combining/separation, peak selection, LoRa FEC, and CRC.
This remains a shared-detection conditional comparison, not an independent
end-to-end front-end comparison. Pass `--no-comparison-paper-local-refinement`
to reproduce the former fixed-sync PCube/MaLoRaGW boundary.

`--comparison-frontend-scope native` is retained as an end-to-end ablation:

- LoRaWAN sees physical Ch0 only.  It independently detects one dominant
  preamble track, confirms sync/SFD, estimates start/CFO/STO, and makes one
  top-1 dechirp-FFT decision per payload symbol.
- MRC independently detects and synchronizes one dominant preamble on the
  physical Rx pair, estimates its own two-channel vector, applies fixed MRC,
  and makes one top-1 decision per payload symbol.
- CIC independently finds consecutive SFD downchirps, confirms the preceding
  preamble/sync symbols, estimates timing/CFO, and then runs CIC demodulation.
- PCube independently searches the physical Rx streams for separated preamble
  tracks, performs preamble/SFD CFO-STO calibration, extracts PDoA, and runs
  PDoA clustering.  It does not receive SP spatial-residual proposals.
- MaLoRaGW independently performs PCA projection before weak-preamble search,
  estimates physical channels, applies ZF, and clusters payload peaks.  Its
  paper-native PCA strong/weak projections are used directly without an
  additional SP residual branch.

Their conditional PRR denominators are therefore method-native complete
detected targets.  Their TPS and payload goodput include native front-end
misses because the numerator is divided by the common business duration.
The method-specific candidates and front-end diagnostics are retained under
`native_comparison_candidates` and `decoder.native_frontends`.

The selected boundary is recorded in every report under
`decoder.comparison_frontend_scope`, `decoder.shared_sp_fine_sync`, and
`decoder.shared_sp_parameters`.

## Paper-to-code mapping and hardware limits

| Method | Implemented paper operations | Capture-specific limit |
|---|---|---|
| LoRaWAN | shared SP candidate and fine start/CFO/STO; physical-Ch0 fixed top-1 bins; standard LoRa FEC/CRC | single receive channel; no extra synchronization, estimation, collision separation, retry, or repair |
| MRC | shared SP fine start/CFO/STO; own physical-pair preamble channel estimate; fixed maximum-ratio combining; top-1 bins; standard LoRa FEC/CRC | two synchronized receive channels; no second synchronization, multi-user projection, retry, or repair |
| MRC+CIC | shared fine start/CFO/STO; fixed target MRC; combined-input preamble RSSI/fractional-frequency estimates; optimal ICSS spectral intersection (Eq. 12), RSSI filter, ten-window SED (Eqs. 15--17), standard FEC/CRC | two recorded channels combined into one; capture is 3x oversampled at BW250k, while the paper prototype reports 8x |
| PCube | shared SP fine sync seed; bounded physical-Rx preamble/SFD start-CFO refinement; own target-preamble PDoA estimate; `Z(f)=Z1(f)Z2*(f)` (Eq. 8); V3 local PDoA soft extension preserving accepted-peak ranking; standard FEC/CRC | the B210 recording supplies one synchronized Rx-pair; Eq. 9 multi-pair diversity gain cannot be evaluated; the paper leaves clustering details unspecified |
| MaLoRaGW | shared SP fine sync seed; bounded PCA-preamble/SFD start-CFO refinement; own preamble channel-matrix estimate; per-payload-window strongest `min(K,M)` selection, ZF `(H^H H)^-1 H^H`, target-ZF energy plus frequency/time/channel-ratio peak clustering, standard FEC/CRC | two receive antennas, uplink only; downlink calibration/beamforming is outside a receive-IQ experiment |

LoRaWAN, MRC, PCube, and MaLoRaGW operate on DC-removed physical antenna
streams.  They must
not use the spatially whitened streams because non-diagonal whitening rotates
physical channel features. Only SP uses the noise-whitened streams for its
spatial filter. In formal shared mode, SP supplies candidate identity and a
pre-payload fine start/CFO/STO seed. PCube and MaLoRaGW then perform the bounded
paper-native preamble/SFD refinement documented above; no other baseline runs a
second synchronization stage. LoRaWAN directly demodulates Ch0; MRC and CIC
estimate only the receiver-specific parameters needed for their combining/separation
rules. In the optional native ablation, the RF-energy busy intervals
only bound computation and supply no packet timing or identity.

The SP-specific bounded integer start--CFO ambiguity branch and its CRC-aided
acceptance are isolated from all baselines. The only baseline local refinement
in formal shared mode is the pre-payload, paper-native PCube/MaLoRaGW procedure
described above.

The older `evaluate_*.py` programs remain synthetic-scene research drivers.
They use symbol-error thresholds and are not the source of formal real-capture
PRR.  Formal experiment results come only from `sp_node01_receiver.py` schema
`node01_sp_receiver_report_v6`.
