"""Single packet-level SP weight with explicit all-bin noise competition.

No payload samples, CRC, or truth enter this selector. The pair margins remain
the existing structural surrogates. The noise maximum threshold uses an exact
single-bin tail plus a union bound under the white complex Gaussian model;
the standardized target margin is a surrogate, not a total error guarantee.
"""
from __future__ import annotations

import math
import numpy as np
from scipy.optimize import brentq

POLICY = 'pair_and_noise_max_v1'
TWO_PACKET_POLICY = 'pair_and_noise_two_packet_v1'
DEFAULT_NOISE_FALSE_ALARM = .05


def noise_max_threshold(lam, sigma2, bin_count, false_alarm=DEFAULT_NOISE_FALSE_ALARM):
    """Upper-tail threshold for max_n (|P_n|²-lambda|Q_n|²).

    For t>=0, Pr(D>t)=exp(-t/sigma2)/(1+lambda). Independence
    BETWEEN bins is unnecessary for the union bound. Within each bin, P/Q
    must be independent white complex Gaussian noise with variance sigma2.
    """
    if lam < 0 or sigma2 <= 0 or bin_count < 1 or not 0 < false_alarm < 1:
        raise ValueError('invalid noise competition parameters')
    return sigma2 * max(0., math.log(bin_count / false_alarm) - math.log1p(lam))


def select_with_noise(pair_rows, seed_candidates, *, power, reliability,
                      noise_sigma2, cap, noise_bin_count,
                      noise_false_alarm=DEFAULT_NOISE_FALSE_ALARM):
    """Maximize min(pair margins, target-vs-noise-maximum margin)."""
    if not math.isfinite(cap) or cap < 0:
        raise ValueError('a finite nonnegative reliability cap is required')
    if power < 0 or not 0 <= reliability <= 1 or noise_sigma2 <= 0:
        raise ValueError('invalid target reference statistics')
    sigma2 = float(noise_sigma2)
    signal_p = float(power * reliability)
    signal_q = float(power * (1. - reliability))
    var_p = sigma2**2 + 2. * sigma2 * signal_p
    var_q = sigma2**2 + 2. * sigma2 * signal_q
    candidates = {}

    def add(lam, source):
        value = float(np.clip(lam, 0., cap))
        # Avoid moving a rounded boundary outside the cap.
        key = min(cap, round(value, 12))
        candidates.setdefault(key, [])
        if source not in candidates[key]:
            candidates[key].append(source)

    def noise_margin(lam):
        threshold = noise_max_threshold(lam, sigma2, noise_bin_count, noise_false_alarm)
        mean = signal_p - lam * signal_q + sigma2 * (1. - lam)
        return (mean - threshold) / math.sqrt(max(var_p + lam * lam * var_q, 1e-30))

    def pair_margin(row, lam):
        return (row['A_under'] + lam * row['B_under']) / math.sqrt(
            max(row['C0'] + lam * lam * row['C2'], 1e-30))

    for item in seed_candidates:
        for source in item['sources']:
            add(item['lambda'], source)
    add(0., 'boundary_low')
    add(cap, 'boundary_cap')
    # Geometric checkpoints preserve small useful weights when cap is large.
    value = 1. / 16.
    while value < cap:
        add(value, 'geometric_checkpoint')
        value *= 2.
    # Lower-envelope optima can occur at pair/noise crossings. Retain these
    # explicitly instead of making accuracy depend on cap/4 checkpoints.
    brackets = sorted(candidates)
    for index, row in enumerate(pair_rows):
        def difference(lam):
            return pair_margin(row, lam) - noise_margin(lam)
        for left, right in zip(brackets[:-1], brackets[1:]):
            a, b = difference(left), difference(right)
            if a * b < 0.:
                root = brentq(difference, left, right, xtol=1e-10)
                add(root, f'pair_{index}_noise_crossing')

    evaluated = []
    for lam in sorted(candidates):
        pair = min((pair_margin(row, lam) for row in pair_rows), default=float('inf'))
        noise = noise_margin(lam)
        evaluated.append(dict(lambda_value=lam, sources=candidates[lam],
            pair_objective=float(pair), noise_objective=float(noise),
            objective=float(min(pair, noise))))
    best = max(evaluated, key=lambda row: (row['objective'], -row['lambda_value']))
    selected = best['lambda_value']
    return dict(policy=POLICY, lambda_cap=cap, selected_lambda=selected,
        selected_threshold=selected / (1. + selected),
        selected_objective=best['objective'],
        selected_pair_objective=best['pair_objective'],
        selected_noise_objective=best['noise_objective'],
        noise_bin_count=int(noise_bin_count), noise_false_alarm=noise_false_alarm,
        noise_max_threshold=noise_max_threshold(selected, sigma2, noise_bin_count, noise_false_alarm),
        candidate_points=[dict(**{k: v for k, v in row.items() if k != 'lambda_value'}, **{'lambda': row['lambda_value']}) for row in evaluated],
        selection_reason='noise_constrained_risk_maximizer' if selected > 0 else 'mrc_is_noise_constrained_risk_maximizer')
