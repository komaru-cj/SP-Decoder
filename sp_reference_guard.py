"""Preamble-only reference and range guards for the single-path SP receiver.

The strength confidence interval is a Gaussian preamble-average approximation,
not a guarantee on packet errors. No payload decisions or CRC enter this file.
"""
from __future__ import annotations
import math
import time
import numpy as np
from scipy.stats import norm
from compare.mrc_input import physical_preamble_measurements
from sp_noise_competition import DEFAULT_NOISE_FALSE_ALARM, noise_max_threshold

GUARDED_PAIR_POLICY = 'pair_and_noise_reference_guard_v2'


def pairs(h):
    return [[float(v.real), float(v.imag)] for v in h]


def vector(h):
    return np.asarray([complex(*v) for v in h], dtype=np.complex128)


def decision_channel(est):
    if float(est.get('lambda_sp', 0.)) == 0 and 'mrc_decision_channel_sp' in est:
        return est['mrc_decision_channel_sp']
    return est.get('channel_sp', est.get('channel', []))


def apply_reference_guard(physical, whitener, estimates, cfg, *, gamma, max_lambda):
    # Import at call time to avoid a cycle with the historical configurator.
    from evaluate_sp_dechirp_real_pos import SPPacketReliability, channel_angle, choose_lambda_sp
    if physical is None or whitener is None:
        raise ValueError('reference-guard policy requires physical samples and their whitener')
    W = np.asarray(whitener, dtype=np.complex128)
    if W.shape != (2, 2) or not np.all(np.isfinite(W)):
        raise ValueError('reference-guard policy requires a finite 2x2 whitener')
    required=set()
    competitors={}
    for i,e in enumerate(estimates):
        end=e['start_sample']+e.get('sto_samples_sp',0.)+(cfg.payload_start_symbols+cfg.payload_symbol_count)*cfg.samples_per_symbol
        payload=e['start_sample']+e.get('sto_samples_sp',0.)+cfg.payload_start_symbols*cfg.samples_per_symbol
        vs=[j for j,v in enumerate(estimates) if i!=j
            and v['start_sample']+v.get('sto_samples_sp',0.)<end
            and v['start_sample']+v.get('sto_samples_sp',0.)+(cfg.payload_start_symbols+cfg.payload_symbol_count)*cfg.samples_per_symbol>payload]
        competitors[i]=vs
        if len(vs)<=1:required.update([i,*vs])
    hs, physical_h, rels, elapsed = {}, {}, {}, {}
    for i in sorted(required):
        began=time.perf_counter_ns()
        e=estimates[i]
        ph=physical_preamble_measurements(physical,e,cfg)[0]
        h=W@ph
        # Move the old uncertainty cone to the new center without shrinking
        # it: triangle inequality preserves the old estimated coverage.
        theta=min(math.pi/2,e['theta_total']+channel_angle(h,vector(e['channel_sp'])))
        hs[i],physical_h[i]=h,ph
        rels[i]=SPPacketReliability(e['theta_obs'],e['theta_drift'],theta,
            math.cos(theta)**2,float(np.vdot(h,h).real),e['noise_sigma2_sp'],e['robust_hit_count'])
        elapsed[i]=(time.perf_counter_ns()-began)/1e6
    for i,e in enumerate(estimates):
        e['lambda_guard_policy_sp']=GUARDED_PAIR_POLICY
        vs=competitors[i]
        if len(vs)>1:
            e['lambda_guard_reason_sp']=('retain_reliability_limited_multiuser_branch'
                if e.get('lambda_fixed_global_cap_removed_sp',False)
                else 'retain_bounded_multiuser_branch')
            continue
        began=time.perf_counter_ns()
        indices=[i,*vs]
        rs=[rels[j] for j in indices]
        lam,U,cert,rows,diag=choose_lambda_sp(0,rs,[hs[j] for j in indices],
            gamma=gamma,max_lambda=max_lambda,
            noise_bin_count=cfg.m-1)
        strength_margin=None
        if not vs:
            reason='no_payload_overlapping_competitor';lam=0.
        else:
            # Variance of the difference of two squared vector norms under
            # an eight-preamble coherent-average approximation, in FFT units.
            n=rs[0].noise_sigma2/max(1,cfg.preamble_len)
            se=math.sqrt(4*n*n+2*n*(rs[0].power+rs[1].power))
            strength_margin=rs[1].power-rs[0].power-norm.ppf(1-DEFAULT_NOISE_FALSE_ALARM/2)*se
            if U>=rs[0].L:
                reason='reference_cones_not_separated';lam=0.
            elif strength_margin<=0:
                reason='no_confident_interference_dominance';lam=0.
            elif diag['selected_objective'] is None or diag['selected_objective']<=0:
                reason='no_positive_joint_margin';lam=0.
            else:reason='guarded_pair_weight'
        for row in rows:row['interferer_index']=indices[row['interferer_index']]
        actual=next(p for p in diag['candidate_points'] if abs(p['lambda']-lam)<1e-10)
        e.update(channel_sp=pairs(hs[i]),reference_channel_source_sp='CFO_compensated_physical_MRC_preamble_then_whitened',
            theta_total=rs[0].theta_total,L_u=rs[0].L,power_sp=rs[0].power,
            lambda_sp=float(lam),U_max_sp=U,certified_sp=bool(lam>0 and cert),
            lambda_pair_rows_sp=rows,lambda_cap_sp=diag['lambda_cap'],
            lambda_threshold_sp=lam/(1+lam),lambda_objective_sp=actual['objective'],
            lambda_candidate_points_sp=diag['candidate_points'],lambda_guard_reason_sp=reason,
            lambda_guard_strength_margin_sp=strength_margin,
            lambda_guard_proposed_lambda_sp=diag['selected_lambda'],
            lambda_guard_proposed_objective_sp=diag['selected_objective'],
            lambda_selection_reason_sp=reason,lambda_policy_sp=GUARDED_PAIR_POLICY,
            lambda_pair_objective_sp=actual.get('pair_objective'),
            lambda_noise_objective_sp=actual.get('noise_objective'),
            lambda_noise_max_threshold_sp=noise_max_threshold(lam,rs[0].noise_sigma2,cfg.m-1),
            sp_mrc_fallback=bool(lam==0))
        if lam==0:
            # White coordinates y_w=W y: d=W^{-H}h_MRC gives d^H y_w=h_MRC^H y.
            # Keep this decision vector separate from the whitened channel
            # direction used for the spatial/error statistics.
            e['mrc_decision_channel_sp']=pairs(np.linalg.solve(W.conj().T,physical_h[i]))
        extra=elapsed[i]+(time.perf_counter_ns()-began)/1e6
        e['lambda_config_elapsed_ms']=e.get('lambda_config_elapsed_ms',0.)+extra
        e['lambda_reference_guard_elapsed_ms']=extra
    return estimates
