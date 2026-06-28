"""Grid helpers for future profile generation."""

from __future__ import annotations

import numpy as np


def log_radial_grid(r_min: float, r_max: float, n_points: int) -> np.ndarray:
    if r_min <= 0 or r_max <= r_min:
        raise ValueError("expected 0 < r_min < r_max")
    if n_points < 2:
        raise ValueError("n_points must be at least 2")
    return np.exp(np.linspace(np.log(r_min), np.log(r_max), n_points))


def gauss_legendre_log_grid(
    r_min: float, r_max: float, n_points: int
) -> tuple[np.ndarray, np.ndarray]:
    if r_min <= 0 or r_max <= r_min:
        raise ValueError("expected 0 < r_min < r_max")
    if n_points < 2:
        raise ValueError("n_points must be at least 2")
    nodes, weights = np.polynomial.legendre.leggauss(n_points)
    t_min = np.log(r_min)
    t_max = np.log(r_max)
    t = 0.5 * (t_max - t_min) * nodes + 0.5 * (t_max + t_min)
    w_t = 0.5 * (t_max - t_min) * weights
    return np.exp(t), w_t
