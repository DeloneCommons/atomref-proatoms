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

from .paths import repo_relative_path
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
            "python_version": platform.python_version(),
            "basis_manifest_sha256": basis_manifest_sha256,
            "state_record_sha256": state_digest(state.record),
        },
    }


def derived_radii_from_profile(
    profile: dict[str, Any], cutoffs: tuple[float, ...] = DEFAULT_DENSITY_CUTOFFS
) -> dict[str, float]:
    return derived_radii(profile["r_bohr"], profile["rho_e_bohr3"], cutoffs)

BOHR_TO_ANGSTROM = 0.529177210903
RADII_DATASET_SCHEMA_VERSION = "atomref.proatoms.radii_dataset.v1"
QA_DATASET_SCHEMA_VERSION = "atomref.proatoms.qa_dataset.v1"
QA_OVERVIEW_SCHEMA_VERSION = "atomref.proatoms.qa_overview.v1"


def radii_bohr_field(cutoff: float) -> str:
    return f"r_iso_{cutoff:g}_e_bohr3_bohr"


def radii_angstrom_field(cutoff: float) -> str:
    return f"r_iso_{cutoff:g}_e_bohr3_angstrom"


def _state_table_prefix(state_id: str, state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "state_id": state_id,
        "symbol": state.get("symbol"),
        "z": state.get("z"),
        "charge": state.get("charge"),
        "electron_count": state.get("electron_count"),
        "multiplicity": state.get("multiplicity"),
        "state_category": state.get("state_category"),
        "state_role": state.get("state_role"),
    }


def _write_dict_rows_csv(
    path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: json_safe(row.get(name)) for name in fieldnames})


def write_radii_dataset_artifacts(
    dataset_dir: Path,
    *,
    dataset_id: str,
    profile_data_version: str,
    basis_id: str,
    cutoffs_e_bohr3: Sequence[float],
    states: Mapping[str, Mapping[str, Any]],
    derived_radii_by_state_id: Mapping[str, Mapping[str, Any]],
    source_profiles_csv: str,
    source_metadata_json: str,
    provenance: Mapping[str, Any] | None = None,
) -> tuple[Path, Path]:
    """Write one dataset's cutoff radii as a first-class result artifact."""

    cutoffs = [float(value) for value in cutoffs_e_bohr3]
    bohr_fields = [radii_bohr_field(cutoff) for cutoff in cutoffs]
    angstrom_fields = [radii_angstrom_field(cutoff) for cutoff in cutoffs]
    fieldnames = [
        "state_id",
        "symbol",
        "z",
        "charge",
        "electron_count",
        "multiplicity",
        "state_category",
        "state_role",
        *bohr_fields,
        *angstrom_fields,
    ]
    rows: list[dict[str, Any]] = []
    for state_id, state in states.items():
        derived = derived_radii_by_state_id.get(state_id, {})
        row = _state_table_prefix(state_id, state)
        for _cutoff, bohr_field, angstrom_field in zip(
            cutoffs, bohr_fields, angstrom_fields, strict=True
        ):
            bohr_value = derived.get(bohr_field)
            row[bohr_field] = bohr_value
            row[angstrom_field] = (
                None if bohr_value is None else float(bohr_value) * BOHR_TO_ANGSTROM
            )
        rows.append(row)

    radii_csv = dataset_dir / "radii.csv"
    metadata_json = dataset_dir / "metadata.json"
    _write_dict_rows_csv(radii_csv, fieldnames, rows)
    write_json(
        metadata_json,
        {
            "schema_version": RADII_DATASET_SCHEMA_VERSION,
            "profile_data_version": profile_data_version,
            "dataset_id": dataset_id,
            "basis_id": basis_id,
            "units": {"r_bohr": "bohr", "r_angstrom": "angstrom", "rho_cutoff": "electron/bohr^3"},
            "cutoffs_e_bohr3": cutoffs,
            "files": {
                "radii_csv": repo_relative_path(radii_csv),
                "metadata_json": repo_relative_path(metadata_json),
            },
            "sources": {
                "profiles_csv": source_profiles_csv,
                "profile_metadata_json": source_metadata_json,
            },
            "row_count": len(rows),
            "provenance": dict(provenance or {}),
        },
    )
    return radii_csv, metadata_json


def qa_overall_pass(row: Mapping[str, Any]) -> bool:
    """Return the release QA pass/fail flag for one state row."""

    required_true = [
        "scf_converged",
        "electron_count_pass",
        "angular_sigma_pass",
        "tail_reaches_min_cutoff",
        "radii_monotonic",
    ]
    return all(bool(row.get(key)) for key in required_true)


def write_qa_dataset_artifacts(
    dataset_dir: Path,
    *,
    dataset_id: str,
    profile_data_version: str,
    basis_id: str,
    states: Mapping[str, Mapping[str, Any]],
    qa_by_state_id: Mapping[str, Mapping[str, Any]],
    source_profiles_csv: str,
    source_metadata_json: str,
    provenance: Mapping[str, Any] | None = None,
) -> tuple[Path, Path]:
    """Write one dataset's QA table and metadata."""

    fieldnames = [
        "state_id",
        "symbol",
        "z",
        "charge",
        "electron_count",
        "multiplicity",
        "state_category",
        "state_role",
        "overall_pass",
        "scf_converged",
        "electron_count_error_qa",
        "electron_count_tolerance",
        "electron_count_pass",
        "max_rel_angular_sigma",
        "max_rel_angular_sigma_tolerance",
        "angular_sigma_pass",
        "tail_reaches_min_cutoff",
        "radii_monotonic",
        "linear_dependency_warning_count",
        "linear_dependency_vectors_removed",
    ]
    rows: list[dict[str, Any]] = []
    for state_id, state in states.items():
        qa = dict(qa_by_state_id.get(state_id, {}))
        row = _state_table_prefix(state_id, state)
        row.update(qa)
        row["overall_pass"] = qa_overall_pass(row)
        rows.append(row)

    qa_csv = dataset_dir / "qa.csv"
    metadata_json = dataset_dir / "metadata.json"
    _write_dict_rows_csv(qa_csv, fieldnames, rows)
    passed = sum(1 for row in rows if bool(row["overall_pass"]))
    write_json(
        metadata_json,
        {
            "schema_version": QA_DATASET_SCHEMA_VERSION,
            "profile_data_version": profile_data_version,
            "dataset_id": dataset_id,
            "basis_id": basis_id,
            "files": {
                "qa_csv": repo_relative_path(qa_csv),
                "metadata_json": repo_relative_path(metadata_json),
            },
            "sources": {
                "profiles_csv": source_profiles_csv,
                "profile_metadata_json": source_metadata_json,
            },
            "row_count": len(rows),
            "passed_count": passed,
            "failed_count": len(rows) - passed,
            "provenance": dict(provenance or {}),
        },
    )
    return qa_csv, metadata_json


def write_qa_overview(
    qa_root: Path,
    *,
    profile_data_version: str,
    dataset_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Path]:
    """Write a compact global QA summary and Markdown all-good report."""

    qa_root.mkdir(parents=True, exist_ok=True)
    summary_csv = qa_root / "qa_summary.csv"
    report_md = qa_root / "qa_report.md"
    metadata_json = qa_root / "metadata.json"
    fields = [
        "dataset_id",
        "basis_id",
        "state_count",
        "passed_count",
        "failed_count",
        "max_abs_electron_count_error_qa",
        "max_rel_angular_sigma",
        "linear_dependency_warning_count",
    ]
    _write_dict_rows_csv(summary_csv, fields, dataset_summaries)

    total_states = sum(int(row.get("state_count", 0) or 0) for row in dataset_summaries)
    total_failed = sum(int(row.get("failed_count", 0) or 0) for row in dataset_summaries)
    total_ld_warnings = sum(
        int(row.get("linear_dependency_warning_count", 0) or 0) for row in dataset_summaries
    )
    status = "PASS" if total_failed == 0 else "FAIL"
    lines = [
        f"# atomref-proatoms QA status: {status}",
        "",
        f"Profile data version: `{profile_data_version}`.",
        f"Datasets checked: {len(dataset_summaries)}.",
        f"States checked: {total_states}.",
        f"Failed rows: {total_failed}.",
        f"Linear-dependency warnings: {total_ld_warnings}.",
        "",
        "This file is generated from `data/qa/*/qa.csv` and is intended as a compact ",
        "release gate, not as a narrative scientific report.",
        "",
        "| dataset_id | states | failed | max |ΔN| | max angular σ/ρ | LD warnings |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in dataset_summaries:
        lines.append(
            "| {dataset_id} | {state_count} | {failed_count} | {err} | {sigma} | {ld} |".format(
                dataset_id=row.get("dataset_id"),
                state_count=row.get("state_count"),
                failed_count=row.get("failed_count"),
                err=row.get("max_abs_electron_count_error_qa"),
                sigma=row.get("max_rel_angular_sigma"),
                ld=row.get("linear_dependency_warning_count"),
            )
        )
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(
        metadata_json,
        {
            "schema_version": QA_OVERVIEW_SCHEMA_VERSION,
            "profile_data_version": profile_data_version,
            "files": {
                "qa_summary_csv": repo_relative_path(summary_csv),
                "qa_report_md": repo_relative_path(report_md),
                "metadata_json": repo_relative_path(metadata_json),
            },
            "dataset_count": len(dataset_summaries),
            "state_count": total_states,
            "failed_count": total_failed,
        },
    )
    return {"qa_summary": summary_csv, "qa_report": report_md, "metadata": metadata_json}
