"""Grid helpers for stored radial profiles and independent QA quadrature."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

PROFILE_R_MIN = 1.0e-6
PROFILE_R_MAX = 80.0
PROFILE_N_R = 1200
PROFILE_N_ANG = 110
QA_R_MIN = 1.0e-7
QA_R_MAX = 120.0
QA_N_R = 400
QA_N_ANG = 110


def log_radial_grid(r_min: float, r_max: float, n_points: int) -> NDArray[np.float64]:
    if r_min <= 0 or r_max <= r_min:
        raise ValueError("expected 0 < r_min < r_max")
    if n_points < 2:
        raise ValueError("n_points must be at least 2")
    return np.exp(np.linspace(np.log(r_min), np.log(r_max), n_points))


def default_profile_grid() -> NDArray[np.float64]:
    return log_radial_grid(PROFILE_R_MIN, PROFILE_R_MAX, PROFILE_N_R)


def gauss_legendre_log_grid(
    r_min: float, r_max: float, n_points: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return nodes ``r`` and weights ``w_t`` for quadrature in ``t = log(r)``.

    Electron count from a spherical average is computed as
    ``sum(w_t * 4*pi*r**3*rho(r))``.
    """

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


def default_qa_grid() -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    return gauss_legendre_log_grid(QA_R_MIN, QA_R_MAX, QA_N_R)


def fibonacci_angular_grid(n_points: int) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return a deterministic unit-sphere grid and normalized weights."""

    if n_points < 4:
        raise ValueError("n_points must be at least 4")
    i = np.arange(n_points, dtype=float)
    z = 1.0 - 2.0 * (i + 0.5) / n_points
    theta = np.arccos(z)
    phi = math.pi * (1.0 + 5.0**0.5) * (i + 0.5)
    x = np.sin(theta) * np.cos(phi)
    y = np.sin(theta) * np.sin(phi)
    directions = np.column_stack([x, y, z])
    weights = np.ones(n_points, dtype=float) / n_points
    return directions, weights


def pyscf_angular_grid(n_points: int) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return a PySCF angular grid; requires PySCF at call time only."""

    try:
        from pyscf.dft.gen_grid import MakeAngularGrid  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("PySCF angular grid requested but PySCF is not installed") from exc

    grid = MakeAngularGrid(n_points)
    directions = np.asarray(grid[:, :3], dtype=float)
    weights = np.asarray(grid[:, 3], dtype=float)
    weights = weights / weights.sum()
    return directions, weights


def angular_grid(
    n_points: int = PROFILE_N_ANG, *, prefer_pyscf: bool = True
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return an angular grid, falling back to Fibonacci when needed.

    PySCF only supports selected Lebedev grid sizes.  For valid custom sizes that
    PySCF does not know, use the deterministic Fibonacci grid instead of failing
    after an expensive SCF calculation has already completed.
    """

    if prefer_pyscf:
        try:
            return pyscf_angular_grid(n_points)
        except (RuntimeError, ValueError):
            pass
    return fibonacci_angular_grid(n_points)


def weighted_mean_and_std(
    values: NDArray[np.float64], weights: NDArray[np.float64]
) -> tuple[float, float]:
    w = np.asarray(weights, dtype=float)
    if w.ndim != 1 or w.size == 0:
        raise ValueError("weights must be a nonempty 1D array")
    w = w / w.sum()
    arr = np.asarray(values, dtype=float)
    if arr.shape != w.shape:
        raise ValueError("values and weights must have the same shape")
    mean = float(np.sum(w * arr))
    var = float(np.sum(w * (arr - mean) ** 2))
    return mean, math.sqrt(max(var, 0.0))
