"""Paper comparison decoders for the real dual-B210 capture pipeline.

The formal receiver supplies a common SP-refined packet estimate; an optional
ablation can instead supply each receiver's paper-native packet estimate.
From that point onward each implementation uses the signal representation and
decision rule described by its paper:

* LoRaWAN: physical Ch0 only and one strongest FFT bin per payload symbol.
* MRC: its own dual-channel estimate, fixed maximum-ratio combining, and one
  strongest combined FFT bin per payload symbol.
* MRC+CIC: fixed target MRC, optimal ICSS spectral intersection (Eq. 12),
  fractional-CFO/RSSI filters, and the ten-window SED rule (Eqs. 15--17).
* PCube: one synchronized Rx-pair, per-bin ``Z1 * conj(Z2)`` (Eq. 8), and
  the user-approved V3 accepted-cluster soft extension. Eq.9 multi-pair combining is not
  available with only two recorded antennas.
* MaLoRaGW: strongest ``min(K, M)`` channel selection, paper ZF projection,
  and peak clustering by fractional frequency/time and channel ratio.

No manifest value, expected payload, CRC repair, or SP signed spectrum is used
by these comparison decoders.  All decoded bins go through the same standard
LoRa FEC/CRC implementation as the main receiver.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from compare.mrc_input import mrc_weights, physical_preamble_measurements
from compare.PCube.soft_grouping import CONSERVATIVE_POLICY as DEFAULT_PCUBE_POLICY

from lora_mrc_sp_core import (
    compensate_symbol_window,
    instantaneous_chirp,
    lora_symbol_fft,
)
from lora_phy_decode import decode_payload_from_symbol_bins


EPS = 1e-30


def _complex_pairs(values: list[list[float]]) -> np.ndarray:
    return np.asarray([complex(real, imag) for real, imag in values], dtype=np.complex128)


def _physical_evidence_key(est: dict) -> tuple:
    """Return a cache identity that cannot cross physical packet hypotheses."""

    supplied = est.get("_physical_evidence_key")
    if supplied is not None:
        return tuple(supplied) if isinstance(supplied, list) else (supplied,)
    channel = np.asarray(
        [complex(value[0], value[1]) for value in est.get("channel", [])],
        dtype=np.complex128,
    )
    norm = float(np.linalg.norm(channel))
    if norm > EPS:
        channel = channel / norm
    direction = tuple(
        (round(float(value.real), 9), round(float(value.imag), 9))
        for value in channel
    )
    return (
        "derived",
        round(float(est.get("start_sample", 0.0)), 9),
        round(float(est.get("sto_samples_sp", est.get("sto_samples", 0.0))), 9),
        round(
            float(est.get("cfo_bins_sp", est.get("continuous_cfo_bins", est.get("cfo_bins", 0.0)))),
            9,
        ),
        direction,
    )


def _payload_parameters_key(est: dict, cfg, symbol_index: int) -> tuple:
    return (
        _physical_evidence_key(est),
        round(float(est["start_sample"]), 9),
        round(float(est.get("sto_samples_sp", est.get("sto_samples", 0.0))), 9),
        round(
            float(est.get("cfo_bins_sp", est.get("continuous_cfo_bins", est["cfo_bins"]))),
            9,
        ),
        int(symbol_index),
        int(cfg.samples_per_symbol),
        int(cfg.m),
    )


def _physical_mixed(samples: np.ndarray, est: dict, cfg, symbol_index: int) -> np.ndarray:
    symbol_start = (
        float(est["start_sample"])
        + (float(cfg.payload_start_symbols) + int(symbol_index)) * cfg.samples_per_symbol
    )
    cfo = float(est.get("cfo_bins_sp", est.get("continuous_cfo_bins", est["cfo_bins"])))
    sto = float(est.get("sto_samples_sp", est.get("sto_samples", 0.0)))
    window = compensate_symbol_window(samples, symbol_start, cfo, cfg, sto_samples=sto)
    return window * instantaneous_chirp(0, cfg, up=False)[None, :]


@dataclass
class PhysicalEvidencePayloadCache:
    """Per-capture payload work cache, keyed by certified physical evidence.

    The cache is intentionally scoped to one input IQ array.  It never shares
    a spectrum merely because two hypotheses are close in time: the anonymous
    candidate's physical evidence and all compensation parameters are part of
    every key.
    """

    mixed: dict[tuple, np.ndarray] = field(default_factory=dict)
    spectra: dict[tuple, np.ndarray] = field(default_factory=dict)
    mixed_hits: int = 0
    mixed_misses: int = 0
    spectrum_hits: int = 0
    spectrum_misses: int = 0

    def mixed_for(
        self,
        samples: np.ndarray,
        est: dict,
        cfg,
        symbol_index: int,
    ) -> np.ndarray:
        key = (id(samples), *_payload_parameters_key(est, cfg, symbol_index))
        value = self.mixed.get(key)
        if value is not None:
            self.mixed_hits += 1
            return value
        self.mixed_misses += 1
        value = _physical_mixed(samples, est, cfg, symbol_index)
        self.mixed[key] = value
        return value

    def spectra_for(
        self,
        samples: np.ndarray,
        est: dict,
        cfg,
        symbol_index: int,
    ) -> np.ndarray:
        key = (id(samples), *_payload_parameters_key(est, cfg, symbol_index))
        value = self.spectra.get(key)
        if value is not None:
            self.spectrum_hits += 1
            return value
        self.spectrum_misses += 1
        mixed = self.mixed_for(samples, est, cfg, symbol_index)
        value = np.vstack(
            [lora_symbol_fft(mixed[ch], cfg) for ch in range(mixed.shape[0])]
        )
        self.spectra[key] = value
        return value

    def audit(self) -> dict:
        return {
            "scope": "same_iq_same_anonymous_physical_evidence_and_compensation",
            "mixed_hits": int(self.mixed_hits),
            "mixed_misses": int(self.mixed_misses),
            "spectrum_hits": int(self.spectrum_hits),
            "spectrum_misses": int(self.spectrum_misses),
            "cached_payload_symbol_mixes": int(len(self.mixed)),
            "cached_payload_symbol_spectra": int(len(self.spectra)),
        }


def _physical_spectra(samples: np.ndarray, est: dict, cfg, symbol_index: int) -> np.ndarray:
    mixed = _physical_mixed(samples, est, cfg, symbol_index)
    return np.vstack([lora_symbol_fft(mixed[ch], cfg) for ch in range(mixed.shape[0])])


def _local_peaks(
    power: np.ndarray,
    *,
    ratio: float = 6.0,
    max_fraction: float = 0.01,
    limit: int = 64,
) -> np.ndarray:
    values = np.asarray(power, dtype=np.float64)
    if values.size == 0:
        return np.asarray([], dtype=np.int64)
    floor = float(np.median(values)) + EPS
    mask = (
        (values >= np.roll(values, 1))
        & (values >= np.roll(values, -1))
        & (values >= float(ratio) * floor)
        & (values >= float(max_fraction) * float(np.max(values)))
    )
    peaks = np.flatnonzero(mask)
    if peaks.size == 0:
        return np.asarray([int(np.argmax(values))], dtype=np.int64)
    if peaks.size > int(limit):
        order = np.argsort(values[peaks])[-int(limit) :]
        peaks = peaks[order]
    return peaks.astype(np.int64, copy=False)


def _result(method: str, bins: list[int], margins: list[float], diagnostics: dict) -> dict:
    phy = decode_payload_from_symbol_bins(bins, diagnostics.pop("cfg"))
    return {
        "method": method,
        "symbol_bins": [int(value) for value in bins],
        "mean_symbol_margin": float(np.mean(margins)) if margins else 0.0,
        "phy": {
            "payload_hex": phy.payload.hex(),
            "phy_crc_ok": bool(phy.phy_crc_ok),
            "corrected_codewords": int(phy.corrected_codewords),
            "uncorrected_codewords": int(phy.uncorrected_codewords),
            "header_nibbles": [int(value) for value in phy.header_nibbles],
            "status": phy.status,
        },
        "paper_diagnostics": diagnostics,
    }


def _frontend_audit(est: dict) -> dict:
    """Expose shared-SP initialization versus paper-method refinement."""

    return {
        "shared_sp_fine_sync_seed": bool(
            est.get("shared_sp_fine_sync_seed", est.get("shared_sp_fine_sync", False))
        ),
        "shared_sp_fine_sync_and_parameters": bool(
            est.get("shared_sp_fine_sync_and_parameters", False)
        ),
        "paper_method_refinement_applied": bool(
            est.get("paper_method_refinement_applied", False)
        ),
        "paper_method_parameter_estimation_applied": bool(
            est.get("paper_method_parameter_estimation_applied", False)
        ),
        "paper_refinement_start_delta_samples": est.get(
            "paper_refinement_start_delta_samples"
        ),
        "paper_refinement_cfo_delta_bins": est.get(
            "paper_refinement_cfo_delta_bins"
        ),
        "paper_refinement_fallback_reason": est.get(
            "paper_refinement_fallback_reason"
        ),
        "paper_refinement_channel_source": est.get(
            "paper_refinement_channel_source"
        ),
    }


def _preamble_measurements(samples: np.ndarray, est: dict, cfg) -> tuple[np.ndarray, float, float]:
    """Return physical channel direction, PDoA, and Ch0 preamble-bin power."""

    try:
        return physical_preamble_measurements(samples, est, cfg)
    except ValueError:
        fallback = _complex_pairs(est.get("channel_sp", est["channel"]))
        pdoa = float(np.angle(fallback[0] * np.conj(fallback[1]))) if fallback.size >= 2 else 0.0
        return fallback, pdoa, 0.0


def _masked_cic_spectrum(mixed: np.ndarray, cfg, begin: int, end: int) -> np.ndarray:
    begin = max(0, int(begin))
    end = min(int(end), int(cfg.samples_per_symbol))
    if end <= begin:
        return np.zeros(cfg.m, dtype=np.float64)
    first_chip = int(math.ceil(begin / cfg.osr))
    last_chip = int(math.floor((end - 1) / cfg.osr))
    if last_chip < first_chip:
        return np.zeros(cfg.m, dtype=np.float64)
    chip_index = np.arange(first_chip, last_chip + 1, dtype=np.int64)
    buffer = np.zeros(cfg.m, dtype=np.complex128)
    buffer[chip_index % cfg.m] = mixed[chip_index * cfg.osr]
    power = np.abs(np.fft.fft(buffer)) ** 2
    return power / (float(np.sum(power)) + EPS)


def _intersection(spectra: list[np.ndarray]) -> np.ndarray:
    return np.minimum.reduce(np.asarray(spectra, dtype=np.float64), axis=0)


def _fractional_offsets_and_power(mixed: np.ndarray, cfg, bins: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    chips = np.asarray(mixed, dtype=np.complex128)[:: cfg.osr][: cfg.m]
    oversampling = 16
    spectrum = np.fft.fft(chips, n=oversampling * cfg.m)
    offsets = np.arange(-oversampling // 2, oversampling // 2 + 1, dtype=np.int64)
    fractional: list[float] = []
    powers: list[float] = []
    for coarse in np.asarray(bins, dtype=np.int64):
        indices = (int(coarse) * oversampling + offsets) % spectrum.size
        local_power = np.abs(spectrum[indices]) ** 2
        best = int(np.argmax(local_power))
        fractional.append(float(offsets[best]) / oversampling)
        powers.append(float(local_power[best]))
    return np.asarray(fractional), np.asarray(powers)


def _cic_preamble_features(samples: np.ndarray, est: dict, cfg, weights=None) -> tuple[float, float]:
    """Estimate CIC's fractional-CFO and RSSI features from the preamble."""

    downchirp = instantaneous_chirp(0, cfg, up=False)
    cfo = float(est.get("cfo_bins_sp", est.get("continuous_cfo_bins", est["cfo_bins"])))
    sto = float(est.get("sto_samples_sp", est.get("sto_samples", 0.0)))
    preamble_fractional: list[float] = []
    powers: list[float] = []
    for preamble_index in range(int(cfg.preamble_len)):
        start = float(est["start_sample"]) + preamble_index * cfg.samples_per_symbol
        if start + sto < 0.0 or start + sto + cfg.samples_per_symbol > samples.shape[1]:
            continue
        comp = compensate_symbol_window(samples, start, cfo, cfg, sto_samples=sto)
        combined = comp[0] if weights is None else weights @ comp
        mixed = combined * downchirp
        offsets, peak_power = _fractional_offsets_and_power(
            mixed, cfg, np.asarray([0], dtype=np.int64)
        )
        preamble_fractional.append(float(offsets[0]))
        powers.append(float(peak_power[0]))
    fractional = preamble_fractional
    if not fractional:
        return 0.0, 0.0
    # Circular median on the one-bin fractional-frequency interval.
    phase = np.exp(2j * np.pi * np.asarray(fractional, dtype=np.float64))
    expected_fractional = float(np.angle(np.sum(phase)) / (2.0 * np.pi))
    return expected_fractional, float(np.median(powers)) if powers else 0.0


@dataclass
class PaperComparisonContext:
    """Reusable context for one capture's paper-comparison decoders."""

    physical_samples: np.ndarray
    estimates: list[dict]
    cfg: object
    frontend_method: str | None = None
    payload_spectrum_cache: PhysicalEvidencePayloadCache | None = None

    def __post_init__(self) -> None:
        self.physical_samples = np.asarray(self.physical_samples, dtype=np.complex64)
        self._reused_local_refinement_channel_count = 0
        self._channels: list[np.ndarray] = []
        self._pdoas: list[float] = []
        self._ch0_powers: list[float] = []
        self._cic_fractional_cfos: list[float] = []
        self._cic_preamble_powers: list[float] = []
        for estimate in self.estimates:
            shared_channel = estimate.get(
                "shared_sp_mrc_channel",
                estimate.get("shared_sp_physical_channel"),
            )
            if self.frontend_method == "lorawan":
                channel = np.ones(
                    self.physical_samples.shape[0], dtype=np.complex128
                )
                pdoa = 0.0
                power = 0.0
            elif self.frontend_method in {"mrc", "mrc_cic"} and shared_channel is not None:
                channel = _complex_pairs(shared_channel)
                pdoa = (
                    float(np.angle(channel[0] * np.conj(channel[1])))
                    if channel.size >= 2
                    else 0.0
                )
                power = float(abs(channel[0]) ** 2) if channel.size else 0.0
            elif (
                self.frontend_method in {"pcube", "maloragw"}
                and bool(estimate.get("paper_method_refinement_applied", False))
                and estimate.get("channel")
            ):
                # The bounded method-native relocation already certified this
                # target's preamble channel.  Reusing it avoids a second
                # preamble FFT pass while keeping the value bound to the same
                # candidate's start/CFO/channel evidence.
                channel = _complex_pairs(estimate["channel"])
                pdoa = (
                    float(np.angle(channel[0] * np.conj(channel[1])))
                    if channel.size >= 2
                    else 0.0
                )
                power = float(abs(channel[0]) ** 2) if channel.size else 0.0
                estimate["paper_refinement_channel_source"] = (
                    "cached_method_native_local_refinement"
                )
                self._reused_local_refinement_channel_count += 1
            else:
                channel, pdoa, power = _preamble_measurements(
                    self.physical_samples, estimate, self.cfg
                )
            self._channels.append(channel)
            self._pdoas.append(pdoa)
            self._ch0_powers.append(power)
            if self.frontend_method == "mrc_cic":
                cic_fractional, cic_power = _cic_preamble_features(
                    self.physical_samples, estimate, self.cfg,
                    weights=mrc_weights(channel, self.physical_samples.shape[0]),
                )
            else:
                cic_fractional, cic_power = 0.0, power
            self._cic_fractional_cfos.append(float(cic_fractional))
            self._cic_preamble_powers.append(float(cic_power))
        self._build_physical_candidate_groups()

    def cache_audit(self) -> dict:
        return {
            "reused_method_native_local_refinement_preamble_channels": int(
                self._reused_local_refinement_channel_count
            ),
        }

    def _build_physical_candidate_groups(self) -> None:
        """Collapse SP start/CFO aliases before multi-user paper operations.

        SP intentionally retains several synchronization hypotheses for one RF
        packet.  They are useful as independent decode attempts, but they must
        not be presented to CIC or MaLoRaGW as additional transmitters.  The
        grouping is blind: only the fine packet start is used, never CRC,
        manifest timing, node identity, or expected payload.
        """

        count = len(self.estimates)
        self._physical_group_by_index = [-1] * count
        groups: list[list[int]] = []
        tolerance = max(
            4.0 * float(getattr(self.cfg, "osr", 1.0)),
            0.125 * float(getattr(self.cfg, "samples_per_symbol", 8.0)),
        )
        for index in sorted(
            range(count), key=lambda value: float(self.estimates[value]["start_sample"])
        ):
            start = float(self.estimates[index]["start_sample"])
            channel = np.asarray(self._channels[index], dtype=np.complex128)
            compatible_group: list[int] | None = None
            best_start_distance = math.inf
            for group in groups:
                center = float(
                    np.median(
                        [float(self.estimates[value]["start_sample"]) for value in group]
                    )
                )
                start_distance = abs(start - center)
                if start_distance > tolerance:
                    continue
                reference = np.asarray(self._channels[group[0]], dtype=np.complex128)
                denominator = math.sqrt(
                    float(np.vdot(channel, channel).real)
                    * float(np.vdot(reference, reference).real)
                ) + EPS
                spatial_coherence = float(abs(np.vdot(reference, channel)) / denominator)
                if spatial_coherence >= 0.96 and start_distance < best_start_distance:
                    compatible_group = group
                    best_start_distance = start_distance
            if compatible_group is None:
                groups.append([index])
            else:
                compatible_group.append(index)
        representatives: list[int] = []
        for group_id, members in enumerate(groups):
            for index in members:
                self._physical_group_by_index[index] = int(group_id)
            representative = max(
                members,
                key=lambda index: (
                    float(np.vdot(self._channels[index], self._channels[index]).real),
                    float(self.estimates[index].get("confidence", 0.0)),
                ),
            )
            representatives.append(int(representative))
        self._physical_groups = groups
        self._physical_group_representatives = representatives

    def _index(self, est: dict) -> int:
        explicit = est.get("_comparison_candidate_index")
        if explicit is not None:
            index = int(explicit)
            if 0 <= index < len(self.estimates):
                return index
        for index, candidate in enumerate(self.estimates):
            if candidate is est:
                return index
        starts = np.asarray([float(item["start_sample"]) for item in self.estimates])
        return int(np.argmin(np.abs(starts - float(est["start_sample"]))))

    def _overlapping_indices(self, target_index: int) -> list[int]:
        target_start = float(self.estimates[target_index]["start_sample"])
        frame = float(self.cfg.frame_samples)
        return [
            index
            for index in self._physical_group_representatives
            if abs(float(self.estimates[index]["start_sample"]) - target_start) < frame
        ]

    def _payload_mixed(self, est: dict, symbol_index: int) -> np.ndarray:
        cache = getattr(self, "payload_spectrum_cache", None)
        if cache is None:
            return _physical_mixed(self.physical_samples, est, self.cfg, symbol_index)
        return cache.mixed_for(self.physical_samples, est, self.cfg, symbol_index)

    def _payload_spectra(
        self,
        est: dict,
        symbol_index: int,
        *,
        channel_count: int | None = None,
    ) -> np.ndarray:
        cache = getattr(self, "payload_spectrum_cache", None)
        if cache is None:
            source = (
                self.physical_samples
                if channel_count is None
                else self.physical_samples[: int(channel_count)]
            )
            return _physical_spectra(source, est, self.cfg, symbol_index)
        spectra = cache.spectra_for(self.physical_samples, est, self.cfg, symbol_index)
        return spectra if channel_count is None else spectra[: int(channel_count)]

    def decode_lorawan(self, est: dict) -> dict:
        """Strict standard single-channel LoRa payload receiver on Ch0.

        The selected comparison front end has already supplied this target.
        Every payload symbol is a single top-1 dechirp-FFT decision.  There is
        no alternate-channel choice, candidate projection, CRC-guided CFO
        retry, symbol repair, or interference cancellation.
        """

        bins: list[int] = []
        margins: list[float] = []
        for symbol_index in range(int(self.cfg.payload_symbol_count)):
            spectrum = self._payload_spectra(est, symbol_index, channel_count=1)[0]
            power = np.abs(spectrum) ** 2
            top2 = np.argpartition(power, -2)[-2:]
            top2 = top2[np.argsort(power[top2])[::-1]]
            chosen = int(top2[0])
            bins.append(chosen)
            second = float(power[top2[1]]) if power.size > 1 else 0.0
            margins.append(float(power[chosen] / (second + EPS)))
        return _result(
            "lorawan",
            bins,
            margins,
            {
                "cfg": self.cfg,
                "receiver_branch": "physical_ch0_only",
                "symbol_decision": "single_strongest_dechirp_fft_bin",
                "cfo_retry_count": 0,
                "crc_guided_retry": False,
                "symbol_repair": False,
                "interference_separation": False,
                "frontend_policy": _frontend_audit(est),
            },
        )

    def decode_mrc(self, est: dict) -> dict:
        """Strict fixed-MRC receiver using the selected front-end target."""

        target_index = self._index(est)
        channel = np.asarray(self._channels[target_index], dtype=np.complex128)
        channel = channel[: self.physical_samples.shape[0]]
        norm = math.sqrt(float(np.vdot(channel, channel).real)) + EPS
        weights = np.conj(channel / norm)
        bins: list[int] = []
        margins: list[float] = []
        for symbol_index in range(int(self.cfg.payload_symbol_count)):
            spectra = self._payload_spectra(est, symbol_index)
            combined = weights @ spectra[: weights.size]
            power = np.abs(combined) ** 2
            top2 = np.argpartition(power, -2)[-2:]
            top2 = top2[np.argsort(power[top2])[::-1]]
            chosen = int(top2[0])
            bins.append(chosen)
            second = float(power[top2[1]]) if power.size > 1 else 0.0
            margins.append(float(power[chosen] / (second + EPS)))
        return _result(
            "mrc",
            bins,
            margins,
            {
                "cfg": self.cfg,
                "receiver_branch": "physical_ch0_ch1_fixed_mrc",
                "symbol_decision": "single_strongest_fixed_mrc_dechirp_fft_bin",
                "channel_estimate_source": (
                    "shared_sp_physical_preamble_channel"
                    if est.get(
                        "shared_sp_mrc_channel",
                        est.get("shared_sp_physical_channel"),
                    )
                    is not None
                    else (
                        "own_mrc_preamble_measurement_at_fixed_sp_fine_sync"
                        if est.get(
                            "shared_sp_fine_sync_seed",
                            est.get("shared_sp_fine_sync", False),
                        )
                        else "native_mrc_preamble"
                    )
                ),
                "mrc_weights": [
                    [float(np.real(value)), float(np.imag(value))] for value in weights
                ],
                "cfo_retry_count": 0,
                "crc_guided_retry": False,
                "symbol_repair": False,
                "interference_separation": False,
                "frontend_policy": _frontend_audit(est),
            },
        )

    def decode_cic(self, est: dict) -> dict:
        """Fixed target MRC followed by CIC's unmodified ICSS/filter/SED path."""

        target_index = self._index(est)
        target_start = float(est["start_sample"])
        weights = mrc_weights(self._channels[target_index], self.physical_samples.shape[0])
        expected_power = self._cic_preamble_powers[target_index]
        expected_fractional = self._cic_fractional_cfos[target_index]
        if self.frontend_method != "mrc_cic":
            expected_fractional, expected_power = _cic_preamble_features(
                self.physical_samples, est, self.cfg, weights=weights
            )
        bins: list[int] = []
        margins: list[float] = []
        boundary_counts: list[int] = []
        candidate_counts: list[int] = []
        erasure_index: int | None = None

        for symbol_index in range(int(self.cfg.payload_symbol_count)):
            symbol_start = target_start + (
                float(self.cfg.payload_start_symbols) + symbol_index
            ) * self.cfg.samples_per_symbol
            mixed = weights @ self._payload_mixed(est, symbol_index)
            boundaries: list[int] = []
            for other_index in self._overlapping_indices(target_index):
                if (
                    self._physical_group_by_index[other_index]
                    == self._physical_group_by_index[target_index]
                ):
                    continue
                other_start = float(self.estimates[other_index]["start_sample"])
                if not (
                    other_start < symbol_start + self.cfg.samples_per_symbol
                    and other_start + self.cfg.frame_samples > symbol_start
                ):
                    continue
                relative = (other_start - symbol_start) % self.cfg.samples_per_symbol
                if self.cfg.osr <= relative <= self.cfg.samples_per_symbol - self.cfg.osr:
                    boundaries.append(int(round(relative)))
            boundaries = sorted(set(boundaries))
            boundary_counts.append(len(boundaries))

            icss = [_masked_cic_spectrum(mixed, self.cfg, 0, self.cfg.samples_per_symbol)]
            for boundary in boundaries:
                icss.append(_masked_cic_spectrum(mixed, self.cfg, 0, boundary))
                icss.append(
                    _masked_cic_spectrum(
                        mixed, self.cfg, boundary, self.cfg.samples_per_symbol
                    )
                )
            cic_spectrum = _intersection(icss)
            candidates = _local_peaks(cic_spectrum, ratio=2.0, limit=64)

            # CIC Sec. 5.7: +/-3 dB preamble-RSSI filter.  The 16x-FFT
            # fractional-CFO/Choir filter is disabled to match the official CIC
            # release, which ships that module commented out (Python/CIC_Demod.py
            # and Matlab/CIC_Demod.m); the previously used 0.25-bin threshold
            # erased a large fraction of valid symbols.
            _, peak_power = _fractional_offsets_and_power(
                mixed, self.cfg, candidates
            )
            keep = np.ones(candidates.size, dtype=bool)
            if expected_power > EPS:
                power_ratio = peak_power / expected_power
                keep &= (power_ratio >= 10.0 ** (-3.0 / 10.0)) & (
                    power_ratio <= 10.0 ** (3.0 / 10.0)
                )
            filtered = candidates[keep]
            if filtered.size == 0:
                erasure_index = int(symbol_index)
                break
            candidates = filtered
            candidate_counts.append(int(candidates.size))

            # CIC Eqs. 15--17: spectral intersections over ten sliding
            # half-symbol windows from the left and right edges, then min SED.
            half = self.cfg.samples_per_symbol // 2
            epsilon = max(self.cfg.osr, half // 10)
            left: list[np.ndarray] = []
            right: list[np.ndarray] = []
            for window_index in range(10):
                shift = window_index * epsilon
                left.append(
                    _masked_cic_spectrum(
                        mixed, self.cfg, shift, min(self.cfg.samples_per_symbol, shift + half)
                    )
                )
                right.append(
                    _masked_cic_spectrum(
                        mixed,
                        self.cfg,
                        max(0, self.cfg.samples_per_symbol - half - shift),
                        self.cfg.samples_per_symbol - shift,
                    )
                )
            sed = np.abs(_intersection(left)[candidates] - _intersection(right)[candidates])
            order = np.lexsort((-cic_spectrum[candidates], sed))
            chosen = int(candidates[int(order[0])])
            bins.append(chosen)
            if candidates.size > 1:
                sorted_sed = np.sort(sed)
                margins.append(float((sorted_sed[1] + EPS) / (sorted_sed[0] + EPS)))
            else:
                margins.append(1_000_000.0)

        return _result(
            "mrc_cic",
            bins,
            margins,
            {
                "cfg": self.cfg,
                "paper": "CIC SIGCOMM 2021",
                "receiver_branch": "physical_channels_target_fixed_mrc",
                "baseline_variant": "MRC+CIC",
                "mrc_weights": [[float(w.real), float(w.imag)] for w in weights],
                "preamble_features_domain": "same_target_mrc_as_payload",
                "icss_equation": 12,
                "sed_equations": [15, 16, 17],
                "capture_oversampling_factor": int(self.cfg.osr),
                "paper_prototype_oversampling_factor": 8,
                "fractional_cfo_fft_oversampling": 16,
                "fractional_cfo_filter_enabled": False,
                "fractional_cfo_tolerance_bins": None,
                "preamble_fractional_cfo_bins": float(expected_fractional),
                "rssi_tolerance_db": 3.0,
                "mean_interferer_boundaries": float(np.mean(boundary_counts)),
                "physical_candidate_group_count": len(self._physical_groups),
                "mean_candidates_after_filters": (
                    float(np.mean(candidate_counts)) if candidate_counts else 0.0
                ),
                "symbol_erasure_index": erasure_index,
                "frontend_policy": _frontend_audit(est),
            },
        )

    def decode_pcube(self, est: dict, *, grouping_policy: str = DEFAULT_PCUBE_POLICY) -> dict:
        """PCube 2-Rx / one-Rx-pair PDoA clustering decoder."""

        if grouping_policy != 'legacy_fixed_gate':
            from compare.PCube.soft_grouping import POLICY, TARGET_POLICY, CONSERVATIVE_POLICY, group_packet
            if grouping_policy not in (POLICY,TARGET_POLICY,CONSERVATIVE_POLICY):
                raise ValueError(f'Unknown PCube grouping policy: {grouping_policy}')
            target_index = self._index(est)
            representatives = [j for j in self._physical_group_representatives
                if float(self.estimates[j]['start_sample']) < float(est['start_sample'])+self.cfg.frame_samples
                and float(self.estimates[j]['start_sample'])+self.cfg.frame_samples > float(est['start_sample'])]
            target_group = self._physical_group_by_index[target_index]
            target_local = next(i for i,j in enumerate(representatives)
                if self._physical_group_by_index[j] == target_group)
            target_only = grouping_policy == TARGET_POLICY
            if target_only:
                representatives=[target_index]
                target_local=0
            spectra = [self._payload_spectra(est,q) for q in range(int(self.cfg.payload_symbol_count))]
            candidates = [_local_peaks(np.sum(abs(f)**2,axis=0),ratio=6.,limit=64) for f in spectra]
            bins,margins,grouping = group_packet(spectra,candidates,
                [self._pdoas[j] for j in representatives],
                [float(np.vdot(self._channels[j],self._channels[j]).real) for j in representatives],
                target_local,int(self.cfg.preamble_len),target_only=target_only,
                preserve_accepted=grouping_policy==CONSERVATIVE_POLICY)
            return _result('pcube',bins,margins,dict(cfg=self.cfg,paper='PCube MobiCom 2021',
                hardware_mode='2Rx_1RxPair',pdoa_equation=8,multi_pair_equation_9_available=False,
                grouping=grouping,mean_detected_fft_peaks=float(np.mean([len(c) for c in candidates])),
                frontend_policy=_frontend_audit(est)))

        target_index = self._index(est)
        target_pdoa = self._pdoas[target_index]
        bins: list[int] = []
        margins: list[float] = []
        candidate_counts: list[int] = []
        for symbol_index in range(int(self.cfg.payload_symbol_count)):
            spectra = self._payload_spectra(est, symbol_index)
            energy = np.sum(np.abs(spectra) ** 2, axis=0)
            candidates = _local_peaks(energy, ratio=6.0, limit=64)
            z_pair = spectra[0] * np.conj(spectra[1])
            rotated_evidence = np.real(
                z_pair[candidates] * np.exp(-1j * target_pdoa)
            )
            phase_distance = np.abs(
                np.angle(np.exp(1j * (np.angle(z_pair[candidates]) - target_pdoa)))
            )
            # Historical local approximation, preserved for paired regression
            # checks. Eq.9 does not specify this gate or this decision rule.
            clustered = phase_distance <= 0.5
            positive = (rotated_evidence > 0.0) & clustered
            if np.any(positive):
                positive_indices = np.flatnonzero(positive)
                local = int(
                    positive_indices[int(np.argmax(rotated_evidence[positive]))]
                )
            elif np.any(clustered):
                clustered_indices = np.flatnonzero(clustered)
                local = int(
                    clustered_indices[
                        int(np.argmax(rotated_evidence[clustered]))
                    ]
                )
            else:
                local = int(np.argmin(phase_distance))
            chosen = int(candidates[local])
            bins.append(chosen)
            candidate_counts.append(int(candidates.size))
            sorted_distance = np.sort(phase_distance)
            margins.append(
                float(sorted_distance[1] - sorted_distance[0])
                if sorted_distance.size > 1
                else math.pi
            )
        return _result(
            "pcube",
            bins,
            margins,
            {
                "cfg": self.cfg,
                "paper": "PCube MobiCom 2021",
                "hardware_mode": "2Rx_1RxPair",
                "pdoa_equation": 8,
                "multi_pair_equation_9_available": False,
                "target_pdoa_rad": float(target_pdoa),
                "mean_detected_fft_peaks": float(np.mean(candidate_counts)),
                "one_rx_pair_decision": (
                    "pdoa_cluster_then_max_positive_rotated_real_evidence"
                ),
                "pdoa_cluster_radius_rad": 0.5,
                "frontend_policy": _frontend_audit(est),
            },
        )

    def decode_maloragw(self, est: dict) -> dict:
        """MaLoRaGW uplink ZF plus frequency/time/channel-ratio clustering."""

        target_index = self._index(est)
        target_group = self._physical_group_by_index[target_index]
        antenna_count = int(self.physical_samples.shape[0])
        target_channel = self._channels[target_index]
        reference = target_channel[0] if abs(target_channel[0]) > EPS else 1.0 + 0.0j
        target_ratio = target_channel / reference
        bins: list[int] = []
        margins: list[float] = []
        removed_repeated_peak_count = 0
        candidate_counts: list[int] = []
        zf_selected_counts: list[int] = []
        zf_condition_numbers: list[float] = []
        zf_selected_indices: set[int] = set()
        target_zf_available_count = 0

        spectra_cache = [
            self._payload_spectra(est, symbol_index)
            for symbol_index in range(int(self.cfg.payload_symbol_count))
        ]
        for symbol_index, spectra in enumerate(spectra_cache):
            symbol_start = float(est["start_sample"]) + (
                float(self.cfg.payload_start_symbols) + symbol_index
            ) * self.cfg.samples_per_symbol
            active = [
                index
                for index in self._physical_group_representatives
                if float(self.estimates[index]["start_sample"])
                < symbol_start + self.cfg.samples_per_symbol
                and float(self.estimates[index]["start_sample"])
                + self.cfg.frame_samples
                > symbol_start
            ]
            strongest = sorted(
                active,
                key=lambda index: float(
                    np.vdot(self._channels[index], self._channels[index]).real
                ),
                reverse=True,
            )[: min(len(active), antenna_count)]
            if strongest:
                channel_matrix = np.column_stack(
                    [self._channels[index] for index in strongest]
                )
                zf = np.linalg.pinv(channel_matrix)
            else:
                channel_matrix = np.eye(antenna_count, dtype=np.complex128)
                zf = np.eye(antenna_count, dtype=np.complex128)
            target_zf_row = next(
                (
                    row_index
                    for row_index, candidate_index in enumerate(strongest)
                    if self._physical_group_by_index[candidate_index] == target_group
                ),
                None,
            )
            zf_selected_counts.append(len(strongest))
            zf_selected_indices.update(int(value) for value in strongest)
            if target_zf_row is not None:
                target_zf_available_count += 1
            if channel_matrix.size:
                zf_condition_numbers.append(float(np.linalg.cond(channel_matrix)))
            projected = zf @ spectra
            candidate_parts = [
                _local_peaks(np.abs(projected[row]) ** 2, ratio=6.0, limit=32)
                for row in range(projected.shape[0])
            ]
            candidate_parts.append(
                _local_peaks(np.sum(np.abs(spectra) ** 2, axis=0), ratio=6.0, limit=32)
            )
            candidates = np.unique(np.concatenate(candidate_parts)).astype(np.int64)

            denominator = np.where(np.abs(spectra[0, candidates]) > EPS, spectra[0, candidates], 1.0)
            ratios = spectra[:, candidates] / denominator[None, :]
            ratio_distance = np.linalg.norm(ratios - target_ratio[:, None], axis=0) / (
                1.0 + np.linalg.norm(target_ratio)
            )

            # Target CFO/CTO were removed before the FFT.  A 16x FFT measures
            # the remaining per-peak fractional frequency used by Sec. 4.4.
            target_norm = math.sqrt(float(np.vdot(target_channel, target_channel).real)) + EPS
            beam = np.conj(target_channel / target_norm) @ self._payload_mixed(
                est, symbol_index
            )
            fractional, _ = _fractional_offsets_and_power(
                beam, self.cfg, candidates
            )

            # A chirp cut by a target-aligned window produces the same peak in
            # two consecutive windows.  Remove such a peak when its spatial
            # channel ratio also says it is not the target (paper Sec. 4.4-i).
            repeated = np.zeros(candidates.size, dtype=bool)
            for adjacent_index in (symbol_index - 1, symbol_index + 1):
                if adjacent_index < 0 or adjacent_index >= len(spectra_cache):
                    continue
                adjacent_energy = np.sum(np.abs(spectra_cache[adjacent_index]) ** 2, axis=0)
                adjacent_peaks = set(int(value) for value in _local_peaks(adjacent_energy, ratio=6.0, limit=64))
                repeated |= np.asarray(
                    [
                        any((int(candidate) + delta) % self.cfg.m in adjacent_peaks for delta in (-1, 0, 1))
                        for candidate in candidates
                    ],
                    dtype=bool,
                )
            removable = repeated & (ratio_distance > 0.15)
            keep = ~removable
            if np.any(keep):
                removed_repeated_peak_count += int(np.count_nonzero(removable))
                candidates = candidates[keep]
                ratio_distance = ratio_distance[keep]
                fractional = fractional[keep]

            feature_distance = ratio_distance + np.abs(fractional)
            if target_zf_row is not None:
                projected_energy = np.abs(projected[target_zf_row, candidates]) ** 2
            else:
                target_norm = math.sqrt(
                    float(np.vdot(target_channel, target_channel).real)
                ) + EPS
                target_projected = np.conj(target_channel / target_norm) @ spectra
                projected_energy = np.abs(target_projected[candidates]) ** 2
            # After feature-based membership filtering, select the strongest
            # peak in the target ZF stream.  Summing all ZF rows would undo the
            # user separation that MaLoRaGW performs.
            target_score = projected_energy / (1.0 + 4.0 * feature_distance ** 2)
            local = int(np.argmax(target_score))
            chosen = int(candidates[local])
            bins.append(chosen)
            candidate_counts.append(int(candidates.size))
            sorted_distance = np.sort(feature_distance)
            margins.append(
                float(sorted_distance[1] - sorted_distance[0])
                if sorted_distance.size > 1
                else 1.0
            )

        return _result(
            "maloragw",
            bins,
            margins,
            {
                "cfg": self.cfg,
                "paper": "MaLoRaGW SenSys 2022",
                "direction": "uplink_only",
                "antenna_count": antenna_count,
                "overlapping_candidate_count": len(
                    self._overlapping_indices(target_index)
                ),
                "physical_candidate_group_count": len(self._physical_groups),
                "zf_selected_count": (
                    float(np.mean(zf_selected_counts)) if zf_selected_counts else 0.0
                ),
                "zf_selected_candidate_indices": sorted(zf_selected_indices),
                "zf_formula": "(H^H H)^-1 H^H (Moore-Penrose numerical evaluation)",
                "zf_target_row_available_fraction": (
                    float(target_zf_available_count) / len(spectra_cache)
                    if spectra_cache
                    else 0.0
                ),
                "channel_matrix_condition_number": (
                    float(np.median(zf_condition_numbers))
                    if zf_condition_numbers
                    else None
                ),
                "peak_features": ["fractional_frequency_and_time", "channel_ratio"],
                "target_peak_score": (
                    "target_zf_row_energy/(1+4*joint_feature_distance^2)"
                ),
                "removed_repeated_peak_count": int(removed_repeated_peak_count),
                "mean_detected_fft_peaks": float(np.mean(candidate_counts)),
                "frontend_policy": _frontend_audit(est),
            },
        )

    def decode_all(self, est: dict) -> list[dict]:
        return [
            self.decode_lorawan(est),
            self.decode_mrc(est),
            self.decode_cic(est),
            self.decode_pcube(est),
            self.decode_maloragw(est),
        ]
