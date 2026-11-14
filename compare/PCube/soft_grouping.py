"""Experimental, preamble-anchored packet-wide PDoA grouping.

This fills in clustering details unspecified in PCube Sec.4.5; it is not author
code. Eq.8 products are grouped by circular phase, with a uniform noise group.
No decoded bins, payload labels, CRC, or SP filters enter the grouping.
"""
from __future__ import annotations

import numpy as np
from scipy.special import i0e, logsumexp

POLICY = 'preamble_anchored_soft_pdoa_v1'
TARGET_POLICY = 'target_noise_soft_pdoa_v2'
CONSERVATIVE_POLICY = 'accepted_cluster_soft_extension_v3'
EPS = 1e-30


def group_packet(spectra, candidates, reference_phases, reference_powers, target_index,
                 preamble_len, *, target_only=False, preserve_accepted=False):
    counts = [len(c) for c in candidates]
    if not counts:
        return [], [], dict(policy=POLICY)
    phases, magnitudes, phase_variances, weights = [], [], [], []
    for f, c in zip(spectra, candidates):
        p = abs(f[:2])**2
        noise = np.median(p,axis=1) / np.log(2.)
        z = f[0,c] * f[1,c].conj()
        signal = np.maximum(p[:,c] - noise[:,None], EPS)
        # Delta-method variance of arg(Z1 conj(Z2)); bound diffuse observations.
        v = (noise[0]*signal[1] + noise[1]*signal[0] + noise.prod()) / (2*signal.prod(axis=0))
        phases.extend(np.angle(z))
        magnitudes.extend(abs(z))
        phase_variances.extend(np.minimum(v,np.pi**2))
        weights.extend(abs(z) / max(float(np.max(abs(z))),EPS))
    phases = np.asarray(phases)
    magnitude = np.asarray(magnitudes)
    observation_var = np.asarray(phase_variances)
    weights = np.asarray(weights)
    refs = np.asarray(reference_phases)
    powers = np.maximum(np.asarray(reference_powers,dtype=float),EPS)
    prior = powers / powers.sum()
    d = np.angle(np.exp(1j*(phases[:,None]-refs[None,:])))
    # Account for finite preamble averaging. Fixed reference centers preserve
    # packet identities when nearby phase clusters cannot be resolved.
    reference_var = np.full(refs.size,float(np.median(observation_var))/max(1,preamble_len))
    intrinsic_var = np.zeros(refs.size)

    def membership():
        variance = observation_var[:,None]+reference_var[None,:]+intrinsic_var[None,:]
        kappa = 1./np.maximum(variance,1e-8)
        log_density = kappa*(np.cos(d)-1.) - np.log(2*np.pi) - np.log(i0e(kappa))
        log_signal = np.log(.95*prior)[None,:] + log_density
        log_noise = np.full((len(phases),1),np.log(.05/(2*np.pi)))
        joint = np.column_stack((log_signal,log_noise))
        return np.exp(log_signal-logsumexp(joint,axis=1)[:,None])

    # Pool phase scatter across the entire packet, with eight zero-excess-
    # variance pseudo-observations from the calibrated preamble as shrinkage.
    # The iteration count and noise-group mass are fixed before evaluation.
    for _ in range(12):
        responsibility = membership()
        w = weights[:,None]*responsibility
        excess = np.maximum(d*d-observation_var[:,None]-reference_var[None,:],0.)
        updated = np.sum(w*excess,axis=0)/(np.sum(w,axis=0)+max(1,preamble_len))
        if np.max(abs(updated-intrinsic_var))<1e-6:
            intrinsic_var = updated
            break
        intrinsic_var = updated
    responsibility = membership()
    if preserve_accepted:
        # Minimal repair: keep the historical ranking of admitted peaks. Add
        # target-group-supported evidence outside the old rejection boundary.
        # This is one spectrum decision, not a CRC/decoder-outcome portfolio.
        membership_weight=np.where(abs(d[:,target_index])<=.5,1.,responsibility[:,target_index])
        scores=magnitude*np.maximum(np.cos(d[:,target_index]),0.)*membership_weight
    elif target_only:
        # Preserve the historical rotated-real ranking where phase is reliable;
        # the continuous target/noise membership replaces only hard rejection.
        scores = magnitude*np.maximum(np.cos(d[:,target_index]),0.)*responsibility[:,target_index]
    else:
        scores = magnitude*responsibility[:,target_index]
    bins, margins = [], []
    offset = 0
    for c,n in zip(candidates,counts):
        score = scores[offset:offset+n]
        chosen = int(np.argmax(score))
        if preserve_accepted and score[chosen]<=EPS:
            chosen=int(np.argmin(abs(d[offset:offset+n,target_index])))
        bins.append(int(c[chosen]))
        order = np.sort(score)
        margins.append(float(order[-1]/max(float(order[-2]),EPS)) if n>1 else 1e30)
        offset += n
    policy=CONSERVATIVE_POLICY if preserve_accepted else TARGET_POLICY if target_only else POLICY
    return bins,margins,dict(policy=policy,reference_phases_rad=refs.tolist(),
        reference_power_priors=prior.tolist(),reference_variance_rad2=reference_var.tolist(),
        packet_excess_phase_variance_rad2=intrinsic_var.tolist(),
        noise_group_prior=.05,clustering_details='local_reproduction_choice_not_specified_by_original_paper')
