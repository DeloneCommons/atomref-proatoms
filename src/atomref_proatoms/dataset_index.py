"""Dataset-level indexes for generated proatom profile directories."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import write_json
from .basis import list_basis_bundles, sha256_file
from .profile_checks import (
    ANGULAR_SIGMA_DEFAULT_TOL,
    ProfileCheckResult,
    check_profile_dataset,
    read_profile_table,
    read_strict_json,
)
from .qa import ELECTRON_COUNT_ABS_TOL, ELECTRON_COUNT_REL_TOL
from .schemas import PROFILE_DATASET_MANIFEST_SCHEMA_VERSION
from .states import AtomState, load_atom_states

PROFILE_INDEX_COLUMNS = (
    "dataset_id",
    "state_id",
    "symbol",
    "z",
    "charge",
    "electron_count",
    "multiplicity",
    "state_category",
    "state_role",
    "spin_model",
    "target_spin_square",
    "reported_spin_square",
    "reported_spin_multiplicity",
    "spin_square_deviation",
    "linear_dependency_warning_count",
    "linear_dependency_vectors_removed",
    "basis_id",
    "basis_sha256",
    "engine",
    "engine_version",
    "xc",
    "relativity",
    "profile_archive",
    "profile_sha256",
    "metadata_json",
    "metadata_sha256",
    "n_grid",
    "n_columns",
    "scf_converged",
    "electron_count_error_qa",
    "max_rel_angular_sigma",
    "tail_reaches_min_cutoff",
    "radii_monotonic",
)

DERIVED_RADII_COLUMNS = (
    "dataset_id",
    "state_id",
    "basis_id",
    "r_iso_0.003_e_bohr3_bohr",
    "r_iso_0.001_e_bohr3_bohr",
    "r_iso_0.0001_e_bohr3_bohr",
)


@dataclass(frozen=True)
class DatasetIndexTables:
    """In-memory dataset-level index tables derived from per-state artifacts."""

    dataset_dir: Path
    dataset_id: str
    manifest: dict[str, Any]
    profile_index_rows: tuple[dict[str, Any], ...]
    derived_radii_rows: tuple[dict[str, Any], ...]

    @property
    def profile_count(self) -> int:
        return len(self.profile_index_rows)


@dataclass(frozen=True)
class DatasetIndexCheckResult:
    """Result of checking dataset-level index files."""

    dataset_dir: Path
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def _states_by_id(states_file: Path | None) -> dict[str, AtomState]:
    if states_file is None or not states_file.exists():
        return {}
    return {state.state_id: state for state in load_atom_states(states_file)}


def _basis_by_id(basis_root: Path | None) -> dict[str, Any]:
    if basis_root is None or not basis_root.exists():
        return {}
    return {bundle.basis_id: bundle for bundle in list_basis_bundles(basis_root)}


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _find_profile_archive(dataset_dir: Path, state_id: str) -> Path:
    profiles_dir = dataset_dir / "profiles"
    candidates = [profiles_dir / f"{state_id}.csv.zip", profiles_dir / f"{state_id}.csv.gz"]
    existing = [path for path in candidates if path.exists()]
    if len(existing) != 1:
        suffixes = ", ".join(path.name for path in existing) or "none"
        raise ValueError(f"{state_id}: expected exactly one profile archive, got {suffixes}")
    return existing[0]


def _csv_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _write_csv(path: Path, columns: tuple[str, ...], rows: tuple[dict[str, Any], ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_scalar(row.get(column)) for column in columns})


def _read_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return tuple(dict(row) for row in reader)


def _archive_format(path: Path) -> str:
    if path.name.endswith(".csv.zip"):
        return "zip"
    if path.name.endswith(".csv.gz"):
        return "csv.gz"
    return "unknown"


def _require_single_dataset_id(rows: tuple[dict[str, Any], ...], dataset_dir: Path) -> str:
    dataset_ids = sorted({str(row.get("dataset_id", "")) for row in rows})
    if len(dataset_ids) != 1 or not dataset_ids[0]:
        raise ValueError(f"{dataset_dir}: expected one nonempty dataset_id, got {dataset_ids}")
    return dataset_ids[0]


def _qa_summary(profile_rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    electron_errors = [
        abs(float(row["electron_count_error_qa"]))
        for row in profile_rows
        if row.get("electron_count_error_qa") is not None
    ]
    angular_sigmas = [
        float(row["max_rel_angular_sigma"])
        for row in profile_rows
        if row.get("max_rel_angular_sigma") is not None
    ]
    spin_deviations = [
        abs(float(row["spin_square_deviation"]))
        for row in profile_rows
        if row.get("spin_square_deviation") is not None
    ]
    dependency_vectors = [
        int(row["linear_dependency_vectors_removed"])
        for row in profile_rows
        if row.get("linear_dependency_vectors_removed") is not None
    ]
    dependency_warnings = [
        int(row["linear_dependency_warning_count"] or 0)
        for row in profile_rows
        if row.get("linear_dependency_warning_count") is not None
    ]
    return {
        "profile_count": len(profile_rows),
        "scf_converged_count": sum(row.get("scf_converged") is True for row in profile_rows),
        "electron_count_qa_count": len(electron_errors),
        "angular_sigma_qa_count": len(angular_sigmas),
        "spin_square_diagnostic_count": len(spin_deviations),
        "linear_dependency_warning_count": sum(dependency_warnings),
        "linear_dependency_profile_count": sum(
            int(row.get("linear_dependency_warning_count") or 0) > 0 for row in profile_rows
        ),
        "max_abs_electron_count_error_qa": max(electron_errors) if electron_errors else None,
        "max_rel_angular_sigma": max(angular_sigmas) if angular_sigmas else None,
        "max_abs_spin_square_deviation": max(spin_deviations) if spin_deviations else None,
        "max_linear_dependency_vectors_removed": max(dependency_vectors) if dependency_vectors else None,
        "all_tail_reaches_min_cutoff": all(
            row.get("tail_reaches_min_cutoff") is True for row in profile_rows
        ),
        "all_radii_monotonic": all(row.get("radii_monotonic") is True for row in profile_rows),
    }


def build_dataset_index_tables(
    dataset_dir: Path,
    *,
    states_file: Path | None = None,
    basis_root: Path | None = None,
) -> DatasetIndexTables:
    """Build dataset manifest/index rows from existing per-state artifacts."""

    metadata_dir = dataset_dir / "metadata"
    if not metadata_dir.is_dir():
        raise ValueError(f"missing metadata directory: {metadata_dir}")
    states = _states_by_id(states_file)
    bases = _basis_by_id(basis_root)

    profile_rows: list[dict[str, Any]] = []
    radii_rows: list[dict[str, Any]] = []
    for metadata_path in sorted(metadata_dir.glob("*.json")):
        metadata = read_strict_json(metadata_path)
        if not isinstance(metadata, dict):
            raise ValueError(f"{metadata_path}: metadata root must be an object")
        state_id = str(metadata.get("state_id"))
        archive_path = _find_profile_archive(dataset_dir, state_id)
        table = read_profile_table(archive_path)
        state = states.get(state_id)
        method = metadata.get("method", {})
        qa = metadata.get("qa", {})
        state_metadata = metadata.get("state", {})
        diagnostics = metadata.get("diagnostics", {})
        if not isinstance(diagnostics, dict):
            diagnostics = {}
        spin_diagnostics = diagnostics.get("spin", {})
        if not isinstance(spin_diagnostics, dict):
            spin_diagnostics = {}
        linear_dependency = diagnostics.get("linear_dependency", {})
        if not isinstance(linear_dependency, dict):
            linear_dependency = {}
        basis_id = str(method.get("basis_id", ""))
        basis_sha256 = str(method.get("basis_sha256", ""))
        if basis_id in bases and basis_sha256 != bases[basis_id].basis_sha256:
            raise ValueError(f"{state_id}: basis_sha256 does not match frozen basis bundle")

        profile_rows.append(
            {
                "dataset_id": metadata.get("dataset_id"),
                "state_id": state_id,
                "symbol": state.symbol if state is not None else state_metadata.get("symbol"),
                "z": state.z if state is not None else "",
                "charge": state.charge if state is not None else state_metadata.get("charge"),
                "electron_count": state.electron_count if state is not None else "",
                "multiplicity": (
                    state.multiplicity if state is not None else state_metadata.get("multiplicity")
                ),
                "state_category": (
                    state.record.get("state_category")
                    if state is not None
                    else state_metadata.get("state_category")
                ),
                "state_role": (
                    state.record.get("state_role")
                    if state is not None
                    else state_metadata.get("state_role")
                ),
                "spin_model": (
                    state.record.get("spin_model")
                    if state is not None
                    else state_metadata.get("spin_model")
                ),
                "target_spin_square": spin_diagnostics.get("target_spin_square"),
                "reported_spin_square": spin_diagnostics.get("reported_spin_square"),
                "reported_spin_multiplicity": spin_diagnostics.get("reported_multiplicity"),
                "spin_square_deviation": spin_diagnostics.get("spin_square_deviation"),
                "linear_dependency_warning_count": linear_dependency.get("warning_count"),
                "linear_dependency_vectors_removed": qa.get("linear_dependency_vectors_removed"),
                "basis_id": basis_id,
                "basis_sha256": basis_sha256,
                "engine": method.get("engine"),
                "engine_version": method.get("engine_version"),
                "xc": method.get("xc"),
                "relativity": method.get("relativity"),
                "profile_archive": _relative_path(archive_path, dataset_dir),
                "profile_sha256": sha256_file(archive_path),
                "metadata_json": _relative_path(metadata_path, dataset_dir),
                "metadata_sha256": sha256_file(metadata_path),
                "n_grid": table.row_count,
                "n_columns": len(table.columns),
                "scf_converged": qa.get("scf_converged"),
                "electron_count_error_qa": qa.get("electron_count_error_qa"),
                "max_rel_angular_sigma": qa.get("max_rel_angular_sigma"),
                "tail_reaches_min_cutoff": qa.get("tail_reaches_min_cutoff"),
                "radii_monotonic": qa.get("radii_monotonic"),
            }
        )
        derived = metadata.get("derived", {})
        radii_rows.append(
            {
                "dataset_id": metadata.get("dataset_id"),
                "state_id": state_id,
                "basis_id": basis_id,
                "r_iso_0.003_e_bohr3_bohr": derived.get("r_iso_0.003_e_bohr3_bohr"),
                "r_iso_0.001_e_bohr3_bohr": derived.get("r_iso_0.001_e_bohr3_bohr"),
                "r_iso_0.0001_e_bohr3_bohr": derived.get("r_iso_0.0001_e_bohr3_bohr"),
            }
        )

    if not profile_rows:
        raise ValueError(f"{dataset_dir}: no metadata JSON files found")
    profile_tuple = tuple(sorted(profile_rows, key=lambda row: str(row["state_id"])))
    radii_tuple = tuple(sorted(radii_rows, key=lambda row: str(row["state_id"])))
    dataset_id = _require_single_dataset_id(profile_tuple, dataset_dir)
    basis_ids = sorted({str(row["basis_id"]) for row in profile_tuple})
    archive_formats = sorted(
        {_archive_format(dataset_dir / str(row["profile_archive"])) for row in profile_tuple}
    )
    method_summary = {
        "engines": sorted({str(row["engine"]) for row in profile_tuple}),
        "engine_versions": sorted({str(row["engine_version"]) for row in profile_tuple}),
        "xc": sorted({str(row["xc"]) for row in profile_tuple}),
        "relativity": sorted({str(row["relativity"]) for row in profile_tuple}),
    }
    manifest = {
        "schema_version": PROFILE_DATASET_MANIFEST_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "profile_count": len(profile_tuple),
        "state_ids": [str(row["state_id"]) for row in profile_tuple],
        "basis_ids": basis_ids,
        "profile_archive_formats": archive_formats,
        "files": {
            "profile_index": "profile_index.csv",
            "derived_radii": "derived_radii.csv",
            "profiles_dir": "profiles",
            "metadata_dir": "metadata",
        },
        "method_summary": method_summary,
        "qa_summary": _qa_summary(profile_tuple),
    }
    return DatasetIndexTables(dataset_dir, dataset_id, manifest, profile_tuple, radii_tuple)


def write_dataset_indexes(tables: DatasetIndexTables) -> tuple[Path, Path, Path]:
    """Write ``dataset_manifest.json``, ``profile_index.csv`` and ``derived_radii.csv``."""

    manifest_path = tables.dataset_dir / "dataset_manifest.json"
    profile_index_path = tables.dataset_dir / "profile_index.csv"
    derived_radii_path = tables.dataset_dir / "derived_radii.csv"
    write_json(manifest_path, tables.manifest)
    _write_csv(profile_index_path, PROFILE_INDEX_COLUMNS, tables.profile_index_rows)
    _write_csv(derived_radii_path, DERIVED_RADII_COLUMNS, tables.derived_radii_rows)
    return manifest_path, profile_index_path, derived_radii_path


def build_and_write_dataset_indexes(
    dataset_dir: Path,
    *,
    states_file: Path | None = None,
    basis_root: Path | None = None,
) -> DatasetIndexTables:
    """Build and write dataset-level index files for an existing generated dataset."""

    tables = build_dataset_index_tables(
        dataset_dir,
        states_file=states_file,
        basis_root=basis_root,
    )
    write_dataset_indexes(tables)
    return tables


def check_dataset_indexes(
    dataset_dir: Path,
    *,
    states_file: Path | None = None,
    basis_root: Path | None = None,
) -> DatasetIndexCheckResult:
    """Validate dataset-level index files against per-state artifacts."""

    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = dataset_dir / "dataset_manifest.json"
    profile_index_path = dataset_dir / "profile_index.csv"
    derived_radii_path = dataset_dir / "derived_radii.csv"
    for path in (manifest_path, profile_index_path, derived_radii_path):
        if not path.exists():
            errors.append(f"missing dataset index file: {path}")
    if errors:
        return DatasetIndexCheckResult(dataset_dir, tuple(errors), tuple(warnings))

    try:
        expected = build_dataset_index_tables(
            dataset_dir,
            states_file=states_file,
            basis_root=basis_root,
        )
        actual_manifest = read_strict_json(manifest_path)
        actual_profile_rows = _read_csv_rows(profile_index_path)
        actual_radii_rows = _read_csv_rows(derived_radii_path)
    except Exception as exc:
        errors.append(str(exc))
        return DatasetIndexCheckResult(dataset_dir, tuple(errors), tuple(warnings))

    if actual_manifest != expected.manifest:
        errors.append(f"{manifest_path}: does not match per-state artifacts")
    expected_profile_rows = tuple(
        {column: _csv_scalar(row.get(column)) for column in PROFILE_INDEX_COLUMNS}
        for row in expected.profile_index_rows
    )
    expected_radii_rows = tuple(
        {column: _csv_scalar(row.get(column)) for column in DERIVED_RADII_COLUMNS}
        for row in expected.derived_radii_rows
    )
    if actual_profile_rows != expected_profile_rows:
        errors.append(f"{profile_index_path}: does not match per-state artifacts")
    if actual_radii_rows != expected_radii_rows:
        errors.append(f"{derived_radii_path}: does not match per-state artifacts")
    return DatasetIndexCheckResult(dataset_dir, tuple(errors), tuple(warnings))


def check_profile_dataset_with_indexes(
    dataset_dir: Path,
    *,
    states_file: Path | None = None,
    basis_root: Path | None = None,
    require_profile_qa: bool = False,
    angular_sigma_tol: float = ANGULAR_SIGMA_DEFAULT_TOL,
    electron_count_abs_tol: float = ELECTRON_COUNT_ABS_TOL,
    electron_count_rel_tol: float = ELECTRON_COUNT_REL_TOL,
    require_indexes: bool = True,
) -> tuple[ProfileCheckResult, DatasetIndexCheckResult | None]:
    """Run per-state profile checks and, optionally, dataset-index checks."""

    profile_result = check_profile_dataset(
        dataset_dir,
        states_file=states_file,
        basis_root=basis_root,
        require_profile_qa=require_profile_qa,
        angular_sigma_tol=angular_sigma_tol,
        electron_count_abs_tol=electron_count_abs_tol,
        electron_count_rel_tol=electron_count_rel_tol,
    )
    if not require_indexes:
        return profile_result, None
    index_result = check_dataset_indexes(
        dataset_dir,
        states_file=states_file,
        basis_root=basis_root,
    )
    return profile_result, index_result
