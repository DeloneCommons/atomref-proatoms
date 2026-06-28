"""Artifact writers for generated proatom profile datasets."""

from __future__ import annotations

import csv
import json
import math
import numbers
import platform
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .profiles import DEFAULT_DENSITY_CUTOFFS, derived_radii
from .schemas import DENSITY_MODEL, PROFILE_METADATA_SCHEMA_VERSION
from .states import AtomState, state_digest


def json_safe(value: Any) -> Any:
    """Return a JSON-serializable value without NaN/Infinity tokens.

    Python's standard ``json.dumps`` allows non-standard ``NaN`` by default.  Profile
    metadata are release artifacts, so we normalize non-finite floating values to
    ``null`` and write with ``allow_nan=False``.
    """

    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path: Path, data: Any) -> None:
    """Write strict JSON with stable indentation and no NaN/Infinity tokens."""

    path.parent.mkdir(parents=True, exist_ok=True)
    safe_data = json_safe(data)
    path.write_text(
        json.dumps(safe_data, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def profile_density_column(state_id: str) -> str:
    """Return the released wide-CSV density column name for one state."""

    if not state_id:
        raise ValueError("state_id must be non-empty")
    return f"rho_e_bohr3__{state_id}"


def _float_list(values: Sequence[float] | Any, *, label: str) -> list[float]:
    try:
        result = [float(value) for value in values]
    except TypeError as exc:
        raise ValueError(f"{label} must be a sequence of numbers") from exc
    if not result:
        raise ValueError(f"{label} must be non-empty")
    return result


def write_wide_profiles_csv(
    path: Path,
    *,
    r_bohr: Sequence[float] | Any,
    densities_by_state_id: Mapping[str, Sequence[float] | Any],
) -> None:
    """Write one released dataset profile CSV with a shared radius grid.

    The output schema is:

    ``r_bohr,rho_e_bohr3__<state_id>,rho_e_bohr3__<state_id>,...``
    """

    r_values = _float_list(r_bohr, label="r_bohr")
    if not densities_by_state_id:
        raise ValueError("densities_by_state_id must be non-empty")
    columns: list[tuple[str, list[float]]] = [("r_bohr", r_values)]
    seen_columns = {"r_bohr"}
    for state_id, rho_values_raw in densities_by_state_id.items():
        column_name = profile_density_column(str(state_id))
        if column_name in seen_columns:
            raise ValueError(f"duplicate density column {column_name!r}")
        seen_columns.add(column_name)
        rho_values = _float_list(rho_values_raw, label=column_name)
        if len(rho_values) != len(r_values):
            raise ValueError(
                f"{column_name} length {len(rho_values)} does not match r_bohr length "
                f"{len(r_values)}"
            )
        columns.append((column_name, rho_values))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([name for name, _values in columns])
        for row_index in range(len(r_values)):
            writer.writerow([f"{values[row_index]:.17g}" for _name, values in columns])


def write_profile_dataset_artifacts(
    dataset_dir: Path,
    *,
    r_bohr: Sequence[float] | Any,
    densities_by_state_id: Mapping[str, Sequence[float] | Any],
    metadata: Mapping[str, Any],
) -> tuple[Path, Path]:
    """Write the v1 dataset-level ``profiles.csv`` and ``metadata.json`` artifacts."""

    profiles_path = dataset_dir / "profiles.csv"
    metadata_path = dataset_dir / "metadata.json"
    write_wide_profiles_csv(
        profiles_path,
        r_bohr=r_bohr,
        densities_by_state_id=densities_by_state_id,
    )
    write_json(metadata_path, dict(metadata))
    return profiles_path, metadata_path


def profile_metadata_template(
    *,
    dataset_id: str,
    state: AtomState,
    basis_id: str,
    basis_sha256: str,
    engine_version: str,
    xc: str = "PBE0",
    scf_type: str = "UKS",
    relativity: str = "sf-X2C-1e",
    derived: dict[str, float] | None = None,
    qa: dict[str, Any] | None = None,
    generator_git_commit: str | None = None,
    basis_manifest_sha256: str | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the common metadata structure for one generated profile.

    This helper is retained for per-state metadata assembly during the transition to
    aggregate dataset metadata.
    """

    return {
        "schema_version": PROFILE_METADATA_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "state_id": state.state_id,
        "density_model": DENSITY_MODEL,
        "method": {
            "engine": "pyscf",
            "engine_version": engine_version,
            "scf_type": scf_type,
            "xc": xc,
            "relativity": relativity,
            "basis_id": basis_id,
            "basis_sha256": basis_sha256,
        },
        "state": {
            "symbol": state.symbol,
            "charge": state.charge,
            "spin_2s": state.spin_2s,
            "multiplicity": state.multiplicity,
            "configuration": state.record["configuration"],
            "spin_model": state.record["spin_model"],
            "occupation_policy": state.record["occupation_policy"],
            "state_category": state.record["state_category"],
            "curation_status": state.record["curation_status"],
        },
        "units": {
            "r": "bohr",
            "rho": "electron/bohr^3",
        },
        "derived": derived or {},
        "qa": qa or {},
        "diagnostics": diagnostics or {},
        "provenance": {
            "generator_git_commit": generator_git_commit,
            "python_version": platform.python_version(),
            "basis_manifest_sha256": basis_manifest_sha256,
            "state_record_sha256": state_digest(state.record),
        },
    }


def derived_radii_from_profile(
    profile: dict[str, Any], cutoffs: tuple[float, ...] = DEFAULT_DENSITY_CUTOFFS
) -> dict[str, float]:
    return derived_radii(profile["r_bohr"], profile["rho_e_bohr3"], cutoffs)
