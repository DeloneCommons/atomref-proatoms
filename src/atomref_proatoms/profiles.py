"""Profile metadata helpers and lightweight radial-density utilities."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from .schemas import (
    DENSITY_MODEL,
    PROFILE_METADATA_SCHEMA_VERSION,
    REQUIRED_PROFILE_METADATA_FIELDS,
    REQUIRED_PROFILE_METHOD_FIELDS,
)


def radius_at_density(
    r_bohr: Sequence[float], rho_e_bohr3: Sequence[float], cutoff: float
) -> float:
    """Interpolate the outermost radius where ``rho`` reaches ``cutoff``.

    The function assumes a radial profile sampled from small to large radius and returns the
    first outward crossing from ``rho >= cutoff`` to ``rho <= cutoff``. Interpolation is linear
    in ``log(rho)`` when both neighboring densities are positive, which is stable for tail
    radii. It raises ``ValueError`` when the profile never crosses the cutoff.
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

    for i in range(len(rho) - 1):
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
    if rho[-1] == cutoff:
        return radii[-1]
    raise ValueError(f"profile does not cross cutoff {cutoff}")


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
