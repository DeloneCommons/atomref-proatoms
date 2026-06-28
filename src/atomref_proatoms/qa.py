"""Small QA helpers shared by profile checks and future generator code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QAResult:
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
