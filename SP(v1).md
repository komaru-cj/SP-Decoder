# SP: Reliability-Constrained Signed Spatial Decoding for Concurrent LoRa Reception

## Abstract

LoRa enables low-power, long-range connectivity for large-scale IoT deployments, but its ALOHA-like access model makes packet collisions inevitable as node density grows. Existing collision-recovery receivers exploit time offsets, frequency offsets, power diversity, or multi-antenna phase features to separate colliding packets. These techniques have significantly improved LoRa concurrency, yet they leave a fundamental decision-stage limitation: after a target packet has been detected, synchronized, and assigned a channel estimate, the final LoRa FFT decision is still often made by a non-negative energy score. A strong interferer can therefore win the target's FFT top-1 decision even when its spatial direction is inconsistent with the target.

This paper presents SP, a two-antenna LoRa receiver that converts the final symbol decision from positive-only combining into a target-conditioned signed spatial test. For each detected packet, SP projects every dechirped FFT bin onto the target channel direction to obtain support evidence and onto the orthogonal spatial direction to obtain contradiction evidence. It then forms a signed spectrum

$$
D_{u,\ell}[k]=|P_{u,\ell}[k]|^2-\lambda_u |Q_{u,\ell}[k]|^2,
$$

where the packet-level weight $\lambda_u$ is selected by a reliability-constrained risk objective rather than by a fixed heuristic. The receiver accounts for channel uncertainty, noise, and multiple detected interferers by bounding the target's reliable polarity interval and evaluating only a finite set of theoretically meaningful candidate weights. The resulting decoder is non-iterative, does not reconstruct interferer waveforms, and remains compatible with COTS LoRa transmitters.

We implement SP on a dual-channel USRP B210 receiver with fifteen SX1276/STM32 LoRa nodes. The implementation separates packet detection from conditional packet reception ratio, uses standard LoRa FEC and PHY CRC as the packet success criterion, and compares SP against MRC, CIC, PCube, and MaLoRaGW on common complete detected targets. Our evaluation methodology combines measured-waveform collision synthesis, standards-compliant PHY simulation, and real-air experiments. This evidence chain isolates the positive-only decision failure, tests the risk-constrained weight independently of the front end, and measures the complete receiver under realistic concurrent traffic.

## 1. Introduction

Low-power wide-area networks have become a common substrate for sensing and control applications that require kilometer-scale coverage and multi-year battery lifetime. LoRa is one of the most widely deployed LPWAN physical layers because chirp spread spectrum modulation enables robust packet reception at low signal-to-noise ratios and with inexpensive transceivers. A LoRa gateway, however, often covers a large population of independently transmitting nodes. When multiple nodes transmit on the same carrier frequency, bandwidth, spreading factor, and coding rate, their packets collide at the gateway. Standard LoRa receivers largely rely on capture; packets that are not captured must be retransmitted, reducing network throughput and increasing device energy cost.

A substantial body of work has shown that LoRa collisions are not necessarily destructive. Time-domain receivers exploit packet start offsets and symbol-edge discontinuities. Frequency-domain receivers use carrier-frequency offsets or peak trajectories. Power-domain receivers group peaks by received amplitude. Multi-antenna receivers add spatial diversity by using phase differences, channel ratios, or MIMO projections. CIC, PCube, and MaLoRaGW represent three important directions in this literature: CIC cancels interferers through carefully selected sub-symbol spectral intersections \cite{cic_sigcomm21}; PCube clusters colliding symbols in a phase domain created by multiple receiving antennas \cite{pcube_mobicom21}; MaLoRaGW uses spatial projection and channel estimation to support multi-user MIMO LoRa reception \cite{maloragw_sensys22}.

These systems motivate a natural question: once a receiver has already found a complete target packet and estimated its timing, CFO, and channel, what is the best way to decide each LoRa FFT bin? In a two-antenna receiver, maximum-ratio combining projects the dechirped FFT vector onto the target channel direction and ranks bins by the resulting non-negative energy. This is optimal for improving SNR in a single-user Gaussian setting, but collisions create a different decision problem. A bin caused by another packet can still have a large projection onto the target direction. MRC can only attenuate this projection; it cannot use the fact that the same bin may also contain strong energy in a direction orthogonal to the target.

The central observation of SP is that this orthogonal energy is not merely residual noise. For a correctly synchronized target symbol, the target bin should be spatially consistent with the target channel and therefore weak in the target-orthogonal direction. A competing bin produced by a different packet may appear strong along the target direction but will often leave a stronger target-orthogonal component. That component is evidence against assigning the bin to the target packet. SP explicitly preserves this negative evidence and incorporates it into LoRa symbol ranking.

Turning this observation into a receiver is not as simple as subtracting the orthogonal spectrum with a fixed coefficient. If the target channel is estimated with error, true target energy leaks into the orthogonal branch and can be incorrectly penalized. If the coefficient is too small, SP degenerates to MRC and fails under near-far collisions. If the coefficient is too large, SP amplifies noise and over-subtracts bins that are actually reliable. With more than one interferer, the worst pairwise leakage condition can dominate the target decision, and no single fixed value works across channel coherence, SIR, and SNR.

SP addresses these issues with a reliability-constrained signed spatial decoder. It estimates a confidence interval for each packet's channel direction, converts this interval into conservative lower and upper bounds on target and interferer spatial polarity, and chooses one packet-level $\lambda_u$ by maximizing a worst-pair normalized decision margin within a risk-bounded interval. The receiver then performs a direct signed top-1 decision for every payload symbol and passes the resulting symbols through standard LoRa FEC and PHY CRC. A bounded start/CFO refinement is applied only when SP-core fails CRC; it is part of the final system but not a source of unbounded oracle search.

This paper makes four contributions.

First, it identifies the positive-only decision bottleneck in dual-antenna LoRa collision decoding. Using real SX127x waveforms and trace-driven collisions, we show that MRC errors often occur because the wrong bin retains enough target-direction energy while also exposing strong target-orthogonal contradiction.

Second, it introduces signed projective decoding for LoRa. The decoder constructs target-conditioned support and contradiction spectra and ranks bins by a signed spatial score. Unlike successive interference cancellation, it does not require decoding an interferer first, reconstructing its waveform, or subtracting packets in a power order.

Third, it develops a packet-level reliability and risk mechanism for selecting $\lambda_u$. The implementation considers channel uncertainty, noise, and arbitrary detected interferers, evaluates interval boundaries, pair-specific flip/peak points, and a few fixed checkpoints, and restricts the search to a bounded interval that prevents unreliable over-subtraction.

Fourth, it implements and evaluates SP on a real two-antenna LoRa receiver. The evaluation separates packet detection rate from conditional PRR, uses FEC/PHY-CRC-closed payload equality as the success criterion, and compares SP+sync-refine with MRC, CIC, PCube, and MaLoRaGW on the same complete detected packet targets.

## 2. Background and Motivation

### 2.1 LoRa FFT Demodulation

For a LoRa spreading factor $\mathrm{SF}$, each symbol encodes one of

$$
M=2^{\mathrm{SF}}
$$

possible cyclic chirp shifts. With bandwidth $\mathrm{BW}$ and oversampling factor $L$, one symbol contains $N=LM$ complex samples. A standard receiver multiplies the received upchirp by a downchirp and performs an $M$-point LoRa FFT on the appropriate polyphase branch. In the absence of collision, the symbol maps to a dominant FFT bin:

$$
\hat{s}=\arg\max_{0\le k<M} |Z[k]|^2.
$$

Collisions change the spectrum from one dominant tone to a set of competing tones. A receiver must then determine which peak belongs to the target packet being decoded.

### 2.2 Two-Antenna Collision Model

Consider $U$ LoRa packets overlapping at a two-antenna gateway. Let $\mathbf{h}_v\in\mathbb{C}^{2}$ denote the effective channel of packet $v$. After aligning the receiver to target packet $u$, compensating its CFO, dechirping one payload symbol $\ell$, and taking the LoRa FFT on both antennas, the vector observation at bin $k$ can be written as

$$
\mathbf{Y}_{u,\ell}[k]
=
\sum_{v=1}^{U}\mathbf{h}_v A_{uv,\ell}[k]
+\mathbf{N}_{u,\ell}[k],
$$

where $A_{uv,\ell}[k]$ is the scalar FFT response of packet $v$ in the target-aligned window. For the target packet, most energy should concentrate at $k=s_{u,\ell}$ when synchronization is accurate. For interferers, the response depends on their relative timing, CFO, symbols, and channel.

Let the normalized target channel direction be

$$
\mathbf{a}_u=\frac{\mathbf{h}_u}{\|\mathbf{h}_u\|}.
$$

In two dimensions, a unit vector orthogonal to $\mathbf{a}_u$ is

$$
\mathbf{b}_u=
\begin{bmatrix}
-a_{u,2}^*\\
a_{u,1}^*
\end{bmatrix}.
$$

The normalized squared coherence between target $u$ and interferer $v$ is

$$
\rho_{uv}=
\frac{|\mathbf{h}_u^H\mathbf{h}_v|^2}
{\|\mathbf{h}_u\|^2\|\mathbf{h}_v\|^2}.
$$

High $\rho_{uv}$ means that the two packets are difficult to separate spatially with two antennas; low $\rho_{uv}$ means that the target-orthogonal direction can provide useful contradiction.

### 2.3 Why Positive-Only Combining Fails

MRC ranks each bin by

$$
M_{u,\ell}[k]=|\mathbf{a}_u^H\mathbf{Y}_{u,\ell}[k]|^2.
$$

Suppose the correct target bin has energy $E_u$, while an interferer creates a strong competing peak of energy $E_v$. MRC approximately sees

$$
M_{u,\ell}[s_u]\approx E_u,\qquad
M_{u,\ell}[k_v]\approx E_v\rho_{uv}.
$$

Thus, if $E_v\rho_{uv}>E_u$, the interferer can win even when $\rho_{uv}<1$. MRC attenuates spatially inconsistent interferers but never assigns negative evidence to them. The decoder knows that a bin has energy in the target direction, but it does not ask whether the same bin also contradicts the target direction.

This is the positive-only decision bottleneck. It is distinct from packet detection or synchronization failure. Even under oracle target start, CFO, and channel, the final symbol top-1 can be wrong because the decision metric only accumulates non-negative support.

### 2.4 Existing Collision-Decoding Dimensions

CIC, PCube, and MaLoRaGW illustrate how LoRa receivers have expanded beyond standard single-packet demodulation.

CIC uses sub-symbol structure. It selects time fragments whose interferer sets differ and intersects their spectra so that peaks not common to all selected fragments are canceled \cite{cic_sigcomm21}. Its strength is that it can remove interferers without relying on their power order; its limitation is that short windows reduce frequency resolution and highly aligned or similar-frequency interferers can remain difficult.

PCube uses phase-domain clustering. Multiple gateway antennas create air-channel phase diversity, allowing symbols from different transmitters to form clusters in an I/Q phase domain \cite{pcube_mobicom21}. It scales LoRa parallel decoding beyond purely time/frequency features, but requires distinguishable phase clusters and benefits from multiple receive-antenna pairs.

MaLoRaGW uses spatial projection and channel estimation for multi-user MIMO LoRa \cite{maloragw_sensys22}. It projects received streams into spatial subspaces, estimates channels, and applies MIMO processing. Its design highlights the importance of breaking the synchronization-channel-estimation dependency loop in multi-antenna LoRa reception.

SP is complementary to these ideas. It focuses on the final target-conditioned symbol decision after a complete target has been detected. Rather than clustering symbols across packets or reconstructing users, SP asks whether each candidate FFT bin is spatially consistent with the target packet itself.

### 2.5 Trace-Driven Motivation

The motivation experiments use measured clean LoRa packets from the dual-channel B210 receiver. Trace-driven collisions preserve SX127x waveform details, packet-to-packet CFO variation, analog front-end imbalance, and real channel directions while allowing controlled mixing of target and interferer packets.

M1 demonstrates a single signed-spectrum case. For a target packet $u$, SP forms

$$
P_{u,\ell}[k]=\mathbf{a}_u^H\mathbf{Y}_{u,\ell}[k],
\qquad
Q_{u,\ell}[k]=\mathbf{b}_u^H\mathbf{Y}_{u,\ell}[k].
$$

In the support spectrum $|P|^2$, a strong interferer can become the MRC top-1. In the contradiction spectrum $|Q|^2$, the same wrong bin exhibits strong target-orthogonal energy, while the true target bin remains weak. This empirical observation motivates a signed score rather than another non-negative combiner.

M2 characterizes when MRC fails under two-packet collisions. It reuses the real trace records behind the preliminary heatmap, bins observations by channel coherence $\rho$ and SIR, and reports symbol error rate under oracle target synchronization and channel. The purpose is not to introduce SP early, but to show that MRC's failure boundary depends jointly on spatial coherence and near-far power.

M3 extends the motivation to multiple concurrent packets and noise. It bootstraps collisions from measured clean packets, varies the concurrent packet number from 2 to 15, and adds target-referenced waveform noise from $-30$ to $-15$ dB before dechirp. The MRC SER heatmap shows that the positive-only bottleneck is not a two-packet artifact. SP and the comparison decoders are evaluated later on the same symbol samples, after the signed decision rule has been introduced.

Together, these observations yield the design requirement: the receiver should preserve target-direction support, preserve target-orthogonal contradiction, and control the amount of contradiction by packet reliability and interference risk.

## 3. SP Design

### 3.1 Receiver Overview

SP operates on complete packet candidates produced by the receiver front end. For each candidate, the front end provides a start estimate, CFO estimate, STO estimate, channel estimate, confidence metrics, and a list of overlapping candidates. The SP decoding pipeline is:

1. whiten or calibrate the two-channel received samples for spatial filtering;
2. estimate or refine each candidate's target channel direction;
3. estimate channel reliability and packet power;
4. choose a packet-level $\lambda_u$ from a bounded risk objective;
5. for every payload symbol, compute support and contradiction spectra;
6. select the top bin of the signed spectrum;
7. decode with standard LoRa interleaving, Hamming FEC, whitening, explicit header, and PHY CRC;
8. if SP-core fails CRC, optionally run bounded start/CFO refinement and retry the same SP decision.

Manifest information, expected payloads, and application sequence numbers are never used in detection, synchronization, $\lambda_u$ selection, or symbol decisions. They are used only offline for evaluation and plotting.

### 3.2 Signed Spatial Spectrum

For a detected target packet $u$ and payload symbol $\ell$, SP computes

$$
P_{u,\ell}[k]=\mathbf{a}_u^H\mathbf{Y}_{u,\ell}[k],
\qquad
Q_{u,\ell}[k]=\mathbf{b}_u^H\mathbf{Y}_{u,\ell}[k].
$$

$P$ is target-direction support. $Q$ is target-orthogonal contradiction. The signed decision spectrum is

$$
D_{u,\ell}[k]=|P_{u,\ell}[k]|^2-\lambda_u|Q_{u,\ell}[k]|^2.
$$

The decoded symbol is

$$
\hat{s}_{u,\ell}=\arg\max_k D_{u,\ell}[k].
$$

When $\lambda_u=0$, SP reduces to MRC. Positive $\lambda_u$ penalizes bins whose energy is inconsistent with the target channel. The method remains a top-1 symbol decision; it does not branch over multiple symbol candidates and does not perform successive interference cancellation.

### 3.3 Channel Reliability

The contradiction branch is useful only when the target direction is reliable. SP therefore estimates a conservative angular uncertainty for each candidate. The implementation uses robust preamble snapshots, isolation weighting, leave-one-out variation, early-late drift, and a small RF-chain allowance to produce

$$
\theta_u=\theta_{\mathrm{obs}}+\theta_{\mathrm{drift}}+\theta_{\mathrm{rf}}.
$$

The reliable target polarity lower bound is

$$
L_u=\cos^2\theta_u.
$$

For an interferer $v$, let $\widehat{\theta}_{uv}$ be the measured channel angle between $u$ and $v$. Because the interferer's own channel estimate has uncertainty, SP uses a conservative leakage upper bound

$$
U_{uv}=
\cos^2\left(\max(\widehat{\theta}_{uv}-\theta_v,0)\right).
$$

$L_u$ lower-bounds the fraction of target energy that remains in the target branch, while $U_{uv}$ upper-bounds the fraction of interferer energy that can leak into the target branch. These quantities make $\lambda_u$ selection depend on reliability, not only on measured channel coherence.

### 3.4 Risk-Constrained Lambda Selection

A fixed $\lambda$ is not robust across near-far ratios, channel coherence, and noise. SP selects $\lambda_u$ once per packet. If $L_u$ is too small or no overlapping interferer is present, SP sets $\lambda_u=0$. Otherwise, it limits the search to

$$
0\le \lambda_u\le
\lambda_{\mathrm{cap}}
=
\min\left(
\lambda_{\max},
\frac{L_u-\gamma}{1-L_u}
\right),
$$

where $\gamma$ is the reliability guard and $\lambda_{\max}$ is a system cap. This prevents aggressive subtraction when the target direction is uncertain.

For every target-interferer pair $(u,v)$, SP computes a conservative signed-margin lower model. Let $S_u$ and $S_v$ denote packet powers and let $\sigma^2$ denote the FFT-domain noise variance. The pair contributes

$$
A_{uv}=S_uL_u-S_vU_{uv},
$$

$$
B_{uv}=S_v(1-U_{uv})-S_u(1-L_u).
$$

The normalized risk score at $\lambda$ is

$$
R_{uv}(\lambda)=
\frac{A_{uv}+\lambda B_{uv}}
{\sqrt{C_{0,uv}+\lambda^2C_{2,uv}}},
$$

where

$$
C_{0,uv}
=
2\sigma^4+
2\sigma^2\left[S_uL_u+S_vU_{uv}\right],
$$

$$
C_{2,uv}
=
2\sigma^4+
2\sigma^2\left[S_u(1-L_u)+S_v(1-U_{uv})\right].
$$

The denominator normalizes the conservative margin by the noise-induced variation in the support and contradiction branches. SP chooses

$$
\lambda_u
=
\arg\max_{\lambda\in\mathcal{C}_u}
\min_{v\ne u}R_{uv}(\lambda).
$$

The candidate set $\mathcal{C}_u$ is finite. In addition to $0$ and $\lambda_{\mathrm{cap}}$, it includes a pairwise flip point

$$
\lambda_{uv}^{\mathrm{flip}}=-\frac{A_{uv}}{B_{uv}}
$$

when $A_{uv}<0<B_{uv}$, and a pairwise peak point

$$
\lambda_{uv}^{\mathrm{peak}}
=
\frac{B_{uv}C_{0,uv}}{A_{uv}C_{2,uv}}
$$

when $A_{uv}>0$ and $B_{uv}>0$. Points outside the certified interval are discarded. SP additionally evaluates a reliable-polarity midpoint when it lies inside the interval and three deterministic checkpoints at one quarter, one half, and three quarters of $\lambda_{\mathrm{cap}}$. The receiver therefore avoids dense continuous search while still evaluating the analytically meaningful points and a bounded set of possible worst-pair crossings.

This design is intentionally conservative. It may choose $\lambda_u=0$ or a small value when the target channel is unreliable. It may also choose the cap when the target direction is reliable and a strong spatially inconsistent interferer is present. The important property is not that $\lambda_u$ equals an oracle weight, but that its resulting SER is close to the best weight within the same safe interval.

### 3.5 Bounded Sync Refinement

SP-core uses one front-end synchronization result and one risk-selected $\lambda_u$. It directly decodes the packet and checks standard PHY CRC. If CRC closes, no additional synchronization search is performed.

If SP-core fails, the implementation performs bounded coupled start/CFO refinement. It evaluates a fixed ordered list of small start corrections around the front-end estimate and a fixed list of CFO corrections around the estimated CFO. For each trial it re-estimates the channel near the trial CFO, reruns the same SP decoder, and stops when PHY CRC closes or when the trial cap is reached. The default cap is 32 trials.

This refinement is not a payload oracle. It uses only ordinary receiver closure through PHY CRC and does not use manifest identity, expected sequence numbers, or expected payloads. In the main evaluation, SP+sync-refine is the primary scheme; SP-core is reported as an ablation to quantify how much loss is due to front-end residual start/CFO error.

### 3.6 Complexity

For each payload symbol, SP requires the same two-antenna LoRa FFTs used by MRC, two complex spatial projections per bin, one real subtraction per bin, and one top-1. The cost is

$$
O(M\log M+M)
$$

per symbol after synchronization, with a small packet-level $\lambda_u$ search whose candidate count grows linearly with the number of overlapping detected packets. SP does not reconstruct interferer waveforms, does not serially cancel packets, and does not perform combinatorial symbol search. Bounded sync refinement increases cost only for packets that fail SP-core and is capped by a fixed trial budget.

## 4. Implementation

### 4.1 Hardware and PHY

The prototype uses a dual-channel USRP B210 receiver with two synchronized receive channels and fifteen LoRa nodes built from STM32F103 controllers and SX1276 radios. A separate B210 controls experiment configuration and start commands. Nodes transmit standard LoRa packets; no transmitter modification is required.

The real-air experiments use:

- carrier frequency 487.7 MHz;
- SF10;
- BW125 kHz;
- CR4/5;
- 8-symbol preamble;
- explicit header;
- PHY CRC enabled;
- sync word 0x34;
- 20-byte application payload.

The receiver samples both B210 channels synchronously and writes raw IQ for offline decoding. The two receive channels are DC-removed and calibrated for physical-channel comparison methods; SP and MRC use noise-whitened streams appropriate for spatial filtering.

### 4.2 Front End and Candidate Interface

SP is evaluated behind a common packet-detection front end. The front end scans busy regions, keeps searching for new preambles inside them, estimates start/CFO/channel, applies SFD and coherent consistency checks, and removes duplicates by time and spatial direction. It outputs complete packet candidates. Truncated bursts and missed detections are accounted for separately in packet detection rate and TPS; they are not counted as conditional PRR failures.

Each candidate is enriched with reliability fields:

- robust preamble channel estimate;
- $\theta_{\mathrm{obs}}$, $\theta_{\mathrm{drift}}$, and $\theta_{\mathrm{total}}$;
- $L_u$;
- overlapping interferer count;
- $U_{\max}$;
- $\lambda_u$, $\lambda_{\mathrm{cap}}$, and candidate $\lambda$ points.

For reproducibility, the receiver retains per-candidate outputs from SP-core, SP+sync-refine, SP+repair, MRC, CIC, PCube, and MaLoRaGW. Only the prespecified primary methods enter the main comparison; diagnostic variants are reported separately.

### 4.3 Comparison Methods

The comparison boundary is a decoder comparison on common complete targets. All methods operate on the same detected complete packets and the same bounded refined timing/CFO estimate. This avoids conflating front-end misses with conditional decoding performance.

MRC uses target-channel maximum-ratio combining and standard LoRa FEC/CRC.

CIC is implemented as a single-antenna decoder using optimal ICSS spectral intersection, fractional-CFO filtering, RSSI filtering, and ten-window SED. It is evaluated on a fixed physical antenna branch because CIC is originally a single-antenna method.

PCube uses the physical two-channel Rx pair, separated-preamble PDoA, per-bin $Z_1(f)Z_2^*(f)$, and nearest target-PDoA cluster selection. The implementation cannot evaluate PCube's multi-pair combining because the B210 capture provides one synchronized Rx pair.

MaLoRaGW uses physical channel measurements, strongest $\min(K,M)$ channel selection, Moore-Penrose ZF projection, and frequency/time/channel-ratio peak clustering. The evaluation covers uplink decoding only; downlink calibration and beamforming are outside the receive-IQ experiment.

SP+repair is not the primary scheme. It is retained as an appendix diagnostic upper bound that may retry theory-generated $\lambda$ points or repair measured spectral drift after sync refinement. Main-paper claims should use SP+sync-refine.

## 5. Evaluation Methodology

### 5.1 Metrics

The evaluation separates detection from decoding.

Packet Detection Rate is the number of detected complete packet targets divided by the actual transmitted packet count. When only a manifest is available, schedule-normalized detection rate uses manifest planned packets as the denominator.

Conditional PRR is the number of detected complete packet targets whose FEC/PHY CRC closes and whose payload is correct, divided by the number of detected complete packet targets. Truncated packets are excluded from this denominator and reported separately. The success criterion is exact payload equality after standard FEC and PHY CRC; no symbol-correctness threshold is used.

End-to-end delivery ratio divides correct unique payloads by actual or planned transmissions. TPS reports correctly decoded packets per second.

### 5.2 Simulation and Trace-Driven Studies

The evaluation uses simulation only where real-air control is impractical.

M1 uses measured clean packets to show that MRC wrong bins often contain target-orthogonal contradiction. It preserves real waveform impairments and illustrates the core signed-spectrum observation.

M2 reuses trace records from measured clean packets to plot MRC SER over $\rho$ and SIR. This avoids a brittle idealized 0/1 heatmap and establishes the near-far/coherence failure boundary before introducing SP.

M3 bootstraps multi-packet collisions from measured clean packets and adds controlled waveform noise. The main figure reports MRC SER over concurrent packet number and target waveform SNR. It is a motivation figure; it does not claim low-SNR front-end detection gains.

D1 evaluates $\lambda_u$ after the signed-spectrum design is introduced. It uses formal PHY simulation with explicit header, FEC, whitening, interleaving, Hamming coding, Gray mapping, and PHY CRC. It shows the finite candidate search, the failure of fixed $\lambda$, and the closeness of risk-selected performance to hindsight-best performance within the same safe interval.

There is no standalone sync-refine mechanism experiment in the main paper. Bounded sync refinement is evaluated through the main real-air SP+sync-refine result and the SP-core ablation.

### 5.3 Real-Air Experiments

The real-air campaign uses fifteen nodes and a two-antenna B210 receiver. Since the current controller and firmware use CONFIG v1 with Poisson offered load, the experiments avoid requiring deterministic barrier traffic or precise per-node offsets. Instead, they rely on repeated runs, seed selection, and manifest-based accounting to obtain a range of collision orders.

The real experiments include:

- single-node gate checks for all fifteen nodes;
- scaling with active node count;
- offered-load sweeps;
- at least two physical layouts to avoid reporting only favorable channels;
- near-far studies using distance changes rather than RF attenuators;
- decoder-only AWGN stress on already detected complete targets;
- SP-core/SP+sync-refine ablation;
- wall-clock runtime of the full offline receiver.

The primary real-air plots are conditional PRR, packet detection rate, TPS, and end-to-end delivery. Since front-end detection and conditional decoding answer different questions, they are never collapsed into one ambiguous delivery metric.

### 5.4 Fairness and Scope

All real-air method comparisons use the same complete detected targets. This design isolates decoder behavior after detection and synchronization. It does not claim to reproduce each baseline paper's full native front end. For CIC, PCube, and MaLoRaGW, the implementation follows the corresponding paper's decoder operations within the limits of a two-channel uplink B210 recording, and the report records those limits explicitly.

The main comparison set is:

- SP+sync-refine;
- MRC;
- CIC;
- PCube-2Rx;
- MaLoRaGW-2Rx-uplink.

SP-core is an ablation. SP+repair is appendix-only.

## 6. Operating Regimes and Design Implications

The signed model identifies three conditions under which SP can improve upon MRC: the target and interferer are not spatially near-collinear, the interferer is strong enough to create an MRC wrong peak, and the target channel is reliable enough that contradiction does not penalize the true bin. These conditions arise in asynchronous near-far collisions with two separated antennas, but they are not universal.

When channel coherence is very high, $\rho_{uv}\approx 1$, the target-orthogonal branch cannot reliably distinguish target and interferer. The reliability constraint consequently drives SP toward MRC through a small $\lambda_u$. High-coherence collisions are therefore an explicit operating boundary rather than an omitted corner case.

At very low SNR, contradiction evidence can help only after the target has already been detected and synchronized. Accordingly, the noise sweep measures decoder robustness on complete targets and makes no claim of improved low-SNR preamble detection.

When packets are perfectly aligned and share header symbols, several users may place energy in the same FFT bin. In that case the bin contains both target and interferer evidence, and subtracting the entire target-orthogonal component may be insufficient or even harmful. SP is designed for asynchronous concurrent LoRa traffic; fully aligned shared-bin collisions are an explicit limitation.

## 7. Discussion

SP occupies a specific point in the LoRa collision-recovery design space. It is not a replacement for packet detection, time-domain separation, or multi-pair spatial clustering. Instead, it improves the final target-conditioned symbol decision when a two-antenna receiver already has complete packet candidates. This scope is narrower than full end-to-end collision recovery, but it is also the reason the method is lightweight and compatible with standard LoRa transmitters.

The reliability-constrained $\lambda_u$ is central to this scope. A large fixed subtraction weight can produce attractive examples but fails under channel uncertainty and noise. A zero weight is safe but collapses to MRC. SP's contribution is the packet-level mechanism that decides when contradiction is trustworthy enough to use and how far subtraction can go without violating the target's reliable polarity interval.

The two-antenna setting is both a constraint and an opportunity. With only two antennas, there is exactly one target-orthogonal direction, making the signed-spectrum interpretation simple and computationally cheap. Additional antennas could create a higher-dimensional contradiction subspace, but that extension requires a different reliability model and falls outside the two-antenna system studied here.

## 8. Conclusion

This paper presents SP, a reliability-constrained signed spatial decoder for concurrent LoRa reception. SP exposes a positive-only decision bottleneck in MRC-style combining and addresses it by preserving both target-direction support and target-orthogonal contradiction. A bounded risk objective selects the packet-level subtraction weight under channel uncertainty, noise, and multiple interferers. The receiver combines this signed decision with bounded synchronization refinement and standard LoRa FEC/PHY CRC, without reconstructing interferer waveforms or modifying transmitters. Separating packet detection from conditional PRR permits a precise evaluation of both front-end recall and post-detection decoding. The resulting architecture provides a lightweight path to collision recovery with two gateway antennas while making its high-coherence and synchronization boundaries explicit.

## References

\bibitem{cic_sigcomm21}
M. O. Shahid, M. Philipose, K. Chintalapudi, S. Banerjee, and B. Krishnaswamy. 2021. Concurrent Interference Cancellation: Decoding Multi-Packet Collisions in LoRa. In *ACM SIGCOMM 2021*. https://doi.org/10.1145/3452296.3472931.

\bibitem{pcube_mobicom21}
X. Xia, N. Hou, Y. Zheng, and T. Gu. 2021. PCube: Scaling LoRa Concurrent Transmissions with Reception Diversities. In *ACM MobiCom 2021*. https://doi.org/10.1145/3447993.3483268.

\bibitem{maloragw_sensys22}
H. Pirayesh, S. Zhang, P. K. Sangdeh, and H. Zeng. 2022. MaLoRaGW: Multi-User MIMO Transmission for LoRa. In *ACM SenSys 2022*. https://doi.org/10.1145/3560905.3568533.
