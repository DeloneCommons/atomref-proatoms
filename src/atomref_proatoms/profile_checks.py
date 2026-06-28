"""Validation helpers for generated proatom profile artifacts."""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .basis import list_basis_bundles
from .datasets import expected_basis_for_dataset, state_allowed_in_dataset
from .profiles import DEFAULT_DENSITY_CUTOFFS, derived_radii, validate_profile_metadata
from .qa import (
    ELECTRON_COUNT_ABS_TOL,
    ELECTRON_COUNT_REL_TOL,
    electron_count_tolerance,
    radii_are_monotonic,
)
from .states import AtomState, load_atom_states

DENSITY_NONNEGATIVE_TOL = 1e-12
RADIUS_COMPARE_REL_TOL = 1e-8
RADIUS_COMPARE_ABS_TOL = 1e-10
ANGULAR_SIGMA_DEFAULT_TOL = 1e-8


@dataclass(frozen=True)
class ProfileTable:
    """Parsed profile archive payload."""

    archive_path: Path
    inner_csv_name: str
    state_id: str
    columns: dict[str, list[float]]

    @property
    def row_count(self) -> int:
        return len(self.columns["r_bohr"])


@dataclass(frozen=True)
class ProfileCheckResult:
    """Result of checking one dataset directory."""

    dataset_dir: Path
    checked_profiles: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


class ProfileCheckError(ValueError):
    """Raised for invalid generated profile artifacts."""


def _reject_json_constant(token: str) -> None:
    raise ValueError(f"non-standard JSON constant {token!r}")


def read_strict_json(path: Path) -> Any:
    """Read JSON while rejecting NaN/Infinity tokens."""

    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except ValueError as exc:
        raise ProfileCheckError(f"{path}: invalid strict JSON: {exc}") from exc


def _state_id_from_archive_name(path: Path) -> str:
    name = path.name
    if name.endswith(".csv.zip"):
        return name.removesuffix(".csv.zip")
    if name.endswith(".csv.gz"):
        return name.removesuffix(".csv.gz")
    raise ProfileCheckError(f"{path}: unsupported profile archive suffix")


def _read_profile_archive_text(path: Path) -> tuple[str, str]:
    """Return ``(inner_csv_name, csv_text)`` from a supported profile archive."""

    expected_state_id = _state_id_from_archive_name(path)
    expected_inner_name = f"{expected_state_id}.csv"
    if path.name.endswith(".csv.zip"):
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                if names != [expected_inner_name]:
                    raise ProfileCheckError(
                        f"{path}: expected exactly one inner file {expected_inner_name!r}, "
                        f"got {names!r}"
                    )
                return names[0], archive.read(names[0]).decode("utf-8")
        except zipfile.BadZipFile as exc:
            raise ProfileCheckError(f"{path}: invalid ZIP archive") from exc
    if path.name.endswith(".csv.gz"):
        try:
            with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
                return expected_inner_name, handle.read()
        except OSError as exc:
            raise ProfileCheckError(f"{path}: invalid gzip archive") from exc
    raise ProfileCheckError(f"{path}: unsupported profile archive suffix")


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _parse_finite_float(value: str, *, path: Path, field: str, row_number: int) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ProfileCheckError(
            f"{path}: row {row_number} column {field!r} is not a float: {value!r}"
        ) from exc
    if not math.isfinite(number):
        raise ProfileCheckError(f"{path}: row {row_number} column {field!r} is non-finite")
    return number


def read_profile_table(path: Path) -> ProfileTable:
    """Read and validate the basic CSV structure from one profile archive."""

    inner_csv_name, text = _read_profile_archive_text(path)
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ProfileCheckError(f"{path}: missing CSV header")
    required = {"r_bohr", "rho_e_bohr3"}
    missing = sorted(required - set(reader.fieldnames))
    if missing:
        raise ProfileCheckError(f"{path}: missing profile columns {missing}")

    columns: dict[str, list[float]] = {field: [] for field in reader.fieldnames}
    for row_number, row in enumerate(reader, start=2):
        for field in reader.fieldnames:
            columns[field].append(
                _parse_finite_float(row[field] or "", path=path, field=field, row_number=row_number)
            )
    if len(columns["r_bohr"]) < 2:
        raise ProfileCheckError(f"{path}: at least two profile rows are required")
    return ProfileTable(
        archive_path=path,
        inner_csv_name=inner_csv_name,
        state_id=_state_id_from_archive_name(path),
        columns=columns,
    )


def validate_profile_table(table: ProfileTable) -> list[str]:
    """Return structural/numerical errors for one parsed profile table."""

    errors: list[str] = []
    r_values = table.columns["r_bohr"]
    rho_values = table.columns["rho_e_bohr3"]
    if any(value <= 0 for value in r_values):
        errors.append(f"{table.archive_path}: all r_bohr values must be positive")
    if any(r_values[i] >= r_values[i + 1] for i in range(len(r_values) - 1)):
        errors.append(f"{table.archive_path}: r_bohr must be strictly increasing")
    min_rho = min(rho_values)
    if min_rho < -DENSITY_NONNEGATIVE_TOL:
        errors.append(
            f"{table.archive_path}: rho_e_bohr3 has value {min_rho:g} below "
            f"-{DENSITY_NONNEGATIVE_TOL:g}"
        )
    if "rho_std_ang_e_bohr3" in table.columns:
        sigma = table.columns["rho_std_ang_e_bohr3"]
        min_sigma = min(sigma)
        if min_sigma < -DENSITY_NONNEGATIVE_TOL:
            errors.append(
                f"{table.archive_path}: rho_std_ang_e_bohr3 has value {min_sigma:g} "
                f"below -{DENSITY_NONNEGATIVE_TOL:g}"
            )
    if "nelec_cumulative_profile" in table.columns:
        cumulative = table.columns["nelec_cumulative_profile"]
        if cumulative[0] < -DENSITY_NONNEGATIVE_TOL:
            errors.append(f"{table.archive_path}: cumulative electron count starts negative")
        if any(cumulative[i] > cumulative[i + 1] + 1e-10 for i in range(len(cumulative) - 1)):
            errors.append(f"{table.archive_path}: cumulative electron count must be nondecreasing")
        if cumulative[-1] <= 0:
            errors.append(f"{table.archive_path}: final cumulative electron count must be positive")
    return errors


def _metadata_state_errors(metadata: dict[str, Any], state: AtomState | None) -> list[str]:
    if state is None:
        return []
    errors: list[str] = []
    state_metadata = metadata.get("state")
    if not isinstance(state_metadata, dict):
        return [f"{metadata.get('state_id', '<unknown>')}: state metadata must be an object"]
    expected = {
        "symbol": state.symbol,
        "charge": state.charge,
        "spin_2s": state.spin_2s,
        "multiplicity": state.multiplicity,
        "configuration": state.record["configuration"],
        "spin_model": state.record["spin_model"],
        "occupation_policy": state.record["occupation_policy"],
        "state_category": state.record["state_category"],
        "curation_status": state.record["curation_status"],
    }
    for key, expected_value in expected.items():
        if state_metadata.get(key) != expected_value:
            errors.append(
                f"{state.state_id}: metadata state.{key}={state_metadata.get(key)!r} "
                f"!= curated {expected_value!r}"
            )
    return errors


def _metadata_dataset_errors(metadata: dict[str, Any], state: AtomState | None) -> list[str]:
    errors: list[str] = []
    dataset_id = str(metadata.get("dataset_id", ""))
    method = metadata.get("method")
    if not isinstance(method, dict):
        return errors
    basis_id = str(method.get("basis_id", ""))
    try:
        expected_basis = expected_basis_for_dataset(dataset_id)
    except ValueError as exc:
        errors.append(str(exc))
    else:
        if basis_id != expected_basis:
            errors.append(
                f"{metadata.get('state_id', '<unknown>')}: dataset {dataset_id} requires "
                f"basis {expected_basis}, got {basis_id}"
            )
    if state is not None and dataset_id:
        try:
            allowed = state_allowed_in_dataset(dataset_id, z=state.z, charge=state.charge)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if not allowed:
                errors.append(
                    f"{state.state_id}: state Z={state.z}, charge={state.charge} is not allowed "
                    f"in dataset {dataset_id}"
                )
    return errors


def _metadata_basis_errors(metadata: dict[str, Any], basis_by_id: dict[str, Any]) -> list[str]:
    method = metadata.get("method")
    if not isinstance(method, dict):
        return []
    basis_id = str(method.get("basis_id", ""))
    if not basis_by_id or basis_id not in basis_by_id:
        return []
    expected_sha = basis_by_id[basis_id].basis_sha256
    actual_sha = method.get("basis_sha256")
    if actual_sha != expected_sha:
        return [
            f"{metadata.get('state_id', '<unknown>')}: basis_sha256 {actual_sha!r} "
            f"!= frozen {expected_sha!r}"
        ]
    return []


def _derived_radius_errors(table: ProfileTable, metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    metadata_derived = metadata.get("derived")
    if not isinstance(metadata_derived, dict):
        return [f"{table.state_id}: metadata.derived must be an object"]
    try:
        actual_derived = derived_radii(
            table.columns["r_bohr"], table.columns["rho_e_bohr3"], DEFAULT_DENSITY_CUTOFFS
        )
    except ValueError as exc:
        errors.append(f"{table.state_id}: cannot derive cutoff radii from profile: {exc}")
        return errors
    for key, actual_value in actual_derived.items():
        metadata_value = metadata_derived.get(key)
        if not _is_finite_number(metadata_value):
            errors.append(f"{table.state_id}: metadata.derived.{key} must be a finite number")
            continue
        if not math.isclose(
            float(metadata_value),
            actual_value,
            rel_tol=RADIUS_COMPARE_REL_TOL,
            abs_tol=RADIUS_COMPARE_ABS_TOL,
        ):
            errors.append(
                f"{table.state_id}: metadata.derived.{key}={metadata_value!r} does not match "
                f"profile-derived {actual_value:.17g}"
            )
    if not radii_are_monotonic(actual_derived):
        errors.append(f"{table.state_id}: profile-derived cutoff radii are not monotonic")
    return errors


def _qa_errors_and_warnings(
    metadata: dict[str, Any],
    state: AtomState | None,
    *,
    require_profile_qa: bool,
    angular_sigma_tol: float,
    electron_count_abs_tol: float,
    electron_count_rel_tol: float,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    qa = metadata.get("qa")
    if not isinstance(qa, dict):
        return [f"{metadata.get('state_id', '<unknown>')}: metadata.qa must be an object"], warnings
    state_id = str(metadata.get("state_id", "<unknown>"))
    if qa.get("scf_converged") is not True:
        errors.append(f"{state_id}: qa.scf_converged must be true for a release/check profile")
    if qa.get("tail_reaches_min_cutoff") is not True:
        errors.append(f"{state_id}: qa.tail_reaches_min_cutoff must be true")
    if qa.get("radii_monotonic") is not True:
        errors.append(f"{state_id}: qa.radii_monotonic must be true")

    electron_count_error = qa.get("electron_count_error_qa")
    if electron_count_error is None:
        message = f"{state_id}: independent QA electron count was skipped"
        if require_profile_qa:
            errors.append(message)
        else:
            warnings.append(message)
    elif not _is_finite_number(electron_count_error):
        errors.append(f"{state_id}: qa.electron_count_error_qa must be finite or null")
    elif state is not None:
        tolerance = electron_count_tolerance(
            state.electron_count,
            abs_tol=electron_count_abs_tol,
            rel_tol=electron_count_rel_tol,
        )
        if abs(float(electron_count_error)) > tolerance:
            errors.append(
                f"{state_id}: qa.electron_count_error_qa={float(electron_count_error):g} "
                f"exceeds tolerance {tolerance:g} "
                f"(abs_tol={electron_count_abs_tol:g}, rel_tol={electron_count_rel_tol:g})"
            )

    angular_sigma = qa.get("max_rel_angular_sigma")
    if angular_sigma is None:
        message = f"{state_id}: angular-sigma QA summary is not recorded yet"
        if require_profile_qa:
            errors.append(message)
        else:
            warnings.append(message)
    elif not _is_finite_number(angular_sigma):
        errors.append(f"{state_id}: qa.max_rel_angular_sigma must be finite or null")
    elif float(angular_sigma) > angular_sigma_tol:
        errors.append(
            f"{state_id}: qa.max_rel_angular_sigma={float(angular_sigma):g} exceeds "
            f"tolerance {angular_sigma_tol:g}"
        )
    return errors, warnings


def _diagnostic_errors_and_warnings(
    metadata: dict[str, Any],
    state: AtomState | None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    state_id = str(metadata.get("state_id", "<unknown>"))
    diagnostics = metadata.get("diagnostics")
    if diagnostics is None or diagnostics == {}:
        return errors, warnings
    if not isinstance(diagnostics, dict):
        return [f"{state_id}: metadata.diagnostics must be an object"], warnings

    spin = diagnostics.get("spin")
    if spin is not None:
        if not isinstance(spin, dict):
            errors.append(f"{state_id}: metadata.diagnostics.spin must be an object")
        else:
            if state is not None:
                expected_mult = state.spin_2s + 1
                expected_ss = (state.spin_2s / 2.0) * (state.spin_2s / 2.0 + 1.0)
                if spin.get("target_spin_2s") != state.spin_2s:
                    errors.append(f"{state_id}: diagnostics.spin.target_spin_2s mismatch")
                if spin.get("target_multiplicity") != expected_mult:
                    errors.append(f"{state_id}: diagnostics.spin.target_multiplicity mismatch")
                target_ss = spin.get("target_spin_square")
                if not _is_finite_number(target_ss) or not math.isclose(
                    float(target_ss), expected_ss, rel_tol=1.0e-12, abs_tol=1.0e-12
                ):
                    errors.append(f"{state_id}: diagnostics.spin.target_spin_square mismatch")
            for key in (
                "reported_spin_square",
                "reported_multiplicity",
                "spin_square_deviation",
                "multiplicity_deviation",
            ):
                value = spin.get(key)
                if value is not None and not _is_finite_number(value):
                    errors.append(f"{state_id}: diagnostics.spin.{key} must be finite or null")

    linear = diagnostics.get("linear_dependency")
    if linear is not None:
        if not isinstance(linear, dict):
            errors.append(f"{state_id}: metadata.diagnostics.linear_dependency must be an object")
        else:
            warning_count = linear.get("warning_count")
            if not isinstance(warning_count, int) or isinstance(warning_count, bool) or warning_count < 0:
                errors.append(
                    f"{state_id}: diagnostics.linear_dependency.warning_count must be a "
                    "non-negative integer"
                )
            vectors_removed = linear.get("vectors_removed")
            if vectors_removed is not None and (
                not isinstance(vectors_removed, int)
                or isinstance(vectors_removed, bool)
                or vectors_removed < 0
            ):
                errors.append(
                    f"{state_id}: diagnostics.linear_dependency.vectors_removed must be "
                    "a non-negative integer or null"
                )
            qa = metadata.get("qa")
            if isinstance(qa, dict) and qa.get("linear_dependency_vectors_removed") != vectors_removed:
                errors.append(
                    f"{state_id}: qa.linear_dependency_vectors_removed does not match "
                    "diagnostics.linear_dependency.vectors_removed"
                )
    return errors, warnings


def _find_archive_for_state(profiles_dir: Path, state_id: str) -> tuple[Path | None, list[str]]:
    candidates = [profiles_dir / f"{state_id}.csv.zip", profiles_dir / f"{state_id}.csv.gz"]
    existing = [path for path in candidates if path.exists()]
    if len(existing) > 1:
        return None, [f"{state_id}: both .csv.zip and .csv.gz profile archives exist"]
    if not existing:
        return None, [f"{state_id}: missing profile archive"]
    return existing[0], []


def check_profile_dataset(
    dataset_dir: Path,
    *,
    states_file: Path | None = None,
    basis_root: Path | None = None,
    require_profile_qa: bool = False,
    angular_sigma_tol: float = ANGULAR_SIGMA_DEFAULT_TOL,
    electron_count_abs_tol: float = ELECTRON_COUNT_ABS_TOL,
    electron_count_rel_tol: float = ELECTRON_COUNT_REL_TOL,
) -> ProfileCheckResult:
    """Validate generated profile archives and metadata under one dataset directory."""

    errors: list[str] = []
    warnings: list[str] = []
    profiles_dir = dataset_dir / "profiles"
    metadata_dir = dataset_dir / "metadata"
    if not dataset_dir.is_dir():
        errors.append(f"missing dataset directory: {dataset_dir}")
        return ProfileCheckResult(dataset_dir, 0, tuple(errors), tuple(warnings))
    if not profiles_dir.is_dir():
        errors.append(f"missing profiles directory: {profiles_dir}")
    if not metadata_dir.is_dir():
        errors.append(f"missing metadata directory: {metadata_dir}")
    if errors:
        return ProfileCheckResult(dataset_dir, 0, tuple(errors), tuple(warnings))

    states_by_id: dict[str, AtomState] = {}
    if states_file is not None and states_file.exists():
        states_by_id = {state.state_id: state for state in load_atom_states(states_file)}
    basis_by_id: dict[str, Any] = {}
    if basis_root is not None and basis_root.exists():
        basis_by_id = {bundle.basis_id: bundle for bundle in list_basis_bundles(basis_root)}

    metadata_paths = sorted(metadata_dir.glob("*.json"))
    archive_paths = sorted(profiles_dir.glob("*.csv.zip")) + sorted(profiles_dir.glob("*.csv.gz"))
    metadata_state_ids = {path.stem for path in metadata_paths}
    archive_state_ids = {_state_id_from_archive_name(path) for path in archive_paths}
    for state_id in sorted(archive_state_ids - metadata_state_ids):
        errors.append(f"{state_id}: profile archive exists without matching metadata JSON")

    checked = 0
    for metadata_path in metadata_paths:
        state_id = metadata_path.stem
        try:
            metadata = read_strict_json(metadata_path)
        except ProfileCheckError as exc:
            errors.append(str(exc))
            continue
        if not isinstance(metadata, dict):
            errors.append(f"{metadata_path}: metadata root must be a JSON object")
            continue
        if metadata.get("state_id") != state_id:
            errors.append(
                f"{metadata_path}: state_id {metadata.get('state_id')!r} does not match filename"
            )
        errors.extend(f"{metadata_path}: {error}" for error in validate_profile_metadata(metadata))
        state = states_by_id.get(state_id)
        if states_by_id and state is None:
            errors.append(f"{metadata_path}: unknown state_id {state_id!r} in curated states")
        errors.extend(_metadata_state_errors(metadata, state))
        errors.extend(_metadata_dataset_errors(metadata, state))
        errors.extend(_metadata_basis_errors(metadata, basis_by_id))

        archive_path, archive_errors = _find_archive_for_state(profiles_dir, state_id)
        errors.extend(archive_errors)
        if archive_path is None:
            continue
        try:
            table = read_profile_table(archive_path)
        except ProfileCheckError as exc:
            errors.append(str(exc))
            continue
        if table.state_id != state_id:
            errors.append(f"{archive_path}: archive state_id does not match metadata filename")
        errors.extend(validate_profile_table(table))
        errors.extend(_derived_radius_errors(table, metadata))
        qa_errors, qa_warnings = _qa_errors_and_warnings(
            metadata,
            state,
            require_profile_qa=require_profile_qa,
            angular_sigma_tol=angular_sigma_tol,
            electron_count_abs_tol=electron_count_abs_tol,
            electron_count_rel_tol=electron_count_rel_tol,
        )
        diagnostic_errors, diagnostic_warnings = _diagnostic_errors_and_warnings(metadata, state)
        errors.extend(qa_errors)
        errors.extend(diagnostic_errors)
        warnings.extend(qa_warnings)
        warnings.extend(diagnostic_warnings)
        checked += 1

    return ProfileCheckResult(dataset_dir, checked, tuple(errors), tuple(warnings))
