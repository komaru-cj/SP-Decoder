#!/usr/bin/env python3
"""Render all 33 independent single-panel figures after ``prepare_data.py``."""

from plots import PLOTS, render


if __name__ == "__main__":
    for name in PLOTS:
        render(name)
    print(f"Rendered {len(PLOTS)} single-panel figures.")
