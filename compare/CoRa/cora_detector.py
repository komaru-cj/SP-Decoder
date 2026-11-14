"""Target MRC followed by the CoRa PMD/HPD Bayesian LoRa symbol detector.

This is the experiment-facing implementation of Section III of the CoRa
paper.  It intentionally preserves the complete symbol path used by the
authors' v2 artifact:

* estimate the expected peak magnitude from all eight preamble symbols;
* calculate an ordinary dechirped FFT and the half-period phase-inverted FFT;
* form HPD and PMD for every FFT bin (there is no peak preselection);
* quantize both features on the published 200 x 200 nearest-neighbour grid;
* apply the consecutive-symbol Bayesian classifier from Equation (2); and
* choose the maximum posterior over every one of the 2**SF bins.

The adapter accepts the repository's arbitrary integer oversampling factors
(3 for BW250 and 6 for BW125).  CoRa itself still operates at one complex
sample per LoRa chip, exactly as the paper and official artifact do.
"""

from __future__ import annotations

from dataclasses import dataclass
import pickle
from pathlib import Path
import time

import numpy as np

from compare.mrc_input import target_mrc_input

from lora_mrc_sp_core import (
    compensate_symbol_window,
    instantaneous_chirp,
    lora_symbol_fft,
)


EPS = 1e-30
GRID_BINS = 200
FEATURE_MAX = 1.0 - 1.0 / GRID_BINS


@dataclass(frozen=True)
class CoRaSymbolResult:
    symbol_bins: list[int]
    expected_peak_magnitude: float
    mean_bayes_margin: float
    min_bayes_margin: float
    stage_seconds: dict[str, float]
    mrc_weights: tuple[complex, ...] = ()
    mrc_channel_source: str = ""


class CoRaDetector:
    """CoRa detector backed by the authors' published posterior grid."""

    def __init__(self, posterior_path: Path | str):
        path = Path(posterior_path)
        with path.open("rb") as handle:
            posterior = pickle.load(handle)
        posterior = np.asarray(posterior, dtype=np.float64)
        if posterior.shape != (GRID_BINS, GRID_BINS):
            raise ValueError(
                f"CoRa posterior must be {GRID_BINS}x{GRID_BINS}, got "
                f"{posterior.shape}"
            )
        if not np.all(np.isfinite(posterior)) or np.any(posterior < 0.0):
            raise ValueError("CoRa posterior contains invalid probabilities")
        self.posterior = posterior

    @staticmethod
    def _effective_sync(estimate: dict) -> tuple[float, float]:
        start = float(estimate["start_sample"]) + float(
            estimate.get("sto_samples_sp", estimate.get("sto_samples", 0.0))
        )
        cfo = float(
            estimate.get(
                "cfo_bins_sp",
                estimate.get("continuous_cfo_bins", estimate.get("cfo_bins", 0.0)),
            )
        )
        return start, cfo

    @staticmethod
    def _dechirped_chips(
        samples: np.ndarray,
        *,
        symbol_start: float,
        cfo_bins: float,
        cfg,
        downchirp: np.ndarray,
    ) -> np.ndarray:
        """Return scalar MRC-input dechirped samples at the LoRa chip rate."""

        compensated = compensate_symbol_window(
            samples[:1], symbol_start, cfo_bins, cfg, sto_samples=0.0
        )[0]
        return np.asarray(compensated * downchirp, dtype=np.complex128)[
            :: cfg.osr
        ][: cfg.m]

    def expected_peak_magnitude(
        self,
        samples: np.ndarray,
        estimate: dict,
        cfg,
    ) -> float:
        """TnB-sync preamble amplitude statistic consumed by CoRa PMD."""

        start, cfo = self._effective_sync(estimate)
        downchirp = instantaneous_chirp(0, cfg, up=False)
        magnitudes: list[float] = []
        for preamble_index in range(int(cfg.preamble_len)):
            symbol_start = start + preamble_index * cfg.samples_per_symbol
            if (
                symbol_start < 0.0
                or symbol_start + cfg.samples_per_symbol > samples.shape[1]
            ):
                continue
            compensated = compensate_symbol_window(
                samples[:1], symbol_start, cfo, cfg, sto_samples=0.0
            )[0]
            spectrum = lora_symbol_fft(compensated * downchirp, cfg)
            # After the supplied integer/fractional CFO compensation, the
            # target preamble is the zero-frequency waveform.
            magnitudes.append(float(abs(spectrum[0])))
        if not magnitudes:
            return 0.0
        return float(np.mean(np.asarray(magnitudes, dtype=np.float64)))

    @staticmethod
    def calculate_features(
        dechirped_chips: np.ndarray,
        expected_peak_magnitude: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (HPD, PMD, ordinary magnitude spectra) for all symbols/bins."""

        chips = np.asarray(dechirped_chips, dtype=np.complex128)
        if chips.ndim != 2:
            raise ValueError("dechirped_chips must have shape (symbols, bins)")
        mask = np.ones(chips.shape[-1], dtype=np.float64)
        mask[chips.shape[-1] // 2 :] = -1.0
        ordinary = np.abs(np.fft.fft(chips, axis=-1))
        inverted = np.abs(np.fft.fft(chips * mask[None, :], axis=-1))

        # Paper Section III-A: Z=min(X,Y), HPD=Z/X.  The official artifact
        # subsequently clips at 199/200 for nearest-neighbour indexing.
        hpd = np.minimum(ordinary, inverted) / np.maximum(ordinary, EPS)
        peak = max(float(expected_peak_magnitude), EPS)
        pmd = np.abs(ordinary - peak) / peak
        return hpd, pmd, ordinary

    def detect(
        self,
        samples: np.ndarray,
        estimate: dict,
        cfg,
    ) -> CoRaSymbolResult:
        """Apply fixed physical-target MRC before the complete CoRa path."""
        started = time.perf_counter_ns()
        combined, local, weights, source = target_mrc_input(samples, estimate, cfg)
        mrc_seconds = (time.perf_counter_ns() - started) / 1e9
        result = self._detect_single_channel(combined, local, cfg)
        stages = dict(result.stage_seconds)
        stages["mrc_preparation"] = mrc_seconds
        stages["total"] += mrc_seconds
        return CoRaSymbolResult(
            result.symbol_bins, result.expected_peak_magnitude,
            result.mean_bayes_margin, result.min_bayes_margin, stages,
            tuple(complex(w) for w in weights), source,
        )

    def _detect_single_channel(
        self,
        samples: np.ndarray,
        estimate: dict,
        cfg,
    ) -> CoRaSymbolResult:
        """Demodulate all explicit-header/payload symbols for one sync target."""

        total_started = time.perf_counter_ns()
        stage_seconds: dict[str, float] = {}
        start, cfo = self._effective_sync(estimate)

        started = time.perf_counter_ns()
        peak = self.expected_peak_magnitude(samples, estimate, cfg)
        stage_seconds["preamble_peak_estimation"] = (
            time.perf_counter_ns() - started
        ) / 1e9
        if peak <= 0.0:
            stage_seconds["total"] = (time.perf_counter_ns() - total_started) / 1e9
            return CoRaSymbolResult([], 0.0, 0.0, 0.0, stage_seconds)

        # The authors prepend one complete symbol to evaluate the second
        # factor in Eq. (2).  For the first payload symbol this is the symbol
        # beginning one symbol before the standard 12.25-symbol payload edge.
        relative_symbols = (
            float(cfg.payload_start_symbols)
            - 1.0
            + np.arange(int(cfg.payload_symbol_count) + 1, dtype=np.float64)
        )
        downchirp = instantaneous_chirp(0, cfg, up=False)
        chips: list[np.ndarray] = []
        started = time.perf_counter_ns()
        for relative in relative_symbols:
            symbol_start = start + float(relative) * cfg.samples_per_symbol
            if (
                symbol_start < 0.0
                or symbol_start + cfg.samples_per_symbol > samples.shape[1]
            ):
                stage_seconds["dechirp"] = (
                    time.perf_counter_ns() - started
                ) / 1e9
                stage_seconds["total"] = (
                    time.perf_counter_ns() - total_started
                ) / 1e9
                return CoRaSymbolResult([], peak, 0.0, 0.0, stage_seconds)
            chips.append(
                self._dechirped_chips(
                    samples,
                    symbol_start=symbol_start,
                    cfo_bins=cfo,
                    cfg=cfg,
                    downchirp=downchirp,
                )
            )
        chip_matrix = np.asarray(chips, dtype=np.complex128)
        stage_seconds["dechirp"] = (time.perf_counter_ns() - started) / 1e9

        started = time.perf_counter_ns()
        hpd, pmd, _ = self.calculate_features(chip_matrix, peak)
        stage_seconds["feature_extraction"] = (
            time.perf_counter_ns() - started
        ) / 1e9

        started = time.perf_counter_ns()
        h_index = np.floor(np.minimum(hpd, FEATURE_MAX) * GRID_BINS).astype(
            np.int64
        )
        p_index = np.floor(np.minimum(pmd, FEATURE_MAX) * GRID_BINS).astype(
            np.int64
        )
        complete_probability = self.posterior[h_index, p_index]
        bayes = complete_probability[1:] * (1.0 - complete_probability[:-1])
        stage_seconds["bayesian_classifier"] = (
            time.perf_counter_ns() - started
        ) / 1e9

        started = time.perf_counter_ns()
        bins = np.argmax(bayes, axis=1).astype(np.int64)
        if bayes.shape[1] > 1:
            top_two = np.partition(bayes, -2, axis=1)[:, -2:]
            margins = np.maximum(top_two[:, 1] - top_two[:, 0], 0.0)
        else:
            margins = bayes[:, 0]
        stage_seconds["argmax"] = (time.perf_counter_ns() - started) / 1e9
        stage_seconds["total"] = (time.perf_counter_ns() - total_started) / 1e9
        return CoRaSymbolResult(
            symbol_bins=[int(value) for value in bins],
            expected_peak_magnitude=peak,
            mean_bayes_margin=float(np.mean(margins)) if margins.size else 0.0,
            min_bayes_margin=float(np.min(margins)) if margins.size else 0.0,
            stage_seconds=stage_seconds,
        )
