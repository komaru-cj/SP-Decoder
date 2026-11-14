# A/B/C data and synthesis readiness

Updated 2026-10-28. This is a resubmission, not a point-by-point rebuttal.
The user permits synthetic collision samples when suitable simultaneous-air
captures are unavailable. New external collection is primarily D.

## Available data

- `real_usrp_outputs/clean_pos_packets.npz`: 26 complete dual-channel packets
  from 10 measured positions. SF10, BW125 kHz, 1 Msps, CR4/5, eight preamble
  chirps, sync word 0x12, implicit header, 32-byte payload. Source metadata
  includes original start, CFO, signal/noise levels, and position.
- `real_usrp_outputs/pos01.npz` through `pos10.npz` and `raw/pos*_ch*.c64`:
  original continuous records, available for re-extraction with pre-packet
  noise. The saved packet bank starts at its estimated frame edge.
- `real_collision_experiment/runs`, `runs_outdoor`, `runs_outdoor1`: physical
  dual-channel captures plus capture metadata and manifests; existing formal
  anonymous fine-sync databases and decoder reports are also available.

## A: controlled mechanism evidence

Use measured directions/CFO from seven distinct positions to generate complete
explicit-header frames in a controlled mixture. New source symbol bins come
from the validated encoder and are used only for offline scoring. Show
support, weighted orthogonal penalty, signed score and rank changes on a
common linear scale, with aggregate rescue/harm over all qualifying windows.
The finished batch has 32 scenes and 224 generated frames. No additional
simultaneous-air capture is required under the user's confirmed scope.

## B: low SNR, small channel angles, collision density

Existing measured directions cover small angles. Clean full-packet reference
angles give 19 cross-position packet pairs below 10 degrees: one at 0–2,
seven at 2–5, eleven at 5–10. Minimum is 1.939 degrees (`pos02#1`, `pos04#1`).
Those pairs come from four position combinations and are not 19 independent
deployments. Same-position repetitions additionally provide near-collinear
stress cases. Detailed preamble and full-frame estimates are saved in
`single_packet_angle_audit/summary.json` and `packet_pairs.csv`.

The measured pool supports starting the controlled experiments without more
collection. Injected noise must account for source-recording noise after
scaling and summation. Add MRC, MRC+CIC, MRC+CoRa, PCube and MaLoRaGW as
appropriate, using the same scenes and front-end scope. Preserve lambda,
protection cap, rescue/harm, and failure-stage records.

## C: overlapping-preamble reception

Compose complete frames with starts randomized within W/Tsym =
0, 0.1, 0.25, 0.5, 1, 2 for K = 2, 4, 6. Use the full detector, track
establishment, reference estimator and decoder. Known timing/channel/symbol
truth is reserved for scoring. Report track establishment, conditional
direction error with coverage, and end-to-end PDR over all source frames.
The plan specifies one reliable-reference SNR and one near-threshold SNR;
their final values should follow a collision-free reception pilot.

## Confirmed implementation: option 2

The user selected measured channel/CFO plus newly generated explicit-header
waveforms. No implicit-header PHY adaptation is needed. The run configuration
is SF10, BW125 kHz, 750 ksample/s, CR4/5, eight preamble chirps, sync 0x34,
20-byte payload, explicit header and CRC. Channel directions come from the
clean full-packet reference cache; CFO values come from the recorded-source
preamble estimates. Both source IDs and values are saved for every scene.

Generated waveforms contain no original-recording noise. Independent complex
AWGN is added once to each receive channel, with variance tied to a unit
per-packet average receive power. Density scans keep per-packet power fixed;
total interference therefore rises with K. Paired SNR/SIR cells reuse source,
payload and noise seeds. The code does not claim 26 independent deployed
nodes or independent source captures for each Monte Carlo repetition.

A/B use controlled exact start/CFO and estimate spatial references/lambda
from their overlapping noisy preambles. C receives only the mixture and runs
the production anonymous detector/SFD supplement. C additionally uses the
production bounded SP synchronization refinement. PDR in C counts unique
exact CRC-valid source payloads over all generated transmitted frames.
User-confirmed offline scoring uses timing/CFO gates (including coupled CSS
start/CFO aliases) and true reconstructed channels to label candidate identities.
Receiver structural confidence selects among aliases of one identity. This
truth-assisted pairing is disclosed with the direction-error statistics; the
receiver input and CRC-based end-to-end PDR remain unchanged. Raw job files
retain the original timing/CFO-only diagnostic; final CSVs use the approved
channel-assisted pairing.

Driver: `paper_experiments/run_revision_abc.py`.
Renderer: `paper_experiments/render_revision_abc.py`.
Outputs: `real_usrp_outputs/revision_abc/`, with separate manifests,
reproducible per-scene JSON, per-target statistics, and PNG/PDF/SVG figures.
The current batch uses 32 A scenes, 16 repeats per B condition, 8 repeats per
C condition, and a 16-repeat collision-free SNR pilot. C uses -20 and 0 dB;
the pilot places the onset of packet degradation near -20 dB.

## Completion

The complete manifests contain 1536 scenes and 4320 generated transmitted
frames. Final plots, 502 metric rows, 113 condition diagnostics, and 3552
scored target rows are under `real_usrp_outputs/revision_abc/figures/`.
Batch checks verify source identities, 33-symbol/20-byte profiles, injected
noise variance, lambda bounds, CRC-result invariance under offline re-pairing,
and all-transmitted-frame C denominators. See `batch_validation.json` and
`figure_manifest.json` for completion and provenance.
