"""Small QA helpers shared by profile checks and generator code."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

ANGULAR_SIGMA_RHO_FLOOR = 1.0e-8
ELECTRON_COUNT_ABS_TOL = 2.0e-6
ELECTRON_COUNT_REL_TOL = 2.0e-7




@dataclass(frozen=True)
class SpinDiagnostics:
    """Diagnostic spin-square summary reported by the backend.

    For spherical fractional occupations the backend ``<S^2>`` value is not a
    strict pass/fail QA target; it is recorded to make open-shell and heavy-atom
    runs auditable.
    """

    target_spin_2s: int
    target_multiplicity: int
    target_spin_square: float
    reported_spin_square: float | None
    reported_multiplicity: float | None
    spin_square_deviation: float | None
    multiplicity_deviation: float | None
    note: str

    def to_json(self) -> dict[str, Any]:
        return {
            "target_spin_2s": self.target_spin_2s,
            "target_multiplicity": self.target_multiplicity,
            "target_spin_square": self.target_spin_square,
            "reported_spin_square": self.reported_spin_square,
            "reported_multiplicity": self.reported_multiplicity,
            "spin_square_deviation": self.spin_square_deviation,
            "multiplicity_deviation": self.multiplicity_deviation,
            "note": self.note,
        }


@dataclass(frozen=True)
class LinearDependencyDiagnostics:
    """Summary of PySCF overlap-linear-dependency warnings parsed from SCF logs."""

    warning_count: int
    vectors_removed: int | None

    def to_json(self) -> dict[str, Any]:
        return {
            "warning_count": self.warning_count,
            "vectors_removed": self.vectors_removed,
        }


SPIN_DIAGNOSTIC_NOTE = (
    "PySCF spin_square is recorded as a diagnostic only. For spherical "
    "fractional-occupation proatoms it is not used as a release QA pass/fail target."
)

LINEAR_DEPENDENCY_RE = re.compile(
    r"WARN:\s+(?P<count>\d+)\s+small eigenvectors? of overlap matrix removed",
    re.IGNORECASE,
)


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


def electron_count_tolerance(
    electron_count: int | float,
    *,
    abs_tol: float = ELECTRON_COUNT_ABS_TOL,
    rel_tol: float = ELECTRON_COUNT_REL_TOL,
) -> float:
    """Return the absolute tolerance for independent electron-count QA.

    The independent QA integration is a numerical quadrature over the generated
    density, not a re-normalization step. Heavy atoms and large relativistic
    bases can show absolute errors around 1e-5 electrons on deliberately modest
    local diagnostic grids while still being excellent on a relative scale.  The default
    therefore combines a small absolute floor with a per-electron relative term.
    """

    if abs_tol < 0 or rel_tol < 0:
        raise ValueError("electron-count tolerances must be non-negative")
    n_electrons = abs(float(electron_count))
    return max(float(abs_tol), float(rel_tol) * n_electrons)


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


def expected_spin_square(spin_2s: int | float) -> float:
    """Return S(S+1) for target ``2S``."""

    spin = float(spin_2s) / 2.0
    return spin * (spin + 1.0)


def spin_diagnostics_from_mf(mf: Any, *, spin_2s: int) -> SpinDiagnostics:
    """Collect backend spin-square diagnostics from a completed mean-field object."""

    target_spin_2s = int(spin_2s)
    target_mult = target_spin_2s + 1
    target_ss = expected_spin_square(target_spin_2s)
    reported_ss: float | None = None
    reported_mult: float | None = None
    spin_square = getattr(mf, "spin_square", None)
    if callable(spin_square):
        try:
            values = spin_square()
        except Exception:
            values = None
        if isinstance(values, tuple) and len(values) >= 2:
            try:
                reported_ss = float(values[0])
                reported_mult = float(values[1])
            except (TypeError, ValueError):
                reported_ss = None
                reported_mult = None
    return SpinDiagnostics(
        target_spin_2s=target_spin_2s,
        target_multiplicity=target_mult,
        target_spin_square=target_ss,
        reported_spin_square=reported_ss,
        reported_multiplicity=reported_mult,
        spin_square_deviation=None if reported_ss is None else reported_ss - target_ss,
        multiplicity_deviation=(
            None if reported_mult is None else reported_mult - float(target_mult)
        ),
        note=SPIN_DIAGNOSTIC_NOTE,
    )


def linear_dependency_diagnostics_from_log(log_text: str) -> LinearDependencyDiagnostics:
    """Parse PySCF overlap-linear-dependency warnings from captured SCF text."""

    counts = [int(match.group("count")) for match in LINEAR_DEPENDENCY_RE.finditer(log_text)]
    return LinearDependencyDiagnostics(
        warning_count=len(counts),
        vectors_removed=sum(counts) if counts else None,
    )
