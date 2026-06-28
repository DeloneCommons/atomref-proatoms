"""Artifact writers for generated proatom profile datasets."""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
import numbers
import platform
import zipfile
from pathlib import Path
from typing import Any, Literal

from .profiles import DEFAULT_DENSITY_CUTOFFS, derived_radii
from .schemas import DENSITY_MODEL, PROFILE_METADATA_SCHEMA_VERSION
from .states import AtomState, state_digest

ProfileArchiveFormat = Literal["zip", "csv.gz"]


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


def _profile_columns(
    rows: list[tuple[float, float]] | None = None,
    *,
    r_bohr: list[float] | Any | None = None,
    rho_e_bohr3: list[float] | Any | None = None,
    rho_std_ang_e_bohr3: list[float] | Any | None = None,
    nelec_cumulative_profile: list[float] | Any | None = None,
) -> list[tuple[str, list[float]]]:
    if rows is not None:
        r_values = [row[0] for row in rows]
        rho_values = [row[1] for row in rows]
    else:
        if r_bohr is None or rho_e_bohr3 is None:
            raise ValueError("either rows or both r_bohr/rho_e_bohr3 must be provided")
        r_values = list(r_bohr)
        rho_values = list(rho_e_bohr3)

    columns: list[tuple[str, list[float]]] = [
        ("r_bohr", [float(value) for value in r_values]),
        ("rho_e_bohr3", [float(value) for value in rho_values]),
    ]
    if rho_std_ang_e_bohr3 is not None:
        columns.append(("rho_std_ang_e_bohr3", [float(value) for value in rho_std_ang_e_bohr3]))
    if nelec_cumulative_profile is not None:
        columns.append(
            ("nelec_cumulative_profile", [float(value) for value in nelec_cumulative_profile])
        )

    n_rows = len(columns[0][1])
    if any(len(values) != n_rows for _name, values in columns):
        raise ValueError("all profile columns must have the same length")
    return columns


def _write_profile_csv_text(handle: Any, columns: list[tuple[str, list[float]]]) -> None:
    writer = csv.writer(handle)
    writer.writerow([name for name, _values in columns])
    for i in range(len(columns[0][1])):
        writer.writerow([f"{values[i]:.17g}" for _name, values in columns])


def write_profile_csv_zip(
    path: Path,
    rows: list[tuple[float, float]] | None = None,
    *,
    r_bohr: list[float] | Any | None = None,
    rho_e_bohr3: list[float] | Any | None = None,
    rho_std_ang_e_bohr3: list[float] | Any | None = None,
    nelec_cumulative_profile: list[float] | Any | None = None,
    inner_csv_name: str | None = None,
) -> None:
    """Write a profile CSV inside a deterministic ``.zip`` archive.

    The default inner file for ``H_q0_mult2_hund.csv.zip`` is
    ``H_q0_mult2_hund.csv``.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    columns = _profile_columns(
        rows,
        r_bohr=r_bohr,
        rho_e_bohr3=rho_e_bohr3,
        rho_std_ang_e_bohr3=rho_std_ang_e_bohr3,
        nelec_cumulative_profile=nelec_cumulative_profile,
    )
    if inner_csv_name is None:
        inner_csv_name = path.name.removesuffix(".zip")
    if not inner_csv_name.endswith(".csv"):
        raise ValueError("inner_csv_name must end with .csv")

    text_handle = io.StringIO(newline="")
    _write_profile_csv_text(text_handle, columns)
    payload = text_handle.getvalue().encode("utf-8")

    info = zipfile.ZipInfo(inner_csv_name)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(info, payload)


def write_profile_csv_gz(
    path: Path,
    rows: list[tuple[float, float]] | None = None,
    *,
    r_bohr: list[float] | Any | None = None,
    rho_e_bohr3: list[float] | Any | None = None,
    rho_std_ang_e_bohr3: list[float] | Any | None = None,
    nelec_cumulative_profile: list[float] | Any | None = None,
) -> None:
    """Write a legacy profile CSV.GZ archive.

    Legacy profile generation used ``.csv.zip`` archives.  This helper remains
    temporarily available until the v1 wide-CSV extractor replaces per-state archives.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    columns = _profile_columns(
        rows,
        r_bohr=r_bohr,
        rho_e_bohr3=rho_e_bohr3,
        rho_std_ang_e_bohr3=rho_std_ang_e_bohr3,
        nelec_cumulative_profile=nelec_cumulative_profile,
    )
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        _write_profile_csv_text(handle, columns)


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
    """Build the common metadata structure for one generated profile."""

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


def write_state_profile_artifacts(
    dataset_dir: Path,
    *,
    state_id: str,
    profile: dict[str, Any],
    metadata: dict[str, Any],
    profile_archive_format: ProfileArchiveFormat = "zip",
) -> tuple[Path, Path]:
    """Write profile archive and per-state metadata JSON under a dataset directory."""

    if profile_archive_format == "zip":
        profile_path = dataset_dir / "profiles" / f"{state_id}.csv.zip"
        write_profile_csv_zip(
            profile_path,
            r_bohr=profile["r_bohr"],
            rho_e_bohr3=profile["rho_e_bohr3"],
            rho_std_ang_e_bohr3=profile.get("rho_std_ang_e_bohr3"),
            nelec_cumulative_profile=profile.get("nelec_cumulative_profile"),
        )
    elif profile_archive_format == "csv.gz":
        profile_path = dataset_dir / "profiles" / f"{state_id}.csv.gz"
        write_profile_csv_gz(
            profile_path,
            r_bohr=profile["r_bohr"],
            rho_e_bohr3=profile["rho_e_bohr3"],
            rho_std_ang_e_bohr3=profile.get("rho_std_ang_e_bohr3"),
            nelec_cumulative_profile=profile.get("nelec_cumulative_profile"),
        )
    else:
        raise ValueError(f"unsupported profile archive format {profile_archive_format!r}")

    metadata_path = dataset_dir / "metadata" / f"{state_id}.json"
    write_json(metadata_path, metadata)
    return profile_path, metadata_path


def derived_radii_from_profile(
    profile: dict[str, Any], cutoffs: tuple[float, ...] = DEFAULT_DENSITY_CUTOFFS
) -> dict[str, float]:
    return derived_radii(profile["r_bohr"], profile["rho_e_bohr3"], cutoffs)
