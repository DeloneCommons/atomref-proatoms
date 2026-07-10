"""Profile metadata helpers and radial-density evaluation utilities."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..dataio.schemas import (
    DENSITY_MODEL,
    PROFILE_METADATA_SCHEMA_VERSION,
    REQUIRED_PROFILE_METADATA_FIELDS,
    REQUIRED_PROFILE_METHOD_FIELDS,
)
from .grids import (
    QA_N_ANG,
    QA_N_R,
    QA_R_MAX,
    QA_R_MIN,
    angular_grid,
    default_profile_grid,
    gauss_legendre_log_grid,
    weighted_mean_and_std,
)

DEFAULT_DENSITY_CUTOFFS = (0.003, 0.001, 0.0001)


def radius_at_density(
    r_bohr: Sequence[float], rho_e_bohr3: Sequence[float], cutoff: float
) -> float:
    """Interpolate the outermost radius where ``rho`` reaches ``cutoff``.

    The function assumes a radial profile sampled from small to large radius and returns the
    outermost outward crossing from ``rho >= cutoff`` to ``rho <= cutoff``. Interpolation is
    linear in ``log(rho)`` when both neighboring densities are positive, which is stable for
    tail radii. It raises ``ValueError`` when the profile never crosses the cutoff.
    """

    if cutoff <= 0:
        raise ValueError("cutoff must be positive")
    if len(r_bohr) != len(rho_e_bohr3):
        raise ValueError("r_bohr and rho_e_bohr3 must have the same length")
    if len(r_bohr) < 2:
        raise ValueError("at least two profile points are required")

    radii = [float(value) for value in r_bohr]
    rho = [float(value) for value in rho_e_bohr3]
    if any(not math.isfinite(value) for value in radii + rho):
        raise ValueError("profile contains non-finite values")
    if any(radii[i] >= radii[i + 1] for i in range(len(radii) - 1)):
        raise ValueError("r_bohr must be strictly increasing")

    if rho[-1] == cutoff:
        return radii[-1]

    for i in range(len(rho) - 2, -1, -1):
        left = rho[i]
        right = rho[i + 1]
        if left == cutoff:
            return radii[i]
        if left >= cutoff >= right:
            if left > 0 and right > 0 and left != right:
                log_left = math.log(left)
                log_right = math.log(right)
                frac = (math.log(cutoff) - log_left) / (log_right - log_left)
            elif left != right:
                frac = (cutoff - left) / (right - left)
            else:
                frac = 0.0
            return radii[i] + frac * (radii[i + 1] - radii[i])
    raise ValueError(f"profile does not cross cutoff {cutoff}")


def derived_radii(
    r_bohr: Sequence[float],
    rho_e_bohr3: Sequence[float],
    cutoffs: Sequence[float] = DEFAULT_DENSITY_CUTOFFS,
) -> dict[str, float]:
    """Return spec-compatible cutoff-radius field names and values."""

    result: dict[str, float] = {}
    for cutoff in cutoffs:
        label = f"{cutoff:g}"
        result[f"r_iso_{label}_e_bohr3_bohr"] = radius_at_density(r_bohr, rho_e_bohr3, cutoff)
    return result


def total_density_matrix(mf: Any) -> NDArray[np.float64]:
    """Return the total alpha+beta density matrix from a PySCF mean-field object."""

    dm = np.asarray(mf.make_rdm1())
    if dm.ndim == 3:
        return dm[0] + dm[1]
    return dm


def _pyscf_numint():
    try:
        from pyscf.dft import numint  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "PySCF is required for density evaluation. Install with "
            "`python -m pip install \"atomref-proatoms[generator]\"` or from source "
            "with `python -m pip install -e \".[generator]\"`."
        ) from exc
    return numint


def angular_density_mean_std(
    mol: Any,
    dm_total: NDArray[np.float64],
    r_bohr: float,
    directions: NDArray[np.float64],
    weights: NDArray[np.float64],
) -> tuple[float, float]:
    """Evaluate angular mean/std of total density at one radius."""

    numint = _pyscf_numint()
    coords = float(r_bohr) * directions
    ao = numint.eval_ao(mol, coords, deriv=0)
    rho = numint.eval_rho(mol, ao, dm_total, xctype="LDA")
    return weighted_mean_and_std(np.asarray(rho, dtype=float), weights)


def electron_count_profile_trapz(
    r_bohr: NDArray[np.float64], rho_e_bohr3: NDArray[np.float64]
) -> tuple[NDArray[np.float64], float]:
    """Diagnostic trapezoidal electron count on the stored profile grid."""

    integrand = 4.0 * math.pi * r_bohr**2 * rho_e_bohr3
    cumulative = np.zeros_like(r_bohr, dtype=float)
    dr = np.diff(r_bohr)
    cumulative[1:] = np.cumsum(0.5 * (integrand[:-1] + integrand[1:]) * dr)
    return cumulative, float(cumulative[-1])


def electron_count_radial_gauss_log(
    mf: Any,
    *,
    r_min: float = QA_R_MIN,
    r_max: float = QA_R_MAX,
    n_r: int = QA_N_R,
    n_ang: int = QA_N_ANG,
    dm_total: NDArray[np.float64] | None = None,
    prefer_pyscf_angular_grid: bool = True,
) -> dict[str, Any]:
    """Electron-count QA via independent Gauss-Legendre quadrature in log-radius."""

    if dm_total is None:
        dm_total = total_density_matrix(mf)
    r_nodes, w_t = gauss_legendre_log_grid(r_min, r_max, n_r)
    directions, weights = angular_grid(n_ang, prefer_pyscf=prefer_pyscf_angular_grid)

    rho_avg = np.empty_like(r_nodes, dtype=float)
    for i, radius in enumerate(r_nodes):
        mean, _std = angular_density_mean_std(mf.mol, dm_total, float(radius), directions, weights)
        rho_avg[i] = mean

    integrand_t = 4.0 * math.pi * r_nodes**3 * rho_avg
    nelec = float(np.dot(w_t, integrand_t))
    return {
        "method": "radial_gauss_legendre_log_r",
        "r_min": r_min,
        "r_max": r_max,
        "n_r": n_r,
        "n_ang": n_ang,
        "nelec": nelec,
    }


def density_profile_from_mf(
    mf: Any,
    *,
    r_grid: NDArray[np.float64] | None = None,
    n_ang: int = QA_N_ANG,
    dm_total: NDArray[np.float64] | None = None,
    compute_qa: bool = True,
    qa_r_min: float = QA_R_MIN,
    qa_r_max: float = QA_R_MAX,
    qa_n_r: int = QA_N_R,
    qa_n_ang: int = QA_N_ANG,
    prefer_pyscf_angular_grid: bool = True,
) -> dict[str, Any]:
    """Evaluate a radial density profile from a completed PySCF mean-field object."""

    if r_grid is None:
        r_grid = default_profile_grid()
    if dm_total is None:
        dm_total = total_density_matrix(mf)
    directions, weights = angular_grid(n_ang, prefer_pyscf=prefer_pyscf_angular_grid)

    rho_avg = np.empty_like(r_grid, dtype=float)
    rho_std = np.empty_like(r_grid, dtype=float)
    for i, radius in enumerate(r_grid):
        mean, std = angular_density_mean_std(mf.mol, dm_total, float(radius), directions, weights)
        rho_avg[i] = mean
        rho_std[i] = std

    nelec_cum, nelec_profile_trapz = electron_count_profile_trapz(r_grid, rho_avg)
    qa = None
    if compute_qa:
        qa = electron_count_radial_gauss_log(
            mf,
            r_min=qa_r_min,
            r_max=qa_r_max,
            n_r=qa_n_r,
            n_ang=qa_n_ang,
            dm_total=dm_total,
            prefer_pyscf_angular_grid=prefer_pyscf_angular_grid,
        )

    return {
        "r_bohr": r_grid,
        "rho_e_bohr3": rho_avg,
        "rho_std_ang_e_bohr3": rho_std,
        "nelec_cumulative_profile": nelec_cum,
        "nelec_integrated_profile_trapz": nelec_profile_trapz,
        "nelec_qa": qa,
        "nelec_integrated_qa": qa["nelec"] if qa is not None else None,
    }


def validate_profile_metadata(metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_PROFILE_METADATA_FIELDS - set(metadata))
    if missing:
        errors.append(f"profile metadata missing fields {missing}")
        return errors
    if metadata.get("schema_version") != PROFILE_METADATA_SCHEMA_VERSION:
        errors.append(f"unexpected profile schema_version {metadata.get('schema_version')!r}")
    if metadata.get("density_model") != DENSITY_MODEL:
        errors.append(f"unexpected density_model {metadata.get('density_model')!r}")
    method = metadata.get("method")
    if not isinstance(method, dict):
        errors.append("method must be an object")
    else:
        method_missing = sorted(REQUIRED_PROFILE_METHOD_FIELDS - set(method))
        if method_missing:
            errors.append(f"profile method metadata missing fields {method_missing}")
    if metadata.get("units", {}).get("r") != "bohr":
        errors.append("radius unit must be bohr")
    if metadata.get("units", {}).get("rho") != "electron/bohr^3":
        errors.append("density unit must be electron/bohr^3")
    if not metadata.get("dataset_id"):
        errors.append("dataset_id is required")
    if not metadata.get("state_id"):
        errors.append("state_id is required")
    return errors
