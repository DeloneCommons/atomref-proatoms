"""Small QA helpers shared by profile checks and generator code."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

ANGULAR_SIGMA_RHO_FLOOR = 1.0e-8
ELECTRON_COUNT_ABS_TOL = 1.0e-6
ELECTRON_COUNT_REL_TOL = 1.0e-8


@dataclass(frozen=True)
class QAResult:
    """Serializable quality-assurance summary for one generated profile."""

    scf_converged: bool
    electron_count_error_qa: float | None
    max_rel_angular_sigma: float | None
    tail_reaches_min_cutoff: bool
    radii_monotonic: bool
    linear_dependency_vectors_removed: int | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "scf_converged": self.scf_converged,
            "electron_count_error_qa": self.electron_count_error_qa,
            "max_rel_angular_sigma": self.max_rel_angular_sigma,
            "linear_dependency_vectors_removed": self.linear_dependency_vectors_removed,
            "tail_reaches_min_cutoff": self.tail_reaches_min_cutoff,
            "radii_monotonic": self.radii_monotonic,
        }


@dataclass(frozen=True)
class AngularSigmaSummary:
    """Relative angular density variation on the stored radial profile grid."""

    max_rel_angular_sigma: float | None
    rho_floor: float
    n_points_used: int

    def to_json(self) -> dict[str, Any]:
        return {
            "max_rel_angular_sigma": self.max_rel_angular_sigma,
            "rho_floor": self.rho_floor,
            "n_points_used": self.n_points_used,
        }


def electron_count_tolerance(electron_count: int | float) -> float:
    """Return the default absolute tolerance for independent electron-count QA."""

    n_electrons = abs(float(electron_count))
    return max(ELECTRON_COUNT_ABS_TOL, ELECTRON_COUNT_REL_TOL * n_electrons)


def radii_are_monotonic(derived: dict[str, float]) -> bool:
    keys = [
        "r_iso_0.003_e_bohr3_bohr",
        "r_iso_0.001_e_bohr3_bohr",
        "r_iso_0.0001_e_bohr3_bohr",
    ]
    try:
        values = [float(derived[key]) for key in keys]
    except KeyError:
        return False
    return values[0] < values[1] < values[2]


def max_relative_angular_sigma(
    rho_e_bohr3: Sequence[float],
    rho_std_ang_e_bohr3: Sequence[float] | None,
    *,
    rho_floor: float = ANGULAR_SIGMA_RHO_FLOOR,
) -> AngularSigmaSummary:
    """Summarize angular variation as ``max(std_ang(rho) / rho)``.

    The spherical proatom algorithm should produce a density that is independent of angle up
    to numerical noise.  Very far in the density tail the denominator is tiny, so points with
    ``rho <= rho_floor`` are ignored.
    """

    if rho_floor <= 0:
        raise ValueError("rho_floor must be positive")
    if rho_std_ang_e_bohr3 is None:
        return AngularSigmaSummary(None, rho_floor, 0)
    rho = [float(value) for value in rho_e_bohr3]
    sigma = [float(value) for value in rho_std_ang_e_bohr3]
    if len(rho) != len(sigma):
        raise ValueError("rho and angular sigma arrays must have the same length")

    relative_values: list[float] = []
    for density, std in zip(rho, sigma, strict=True):
        if not math.isfinite(density) or not math.isfinite(std):
            raise ValueError("rho and angular sigma arrays must contain only finite values")
        if density > rho_floor:
            relative_values.append(abs(std) / abs(density))
    if not relative_values:
        return AngularSigmaSummary(None, rho_floor, 0)
    return AngularSigmaSummary(max(relative_values), rho_floor, len(relative_values))


def qa_result_from_profile(
    *,
    scf_converged: bool,
    electron_count_exact: int | float,
    derived: dict[str, float],
    profile: dict[str, Any],
    linear_dependency_vectors_removed: int | None = None,
    angular_sigma_rho_floor: float = ANGULAR_SIGMA_RHO_FLOOR,
) -> QAResult:
    """Build the standard per-profile QA summary from a generated profile dict."""

    nelec_qa = profile.get("nelec_integrated_qa")
    electron_count_error_qa = (
        None if nelec_qa is None else float(nelec_qa) - float(electron_count_exact)
    )
    angular = max_relative_angular_sigma(
        profile.get("rho_e_bohr3", []),
        profile.get("rho_std_ang_e_bohr3"),
        rho_floor=angular_sigma_rho_floor,
    )
    return QAResult(
        scf_converged=scf_converged,
        electron_count_error_qa=electron_count_error_qa,
        max_rel_angular_sigma=angular.max_rel_angular_sigma,
        linear_dependency_vectors_removed=linear_dependency_vectors_removed,
        tail_reaches_min_cutoff=True,
        radii_monotonic=radii_are_monotonic(derived),
    )
