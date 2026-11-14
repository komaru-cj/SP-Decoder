# Proposal: collision limits, spatial separability, and per-node fairness

Status: proposed design for discussion; no new captures or batch runs authorized by this document.

## Diagnosis from current A3 results

The current arrival-density sweep uses rho=(K-1)T_sym/W. At K=10,
rho=10/3,5,10,20 gives W/T_sym=2.7,1.8,0.9,0.45. With 38 payload
symbols, the common payload intersection already covers about 93%,95%,98%,99%
of a payload. This is a narrow sweep near full overlap, not sparse collisions.
Increasing rho further may change fractional-symbol interference and reference
mixing but does not substantially increase payload occupancy.

Lambda is a receiver configuration, not a recoverability measure. Endpoint
solutions can arise from a monotonic surrogate or a fixed search bound. Cap 40
delivers 920/1792 versus cap 4's 1065/1792 on paired current A3 scenes; simply
enlarging the range does not establish a better isolation boundary. Current
lambda illustrations intentionally select repeat 11 for fewer capped values;
they cannot establish population performance or reliability.

## Common measurements and definitions

Use the complex projective channel angle:
delta(u,v)=acos(|h_u^H h_v|/(||h_u|| ||h_v||)). This is not geographic bearing.
Use independent isolated calibration channels for offline geometry labels;
keep physical versus whitened coordinates explicit and consistent within a plot.
Never feed calibration truth into the production reference estimator.

Record both deployment minimum angle (all other deployed nodes) and active
minimum angle (only nodes actually overlapping the target). Only the latter
directly labels an individual collision. During changing channels, measure
calibration before/after each session and retain temporal variability.

Record total active packets including target, target-relative average and peak
concurrency over payload, overlap fraction, target SNR, individual and aggregate
SIR, start/CFO, channel uncertainty, lambda, lambda cap, guard branch, acquisition
status, CRC/payload correctness, and node ID. Registered node count is not
simultaneous collision order.

Fix the production selector before evaluation; keep cap 40 as an ablation.
Use SP, MRC, PCube, and MaLoRaGW on identical observations and PHY. Separate
controlled-synchronization conditional decoding from blind end-to-end results.

## Experiment A: controlled limits

Temporal sweep: hold K=6 or 8, paired sources, powers, CFO, and relative start
pattern fixed. Scale W/T_payload across .01,.05,.25,.5,1,2, with sample-rounded
offsets and measured payload occupancy. Repeat for measured small/medium/large
active minimum-angle cohorts. Change only timing within a paired temporal sweep.
Plot PDR against measured average concurrency or normalized start span, using
separate facets for geometry. Report actual rho as a secondary coordinate if useful.

Spatial/concurrency sweep: target K=2,4,6,8,10 and active minimum-angle bins
0-2,2-5,5-10,10-20,20-40,40-90 degrees, subject to available distinct measured
channels. Leave unsupported cells empty; do not rotate measured channels or
reuse one physical position as several independent nodes. Fix a high-overlap
timing regime and a single calibrated per-node power policy. Report aggregate
SIR because equal individual power implies rising total interference with K.
An additional fixed-aggregate-interference control can distinguish these effects.

Choose a mechanism SNR using isolated-link calibration (e.g. isolated PDR>=99%),
and retain current 0 dB as a stress condition. Do not tune SNR or geometry per cell
to manufacture a contour. Start with 30 independent bursts/cell; collect 100-200
or more around a transition, using an outcome-independent prespecified sampling
rule and adequate distinct measured channel groups. Report uncertainty clustered
by independent burst/channel session rather than treating correlated targets as
independent trials.

Primary figure: four aligned K-by-active-angle PDR heatmaps, one per method,
with a common 0-1 scale and a prespecified PDR=0.9 empirical contour wherever
supported. Add a compact temporal PDR curve figure. A contour is conditional on
SNR, SIR, timing, PHY, and reference policy; do not claim a universal capacity.
If no cell reaches the threshold, report that fact. For a stronger reliability
claim, require a one-sided confidence lower bound >=0.9 rather than just the mean.

## Experiment B: deployment fairness

For each actual deployment, keep all nodes fixed and sweep offered airtime load
G=sum_i r_i*T_frame across low/medium/high settings, initially .25,.5,1,2,4 as a
pilot. Choose final load levels from an independent pilot, then freeze them.
Measure realized collision order; do not equate G or N with simultaneous K.
Use at least 200 scheduled transmissions/node/condition as a starting point,
repeat independent sessions, include zero-success nodes, and report uncertainty.

For each method, node PDR is correct packets/scheduled transmissions, including
acquisition failures. The node CDF has one equally weighted value/node; the
sample count is N nodes, not the number of transmitted packets. Include a
low-load single-node reference measurement to identify intrinsically weak links.

Fairness figure: (a) per-node PDR ECDFs for the four methods at a fixed high load,
with additional loads as facets or appendix; (b) absolute per-node PDR versus
deployment minimum projective angle, using the same node identities for every
method and indicating link SNR. An inset/companion plot of SP-minus-MRC PDR
versus angle exposes harmed nodes (below zero). Report lower-tail PDR and the
fraction of nodes worse than each baseline, not only aggregate gain.

Use active minimum angles and measured concurrency from the same deployment
as a bridge to Experiment A. A node-level angle correlation alone does not
establish a causal or universal collision boundary.

The existing replay pool has 22 retained source packets from only 10 positions.
It cannot supply a genuine 24-node CDF or independent 24-node spatial geometry.
Those claims require identifiable deployment data from 24 actual nodes.

## Optional lambda mechanism figure

Use an offline diagnostic lambda sweep on a fixed, prespecified target/channel
group across collision severity. Plot lambda on x, K or active minimum angle on
y, and empirical PDR at each fixed lambda as color. Overlay the production
selector's chosen-lambda distribution and the per-packet reliability bounds.
Show which lambda regions meet the declared PDR threshold and how they disappear.
Such regions may be disconnected; do not force a single usable interval.

Payload truth is allowed only for this labeled offline diagnostic, never for
production lambda selection. Compare the actual selector's PDR with the best
fixed-lambda diagnostic to distinguish tuning failure from absence of a useful
weight. For stronger per-observation evidence, intersect A+lambda*B>0 over
all competitor bins and symbols: a nonempty intersection is sufficient for
error-free top-1 recovery on those fixed observations. Its being empty does
not imply packet failure, since FEC can correct symbol errors.

Recommended presentation: shared story and channel calibration, separate evidence
for controlled collision limits and deployment fairness. Move selected-repeat
lambda-value maps to the appendix; use outcome-based figures for the main claims.
