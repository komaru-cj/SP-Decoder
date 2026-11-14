"""Fixed, target-conditioned MRC on the physical receive channels.

Only the supplied synchronization and preamble are used.  The same weights
are reused for the entire target frame; payload decisions never select them.
"""

from __future__ import annotations

import math
import numpy as np

from lora_mrc_sp_core import (
    compensate_symbol_window,
    instantaneous_chirp,
    lora_symbol_fft,
)

EPS = 1e-30
MRC_CIC = "mrc_cic"
MRC_CORA = "mrc_cora"


def physical_preamble_measurements(samples, estimate, cfg):
    """Return the physical channel, PDoA, and Ch0 preamble-bin power."""
    downchirp = instantaneous_chirp(0, cfg, up=False)
    cfo = float(estimate.get("cfo_bins_sp", estimate.get("continuous_cfo_bins", estimate.get("cfo_bins", 0.0))))
    sto = float(estimate.get("sto_samples_sp", estimate.get("sto_samples", 0.0)))
    snapshots, products, powers = [], [], []
    for p in range(int(cfg.preamble_len)):
        start = float(estimate["start_sample"]) + p * cfg.samples_per_symbol
        if start + sto < 0 or start + sto + cfg.samples_per_symbol > samples.shape[1]:
            continue
        comp = compensate_symbol_window(samples, start, cfo, cfg, sto_samples=sto)
        spectra = np.vstack([lora_symbol_fft(row * downchirp, cfg) for row in comp])
        local = np.asarray([k % cfg.m for k in range(-2, 3)], dtype=np.int64)
        peak = int(local[np.argmax(np.sum(abs(spectra[:, local]) ** 2, axis=0))])
        vector = spectra[:, peak].astype(np.complex128)
        snapshots.append(vector)
        if vector.size >= 2:
            products.append(vector[0] * np.conj(vector[1]))
        powers.append(float(abs(vector[0]) ** 2))
    if not snapshots:
        # Do not use a possibly whitened SP channel as a physical-Rx vector.
        raise ValueError("MRC requires an observable preamble or a supplied physical channel")
    vectors = np.asarray(snapshots)
    reference = vectors[np.argmax(np.sum(abs(vectors) ** 2, axis=1))]
    aligned = np.asarray([v * np.exp(-1j * np.angle(np.vdot(reference, v))) for v in vectors])
    channel = np.median(aligned.real, axis=0) + 1j * np.median(aligned.imag, axis=0)
    pdoa = float(np.angle(np.sum(products))) if products else 0.0
    return channel, pdoa, float(np.median(powers))


def mrc_weights(channel, channel_count):
    channel = np.asarray(channel, dtype=np.complex128).reshape(-1)
    if channel.size != channel_count or not np.all(np.isfinite(channel)):
        raise ValueError("MRC channel must match the physical input channels and be finite")
    return np.conj(channel / (np.linalg.norm(channel) + EPS))


def target_mrc_weights(samples, estimate, cfg):
    supplied = estimate.get("shared_sp_mrc_channel", estimate.get("shared_sp_physical_channel"))
    if supplied is not None:
        channel = np.asarray([complex(*value) for value in supplied])
        source = "shared_physical_preamble_channel"
    else:
        channel, _, _ = physical_preamble_measurements(samples, estimate, cfg)
        source = "physical_preamble_at_supplied_sync"
    return mrc_weights(channel, samples.shape[0]), source


def target_mrc_input(samples, estimate, cfg):
    """Combine just this target's frame, preserving its fractional start/CFO.

    Cropping avoids combining a complete capture again for every target.
    One interpolation guard sample is retained on either side of the frame.
    """
    if np.ndim(samples) != 2 or samples.shape[0] < 2:
        raise ValueError("MRC baseline requires at least two physical receive channels")
    weights, source = target_mrc_weights(samples, estimate, cfg)
    start = float(estimate["start_sample"]) + float(estimate.get("sto_samples_sp", estimate.get("sto_samples", 0.0)))
    frame_samples = (float(cfg.payload_start_symbols) + int(cfg.payload_symbol_count)) * cfg.samples_per_symbol
    begin = max(0, int(math.floor(start)) - 1)
    end = min(samples.shape[1], int(math.ceil(start + frame_samples)) + 1)
    combined = (weights @ samples[:, begin:end])[None, :]
    local = dict(estimate)
    local["start_sample"] = float(estimate["start_sample"]) - begin
    return combined, local, weights, source
