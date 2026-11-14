#!/usr/bin/env python3
"""Calculate and render the LoRa chirp/dechirp/FFT motivation figure.

The figure is deliberately computed rather than sketched.  Each row starts
from the discrete LoRa upchirp

    c[n] = exp(j 2π (n²/(2M) - n/2)),  M = 2**SF,

and forms symbols x_s[n] = c[n] exp(j 2π s n/M).  In the concurrent row the
target-aligned window contains two asynchronously starting interferers.  Their
symbol boundaries, CFOs, phases, and gains live in the editable CSV beside
this file.  The plots then show the STFT energy of the received window, the
STFT energy after multiplication by the target downchirp, and the actual
M-point FFT magnitude of that same dechirped vector.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyArrowPatch, Rectangle


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUTPUT = HERE / "output"
SETTINGS_FILE = DATA / "fig_lora_css_demodulation_settings.csv"
PARAMETERS_FILE = DATA / "fig_lora_css_demodulation_parameters.csv"

TARGET_BOX = "#E53935"
INK = "#111111"
ENERGY = LinearSegmentedColormap.from_list(
    "black_yellow_energy",
    [(0.00, "#000000"), (0.35, "#171717"), (0.66, "#705400"), (0.86, "#FFC21A"), (1.00, "#FFF6C6")],
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def read_settings() -> dict[str, float]:
    return {row["key"]: float(row["value"]) for row in read_csv(SETTINGS_FILE)}


def upchirp(symbol: int, sample: np.ndarray, m: int) -> np.ndarray:
    """Return the exact discrete LoRa symbol waveform at local sample indices."""

    q = np.asarray(sample, dtype=float)
    phase = 2.0 * np.pi * (q * q / (2.0 * m) - q / 2.0 + symbol * q / m)
    return np.exp(1j * phase)


def component_waveform(row: dict[str, str], samples: np.ndarray, m: int) -> np.ndarray:
    """One packet contribution in the target packet's symbol window.

    ``start_sample`` is the interferer's actual symbol boundary relative to
    the beginning of the target window.  Thus samples before it come from the
    tail of ``symbol_before`` and later samples from ``symbol_after``.
    """

    start = int(row["start_sample"])
    q = np.mod(samples - start, m)
    symbols = np.where(samples < start, int(row["symbol_before"]), int(row["symbol_after"]))
    phase = 2.0 * np.pi * (q * q / (2.0 * m) - q / 2.0 + symbols * q / m)
    cfo = float(row["cfo_bins"])
    gain = float(row["amplitude"]) * np.exp(1j * float(row["phase_rad"]))
    return gain * np.exp(1j * phase) * np.exp(1j * 2.0 * np.pi * cfo * samples / m)


def stft_energy(signal: np.ndarray, m: int, window_size: int, hop: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Short-time energy spectrum in LoRa FFT-bin frequency units."""

    starts = np.arange(0, len(signal) - window_size + 1, hop, dtype=int)
    taper = np.hanning(window_size)
    transform = np.asarray(
        [np.fft.fftshift(np.fft.fft(signal[start:start + window_size] * taper, n=m)) for start in starts]
    ).T
    energy = np.abs(transform) ** 2 / max(float(np.sum(taper**2)), 1e-12)
    frequencies = np.fft.fftshift(np.fft.fftfreq(m, d=1.0 / m))
    times = (starts + (window_size - 1) / 2.0) / m
    return times, frequencies, energy


def target_ridge(symbol: int, m: int) -> tuple[np.ndarray, np.ndarray]:
    """The instantaneous frequency ridge implied by the same discrete chirp."""

    samples = np.arange(m)
    frequencies = np.mod(samples + 0.5 + symbol, m) - m / 2.0
    plotted = frequencies.astype(float)
    jumps = np.flatnonzero(np.abs(np.diff(frequencies)) > m / 2.0)
    plotted[jumps + 1] = np.nan  # do not draw a false vertical line at spectral wrap.
    return samples / m, plotted


def scenario_signal(
    scenario: str, parameters: list[dict[str, str]], m: int, noise_std: float, seed: int
) -> tuple[np.ndarray, np.ndarray, int]:
    selected = [row for row in parameters if row["scenario"] == scenario]
    target = next(row for row in selected if row["component"] == "target")
    samples = np.arange(m)
    clean = sum((component_waveform(row, samples, m) for row in selected), start=np.zeros(m, dtype=complex))
    rng = np.random.default_rng(seed)
    noise = noise_std / np.sqrt(2.0) * (rng.standard_normal(m) + 1j * rng.standard_normal(m))
    received = clean + noise
    downchirp = np.conj(upchirp(0, samples, m))
    dechirped = received * downchirp
    return received, dechirped, int(target["symbol_after"])


def dark_axis(axis) -> None:
    axis.set_facecolor("#000000")
    for spine in axis.spines.values():
        spine.set_color(INK)
        spine.set_linewidth(1.0)
    axis.tick_params(direction="in", color=INK, labelcolor=INK, length=4, width=1.0)
    axis.grid(False)


def draw_energy(axis, times: np.ndarray, frequencies: np.ndarray, relative_db: np.ndarray, floor_db: float) -> None:
    axis.imshow(
        relative_db,
        origin="lower",
        aspect="auto",
        interpolation="nearest",
        extent=(times[0], times[-1], frequencies[0], frequencies[-1]),
        cmap=ENERGY,
        vmin=floor_db,
        vmax=0.0,
    )
    dark_axis(axis)


def draw_fft(axis, magnitude: np.ndarray, target_bin: int, *, concurrent: bool) -> None:
    bins = np.arange(len(magnitude))
    normalized = magnitude / max(float(magnitude.max()), 1e-12)
    axis.set_facecolor("#000000")
    axis.fill_between(bins, normalized, color="#E3A600", alpha=0.72, linewidth=0)
    axis.plot(bins, normalized, color="#FFE06A", linewidth=0.8)
    dark_axis(axis)
    axis.set_xlim(0, len(bins) - 1)
    axis.set_ylim(0, 1.12)
    axis.set_xticks([0, target_bin, len(bins) - 1])
    axis.set_xlabel("FFT bin k")
    axis.set_ylabel("normalized magnitude")

    target_height = normalized[target_bin]
    axis.add_patch(
        Rectangle((target_bin - 3.3, 0.0), 6.6, max(target_height, 0.035), fill=False, edgecolor=TARGET_BOX, linewidth=1.8, zorder=5)
    )
    axis.annotate(
        "target bin",
        xy=(target_bin, max(target_height, 0.035)),
        xytext=(target_bin + 24, 0.82),
        color=TARGET_BOX,
        fontsize=8,
        arrowprops={"arrowstyle": "-", "color": TARGET_BOX, "lw": 1.1},
    )

    if concurrent:
        winner = int(np.argmax(magnitude))
        axis.plot(winner, normalized[winner], marker="*", markersize=10, color="#FFF6C6", markeredgecolor=INK, zorder=6)
        axis.annotate(
            f"largest bin {winner}",
            xy=(winner, normalized[winner]),
            xytext=(winner + 72, 1.02),
            color="#FFF6C6",
            fontsize=8,
            arrowprops={"arrowstyle": "-", "color": "#FFF6C6", "lw": 1.1},
        )


def add_arrow(fig, left_axis, right_axis) -> None:
    left = left_axis.get_position()
    right = right_axis.get_position()
    y = 0.5 * (left.y0 + left.y1)
    arrow = FancyArrowPatch(
        (left.x1 + 0.006, y), (right.x0 - 0.006, y),
        transform=fig.transFigure, arrowstyle="simple", mutation_scale=12,
        color=INK, linewidth=0,
    )
    fig.add_artist(arrow)


def render() -> None:
    settings = read_settings()
    sf = int(settings["sf"])
    m = 2**sf
    window_size = int(settings["stft_window_samples"])
    hop = int(settings["stft_hop_samples"])
    floor_db = float(settings["energy_floor_db"])
    parameters = read_csv(PARAMETERS_FILE)

    simulations = {}
    for index, scenario in enumerate(("single", "concurrent")):
        received, dechirped, target_bin = scenario_signal(
            scenario, parameters, m, settings["noise_std"], int(settings["random_seed"]) + index
        )
        raw_tf = stft_energy(received, m, window_size, hop)
        dechirped_tf = stft_energy(dechirped, m, window_size, hop)
        spectrum = np.abs(np.fft.fft(dechirped))
        simulations[scenario] = (raw_tf, dechirped_tf, spectrum, target_bin)

    global_peak = max(
        float(energy.max())
        for scenario in simulations.values()
        for energy in (scenario[0][2], scenario[1][2])
    )

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.labelsize": 11})
    fig, axes = plt.subplots(2, 3, figsize=(12.0, 9.0))  # Exact 4:3 output.
    fig.subplots_adjust(left=0.14, right=0.985, bottom=0.09, top=0.91, wspace=0.34, hspace=0.40)

    headings = ("received LoRa time–frequency energy", "after target dechirping", f"{m}-point FFT magnitude")
    for axis, heading in zip(axes[0], headings):
        axis.set_title(heading, color=INK, pad=10, fontsize=11)

    for row_index, scenario in enumerate(("single", "concurrent")):
        raw_tf, dechirped_tf, magnitude, target_bin = simulations[scenario]
        raw_time, raw_frequency, raw_energy = raw_tf
        de_time, de_frequency, de_energy = dechirped_tf
        raw_db = 10.0 * np.log10(np.maximum(raw_energy, 1e-15) / global_peak)
        de_db = 10.0 * np.log10(np.maximum(de_energy, 1e-15) / global_peak)

        draw_energy(axes[row_index, 0], raw_time, raw_frequency, raw_db, floor_db)
        draw_energy(axes[row_index, 1], de_time, de_frequency, de_db, floor_db)
        draw_fft(axes[row_index, 2], magnitude, target_bin, concurrent=(scenario == "concurrent"))

        axes[row_index, 0].set_ylabel("relative frequency (FFT bins)")
        axes[row_index, 0].set_xlabel("time in target window ($T_s$)")
        axes[row_index, 0].set_yticks([-m / 2, 0, m / 2], [r"$-B/2$", "0", r"$+B/2$"])
        axes[row_index, 0].set_xticks([0.0, 0.5, 1.0], ["0", r"$T_s/2$", r"$T_s$"])

        axes[row_index, 1].set_ylabel("dechirped frequency (FFT bins)")
        axes[row_index, 1].set_xlabel("time in target window ($T_s$)")
        axes[row_index, 1].set_yticks([-m / 2, 0, target_bin, m / 2])
        axes[row_index, 1].set_xticks([0.0, 0.5, 1.0], ["0", r"$T_s/2$", r"$T_s$"])

        axes[row_index, 0].text(
            0.025, 0.95,
            "single packet" if scenario == "single" else "concurrent packets",
            transform=axes[row_index, 0].transAxes,
            color="#FFF6C6",
            fontsize=10,
            weight="bold",
            va="top",
            bbox={"facecolor": "#000000", "edgecolor": "none", "alpha": 0.72, "pad": 1.7},
        )

        if scenario == "concurrent":
            ridge_time, ridge_frequency = target_ridge(target_bin, m)
            # The red outline follows the target's exact cyclic upchirp ridge;
            # it is annotation only and does not alter the energy calculation.
            axes[row_index, 0].plot(ridge_time, ridge_frequency, color=TARGET_BOX, linewidth=1.7, zorder=5)
            axes[row_index, 1].add_patch(
                Rectangle((0.0, target_bin - 4.2), 1.0, 8.4, fill=False, edgecolor=TARGET_BOX, linewidth=1.7, zorder=5)
            )

        add_arrow(fig, axes[row_index, 0], axes[row_index, 1])
        add_arrow(fig, axes[row_index, 1], axes[row_index, 2])

    fig.text(0.025, 0.70, "single packet", ha="left", va="center", fontsize=13, color=INK, weight="bold")
    fig.text(0.025, 0.30, "concurrent packets", ha="left", va="center", fontsize=13, color=INK, weight="bold")
    fig.text(0.50, 0.025, "Black → yellow: energy (common dB scale); red outline: synchronized target symbol", ha="center", fontsize=9, color=INK)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf"):
        fig.savefig(OUTPUT / f"fig_lora_css_demodulation.{suffix}", dpi=200, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    render()
