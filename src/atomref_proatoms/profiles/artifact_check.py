"""Consistency checks for generated profile/radii/QA release artifacts."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..dataio.basis import list_basis_bundles
from ..dataio.datasets import ProfileDatasetConfig, load_profile_dataset_config
from ..dataio.paths import (
    BASIS_ROOT,
    PROFILE_DATASETS_FILE,
    PROFILES_ROOT,
    QA_ROOT,
    RADII_ROOT,
    STATES_FILE,
    repo_relative_path,
)
from ..dataio.schemas import PROFILE_DATASET_MANIFEST_SCHEMA_VERSION
from ..engines.pyscf_backend import (
    SCF_REUSE_FINGERPRINT_KEYS,
    SCFSettings,
    scf_settings_reuse_digest,
    stable_json_digest,
)
from ..states.state_tables import load_atom_states, state_digest
from .artifacts import (
    QA_DATASET_SCHEMA_VERSION,
    QA_OVERVIEW_SCHEMA_VERSION,
    RADII_DATASET_SCHEMA_VERSION,
    profile_density_column,
)
from .basis_sensitivity import (
    BASIS_SENSITIVITY_DIRNAME,
    BASIS_SENSITIVITY_FILES,
    BASIS_SENSITIVITY_SCHEMA_VERSION,
)
from .build_plan import ProfileBuildJob, build_jobs_for_datasets

ROOT_README = "README.md"
QA_OVERVIEW_FILES = {"qa_summary.csv", "qa_report.md", "metadata.json"}
SPECIAL_QA_DIRS = {BASIS_SENSITIVITY_DIRNAME}


@dataclass(frozen=True)
class GeneratedArtifactCheck:
    """Result object returned by the generated-artifact checker."""

    profile_data_version: str
    configured_dataset_ids: tuple[str, ...]
    checked_dataset_ids: tuple[str, ...]
    state_count: int
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def _load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive detail in error text
        errors.append(f"{repo_relative_path(path)}: cannot read JSON ({exc})")
        return None
    if not isinstance(data, dict):
        errors.append(f"{repo_relative_path(path)}: JSON root must be an object")
        return None
    return data


def _root_dataset_dirs(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {
        path.name
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }


def _root_files(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {
        path.name
        for path in root.iterdir()
        if path.is_file() and not path.name.startswith(".")
    }


def _format_set(values: Sequence[str] | set[str]) -> str:
    return "[" + ", ".join(sorted(values)) + "]"


def _check_root_files(root: Path, *, allowed: set[str], errors: list[str]) -> None:
    files = _root_files(root)
    unexpected = files - allowed
    if unexpected:
        errors.append(
            f"{repo_relative_path(root)}: unexpected root files {_format_set(unexpected)}; "
            f"allowed files are {_format_set(allowed)}"
        )


def _group_jobs_by_dataset(
    jobs: Sequence[ProfileBuildJob],
) -> dict[str, tuple[ProfileBuildJob, ...]]:
    grouped: dict[str, list[ProfileBuildJob]] = {}
    for job in jobs:
        grouped.setdefault(job.dataset_id, []).append(job)
    return {dataset_id: tuple(dataset_jobs) for dataset_id, dataset_jobs in grouped.items()}


def _read_csv_rows(path: Path, errors: list[str]) -> list[dict[str, str]] | None:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except Exception as exc:  # pragma: no cover - defensive detail in error text
        errors.append(f"{repo_relative_path(path)}: cannot read CSV ({exc})")
        return None


def _read_csv_header_and_row_count(path: Path, errors: list[str]) -> tuple[list[str], int] | None:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration:
                errors.append(f"{repo_relative_path(path)}: empty CSV")
                return None
            return header, sum(1 for _row in reader)
    except Exception as exc:  # pragma: no cover - defensive detail in error text
        errors.append(f"{repo_relative_path(path)}: cannot read CSV ({exc})")
        return None


def _require_files(directory: Path, filenames: Sequence[str], errors: list[str]) -> bool:
    ok = True
    for filename in filenames:
        path = directory / filename
        if not path.is_file():
            errors.append(f"missing {repo_relative_path(path)}")
            ok = False
    return ok


def _check_common_metadata(
    metadata: Mapping[str, Any],
    *,
    metadata_path: Path,
    schema_version: str,
    profile_data_version: str,
    dataset_id: str,
    basis_id: str,
    errors: list[str],
) -> None:
    label = repo_relative_path(metadata_path)
    if metadata.get("schema_version") != schema_version:
        errors.append(
            f"{label}: schema_version must be {schema_version!r}, "
            f"got {metadata.get('schema_version')!r}"
        )
    if metadata.get("profile_data_version") != profile_data_version:
        errors.append(
            f"{label}: profile_data_version must be {profile_data_version!r}, "
            f"got {metadata.get('profile_data_version')!r}"
        )
    if metadata.get("dataset_id") != dataset_id:
        errors.append(
            f"{label}: dataset_id must be {dataset_id!r}, "
            f"got {metadata.get('dataset_id')!r}"
        )
    if metadata.get("basis_id") != basis_id:
        errors.append(
            f"{label}: basis_id must be {basis_id!r}, "
            f"got {metadata.get('basis_id')!r}"
        )


def _check_profiles_dataset(
    *,
    dataset_id: str,
    dataset_dir: Path,
    radii_root: Path,
    qa_root: Path,
    jobs: tuple[ProfileBuildJob, ...],
    config: ProfileDatasetConfig,
    basis_sha256_by_id: Mapping[str, str],
    state_record_sha256_by_id: Mapping[str, str],
    errors: list[str],
) -> None:
    profiles_csv = dataset_dir / "profiles.csv"
    metadata_json = dataset_dir / "metadata.json"
    if not _require_files(dataset_dir, ("profiles.csv", "metadata.json"), errors):
        return

    expected_state_ids = [job.state_id for job in jobs]
    expected_columns = [profile_density_column(state_id) for state_id in expected_state_ids]
    header_count = _read_csv_header_and_row_count(profiles_csv, errors)
    if header_count is not None:
        header, row_count = header_count
        expected_header = ["r_bohr", *expected_columns]
        if header != expected_header:
            errors.append(
                f"{repo_relative_path(profiles_csv)}: header does not match active build plan"
            )
        expected_n = int(config.profile_grid.get("n", 0) or 0)
        if expected_n and row_count != expected_n:
            errors.append(
                f"{repo_relative_path(profiles_csv)}: expected {expected_n} radial rows, "
                f"got {row_count}"
            )

    metadata = _load_json(metadata_json, errors)
    if metadata is None:
        return
    basis_id = jobs[0].basis_id if jobs else config.scope(dataset_id).basis_id
    _check_common_metadata(
        metadata,
        metadata_path=metadata_json,
        schema_version=PROFILE_DATASET_MANIFEST_SCHEMA_VERSION,
        profile_data_version=config.profile_data_version,
        dataset_id=dataset_id,
        basis_id=basis_id,
        errors=errors,
    )
    if metadata.get("density_model") != config.defaults.get("density_model"):
        errors.append(
            f"{repo_relative_path(metadata_json)}: density_model does not match active config"
        )
    if metadata.get("profile_grid") != dict(config.profile_grid):
        errors.append(f"{repo_relative_path(metadata_json)}: profile_grid does not match config")
    if metadata.get("qa_grid") != dict(config.qa_grid):
        errors.append(f"{repo_relative_path(metadata_json)}: qa_grid does not match config")
    if metadata.get("cutoffs_e_bohr3") != list(config.cutoffs_e_bohr3):
        errors.append(
            f"{repo_relative_path(metadata_json)}: cutoffs_e_bohr3 does not match config"
        )

    current_basis_sha = basis_sha256_by_id.get(basis_id)
    if current_basis_sha is not None and metadata.get("basis_sha256") != current_basis_sha:
        errors.append(
            f"{repo_relative_path(metadata_json)}: basis_sha256 must be "
            f"{current_basis_sha!r}, got {metadata.get('basis_sha256')!r}"
        )
    method = metadata.get("method", {})
    if isinstance(method, Mapping):
        expected_method = {
            "engine": str(config.defaults.get("engine", "pyscf")),
            "engine_version": str(config.defaults.get("expected_engine_version", "")),
            "scf_type": str(config.defaults.get("scf_type", "")),
            "xc": str(config.defaults.get("xc", "")),
            "relativity": str(config.defaults.get("relativity", "sf-X2C-1e")),
            "basis_id": basis_id,
        }
        if current_basis_sha is not None:
            expected_method["basis_sha256"] = current_basis_sha
        for key, expected in expected_method.items():
            if expected and method.get(key) != expected:
                errors.append(
                    f"{repo_relative_path(metadata_json)}: method[{key!r}] must be "
                    f"{expected!r}, got {method.get(key)!r}"
                )
    else:
        errors.append(f"{repo_relative_path(metadata_json)}: method must be an object")

    state_keys = (
        set(metadata.get("states", {}))
        if isinstance(metadata.get("states"), Mapping)
        else set()
    )
    if state_keys != set(expected_state_ids):
        errors.append(
            f"{repo_relative_path(metadata_json)}: states do not match active build plan"
        )
    column_keys = (
        set(metadata.get("columns", {}))
        if isinstance(metadata.get("columns"), Mapping)
        else set()
    )
    if column_keys != set(expected_columns):
        errors.append(
            f"{repo_relative_path(metadata_json)}: columns do not match "
            "profiles.csv/build plan"
        )
    related = metadata.get("related_artifacts", {})
    if isinstance(related, Mapping):
        expected_related = {
            "profiles_csv": repo_relative_path(profiles_csv),
            "profile_metadata_json": repo_relative_path(metadata_json),
            "radii_csv": repo_relative_path(radii_root / dataset_id / "radii.csv"),
            "radii_metadata_json": repo_relative_path(radii_root / dataset_id / "metadata.json"),
            "qa_csv": repo_relative_path(qa_root / dataset_id / "qa.csv"),
            "qa_metadata_json": repo_relative_path(qa_root / dataset_id / "metadata.json"),
        }
        for key, value in expected_related.items():
            if related.get(key) != value:
                errors.append(
                    f"{repo_relative_path(metadata_json)}: related_artifacts[{key!r}] "
                    f"must be {value!r}, got {related.get(key)!r}"
                )
    else:
        errors.append(f"{repo_relative_path(metadata_json)}: related_artifacts must be an object")

    scf_artifacts = metadata.get("scf_artifacts", {})
    if not isinstance(scf_artifacts, Mapping):
        errors.append(f"{repo_relative_path(metadata_json)}: scf_artifacts must be an object")
        return
    artifact_keys = set(scf_artifacts)
    if artifact_keys != set(expected_state_ids):
        errors.append(
            f"{repo_relative_path(metadata_json)}: scf_artifacts do not match active build plan"
        )
    expected_fingerprints = _expected_reuse_fingerprints(
        config=config,
        basis_sha256=current_basis_sha,
    )
    for state_id in expected_state_ids:
        artifact = scf_artifacts.get(state_id, {})
        if not isinstance(artifact, Mapping):
            errors.append(
                f"{repo_relative_path(metadata_json)}: scf_artifacts[{state_id!r}] "
                "must be an object"
            )
            continue
        results = artifact.get("results", {})
        if not isinstance(results, Mapping) or results.get("converged") is not True:
            errors.append(
                f"{repo_relative_path(metadata_json)}: scf_artifacts[{state_id!r}] "
                "does not record a converged SCF"
            )
        fingerprints = artifact.get("fingerprints", {})
        if not isinstance(fingerprints, Mapping):
            errors.append(
                f"{repo_relative_path(metadata_json)}: scf_artifacts[{state_id!r}] "
                "fingerprints must be an object"
            )
            continue
        state_digest_expected = state_record_sha256_by_id.get(state_id)
        per_state_expected = dict(expected_fingerprints)
        if state_digest_expected is not None:
            per_state_expected["state_record_sha256"] = state_digest_expected
        accepted_settings_digests = _expected_scf_settings_digests(config)
        for key in SCF_REUSE_FINGERPRINT_KEYS:
            if key == "scf_settings_sha256":
                actual = fingerprints.get(key)
                if actual not in accepted_settings_digests:
                    errors.append(
                        f"{repo_relative_path(metadata_json)}: scf_artifacts[{state_id!r}] "
                        f"fingerprint {key!r} must be one of "
                        f"{sorted(accepted_settings_digests)!r}, got {actual!r}"
                    )
                continue
            if key in per_state_expected and fingerprints.get(key) != per_state_expected[key]:
                errors.append(
                    f"{repo_relative_path(metadata_json)}: scf_artifacts[{state_id!r}] "
                    f"fingerprint {key!r} must be {per_state_expected[key]!r}, "
                    f"got {fingerprints.get(key)!r}"
                )


def _csv_state_ids(path: Path, errors: list[str]) -> list[str] | None:
    rows = _read_csv_rows(path, errors)
    if rows is None:
        return None
    if rows and "state_id" not in rows[0]:
        errors.append(f"{repo_relative_path(path)}: missing state_id column")
        return None
    return [row.get("state_id", "") for row in rows]


def _check_radii_dataset(
    *,
    dataset_id: str,
    dataset_dir: Path,
    jobs: tuple[ProfileBuildJob, ...],
    config: ProfileDatasetConfig,
    errors: list[str],
) -> None:
    radii_csv = dataset_dir / "radii.csv"
    metadata_json = dataset_dir / "metadata.json"
    if not _require_files(dataset_dir, ("radii.csv", "metadata.json"), errors):
        return
    expected_state_ids = [job.state_id for job in jobs]
    state_ids = _csv_state_ids(radii_csv, errors)
    if state_ids is not None and state_ids != expected_state_ids:
        errors.append(
            f"{repo_relative_path(radii_csv)}: state rows do not match active build plan"
        )
    metadata = _load_json(metadata_json, errors)
    if metadata is None:
        return
    basis_id = jobs[0].basis_id if jobs else config.scope(dataset_id).basis_id
    _check_common_metadata(
        metadata,
        metadata_path=metadata_json,
        schema_version=RADII_DATASET_SCHEMA_VERSION,
        profile_data_version=config.profile_data_version,
        dataset_id=dataset_id,
        basis_id=basis_id,
        errors=errors,
    )
    if metadata.get("row_count") != len(expected_state_ids):
        errors.append(
            f"{repo_relative_path(metadata_json)}: row_count must be {len(expected_state_ids)}, "
            f"got {metadata.get('row_count')!r}"
        )


def _truthy_csv_value(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def _check_qa_dataset(
    *,
    dataset_id: str,
    dataset_dir: Path,
    jobs: tuple[ProfileBuildJob, ...],
    config: ProfileDatasetConfig,
    require_qa_pass: bool,
    errors: list[str],
) -> None:
    qa_csv = dataset_dir / "qa.csv"
    metadata_json = dataset_dir / "metadata.json"
    if not _require_files(dataset_dir, ("qa.csv", "metadata.json"), errors):
        return
    expected_state_ids = [job.state_id for job in jobs]
    rows = _read_csv_rows(qa_csv, errors)
    if rows is not None:
        state_ids = [row.get("state_id", "") for row in rows]
        if state_ids != expected_state_ids:
            errors.append(
                f"{repo_relative_path(qa_csv)}: state rows do not match "
                "active build plan"
            )
        if require_qa_pass:
            failed = [
                row.get("state_id", "")
                for row in rows
                if not _truthy_csv_value(row.get("overall_pass", ""))
            ]
            if failed:
                errors.append(
                    f"{repo_relative_path(qa_csv)}: QA failures present for "
                    f"{_format_set(failed)}"
                )
    metadata = _load_json(metadata_json, errors)
    if metadata is None:
        return
    basis_id = jobs[0].basis_id if jobs else config.scope(dataset_id).basis_id
    _check_common_metadata(
        metadata,
        metadata_path=metadata_json,
        schema_version=QA_DATASET_SCHEMA_VERSION,
        profile_data_version=config.profile_data_version,
        dataset_id=dataset_id,
        basis_id=basis_id,
        errors=errors,
    )
    if metadata.get("row_count") != len(expected_state_ids):
        errors.append(
            f"{repo_relative_path(metadata_json)}: row_count must be {len(expected_state_ids)}, "
            f"got {metadata.get('row_count')!r}"
        )
    if require_qa_pass and metadata.get("failed_count") not in {0, None}:
        errors.append(
            f"{repo_relative_path(metadata_json)}: failed_count must be 0, "
            f"got {metadata.get('failed_count')!r}"
        )


def _check_qa_overview(
    *,
    qa_root: Path,
    expected_dataset_ids: tuple[str, ...],
    expected_counts: Mapping[str, int],
    config: ProfileDatasetConfig,
    require_qa_pass: bool,
    errors: list[str],
) -> None:
    if not _require_files(qa_root, ("qa_summary.csv", "qa_report.md", "metadata.json"), errors):
        return
    summary_csv = qa_root / "qa_summary.csv"
    rows = _read_csv_rows(summary_csv, errors)
    if rows is not None:
        row_ids = [row.get("dataset_id", "") for row in rows]
        if row_ids != list(expected_dataset_ids):
            errors.append(
                f"{repo_relative_path(summary_csv)}: dataset rows do not match "
                "active datasets"
            )
        for row in rows:
            dataset_id = row.get("dataset_id", "")
            expected_count = expected_counts.get(dataset_id)
            if expected_count is None:
                continue
            if str(row.get("state_count", "")) != str(expected_count):
                errors.append(
                    f"{repo_relative_path(summary_csv)}: {dataset_id} state_count must be "
                    f"{expected_count}, got {row.get('state_count')!r}"
                )
            if require_qa_pass and str(row.get("failed_count", "")) not in {"0", "0.0"}:
                errors.append(
                    f"{repo_relative_path(summary_csv)}: {dataset_id} failed_count must be 0, "
                    f"got {row.get('failed_count')!r}"
                )
    metadata = _load_json(qa_root / "metadata.json", errors)
    if metadata is None:
        return
    if metadata.get("schema_version") != QA_OVERVIEW_SCHEMA_VERSION:
        errors.append(
            f"{repo_relative_path(qa_root / 'metadata.json')}: schema_version must be "
            f"{QA_OVERVIEW_SCHEMA_VERSION!r}, got {metadata.get('schema_version')!r}"
        )
    if metadata.get("profile_data_version") != config.profile_data_version:
        errors.append(
            f"{repo_relative_path(qa_root / 'metadata.json')}: profile_data_version must be "
            f"{config.profile_data_version!r}, got {metadata.get('profile_data_version')!r}"
        )
    expected_state_count = sum(expected_counts.values())
    if metadata.get("dataset_count") != len(expected_dataset_ids):
        errors.append(
            f"{repo_relative_path(qa_root / 'metadata.json')}: dataset_count must be "
            f"{len(expected_dataset_ids)}, got {metadata.get('dataset_count')!r}"
        )
    if metadata.get("state_count") != expected_state_count:
        errors.append(
            f"{repo_relative_path(qa_root / 'metadata.json')}: state_count must be "
            f"{expected_state_count}, got {metadata.get('state_count')!r}"
        )
    if require_qa_pass and metadata.get("failed_count") not in {0, None}:
        errors.append(
            f"{repo_relative_path(qa_root / 'metadata.json')}: failed_count must be 0, "
            f"got {metadata.get('failed_count')!r}"
        )


def _metadata_int(metadata: Mapping[str, Any], key: str) -> int:
    value = metadata.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _check_basis_sensitivity_qa(
    directory: Path, *, config: ProfileDatasetConfig, errors: list[str]
) -> None:
    """Validate optional diffuse-basis sensitivity QA artifacts when present."""

    if not _require_files(directory, sorted(BASIS_SENSITIVITY_FILES), errors):
        return
    metadata = _load_json(directory / "metadata.json", errors)
    if metadata is None:
        return
    label = repo_relative_path(directory / "metadata.json")
    if metadata.get("schema_version") != BASIS_SENSITIVITY_SCHEMA_VERSION:
        errors.append(
            f"{label}: schema_version must be {BASIS_SENSITIVITY_SCHEMA_VERSION!r}, "
            f"got {metadata.get('schema_version')!r}"
        )
    if metadata.get("profile_data_version") != config.profile_data_version:
        errors.append(
            f"{label}: profile_data_version must be {config.profile_data_version!r}, "
            f"got {metadata.get('profile_data_version')!r}"
        )
    expected_counts = {
        "basis_sensitivity.csv": _metadata_int(metadata, "row_count"),
        "basis_sensitivity_summary.csv": _metadata_int(metadata, "summary_count"),
        "basis_sensitivity_outliers.csv": _metadata_int(metadata, "outlier_count"),
    }
    for filename, expected_count in expected_counts.items():
        header_count = _read_csv_header_and_row_count(directory / filename, errors)
        if header_count is None:
            continue
        _header, row_count = header_count
        if expected_count >= 0 and row_count != expected_count:
            errors.append(
                f"{repo_relative_path(directory / filename)}: expected {expected_count} rows, "
                f"got {row_count}"
            )


def _scf_settings_from_config(
    config: ProfileDatasetConfig, *, max_cycle: int | None = None
) -> SCFSettings:
    defaults = config.defaults
    relativity = str(defaults.get("relativity", "sf-X2C-1e"))
    return SCFSettings(
        xc=str(defaults.get("xc", "PBE0")),
        use_x2c=relativity != "none",
        conv_tol=float(defaults.get("conv_tol", 1e-9)),
        max_cycle=int(
            max_cycle if max_cycle is not None else defaults.get("max_cycle", 300)
        ),
        diis_space=int(defaults.get("diis_space", 12)),
        diis_start_cycle=int(defaults.get("diis_start_cycle", 1)),
        grid_level=int(defaults.get("grid_level", 4)),
    )


def _expected_scf_settings_digest(config: ProfileDatasetConfig) -> str:
    settings = _scf_settings_from_config(config)
    return scf_settings_reuse_digest(settings.to_fingerprint_json())


def _expected_scf_settings_digests(config: ProfileDatasetConfig) -> set[str]:
    """Return accepted current and legacy SCF-settings digests.

    Older v2 pre-release artifacts included ``max_cycle`` in the digest.  The
    current digest excludes it because it is a convergence-attempt limit rather
    than part of the converged SCF solution.
    """

    current = _scf_settings_from_config(config)
    digests = {scf_settings_reuse_digest(current.to_fingerprint_json())}
    for max_cycle in {100, current.max_cycle}:
        legacy = _scf_settings_from_config(config, max_cycle=max_cycle)
        digests.add(stable_json_digest(legacy.to_fingerprint_json()))
    return digests


def _expected_reuse_fingerprints(
    *, config: ProfileDatasetConfig, basis_sha256: str | None
) -> dict[str, str]:
    expected = {
        "scf_settings_sha256": _expected_scf_settings_digest(config),
        "engine_version": str(config.defaults.get("expected_engine_version", "")),
        "density_model": str(config.defaults.get("density_model", "")),
        "scf_type": str(config.defaults.get("scf_type", "")),
    }
    if basis_sha256 is not None:
        expected["basis_sha256"] = basis_sha256
    return expected


def _basis_sha256_by_id(errors: list[str]) -> dict[str, str]:
    try:
        bundles = list_basis_bundles(BASIS_ROOT)
    except Exception as exc:
        errors.append(f"Could not validate current basis bundle fingerprints: {exc}")
        return {}
    return {bundle.basis_id: bundle.basis_sha256 for bundle in bundles}


def check_generated_artifacts(
    *,
    config_path: Path = PROFILE_DATASETS_FILE,
    states_file: Path = STATES_FILE,
    profiles_root: Path = PROFILES_ROOT,
    radii_root: Path = RADII_ROOT,
    qa_root: Path = QA_ROOT,
    allow_empty: bool = True,
    allow_partial: bool = False,
    require_qa_pass: bool = True,
) -> GeneratedArtifactCheck:
    """Validate generated profile, radii, and QA artifacts against active v2 config.

    The checker is intentionally safe before generation: an entirely empty generated
    artifact layer passes by default.  Once any generated dataset directory exists,
    the default release-gate mode requires all generated dataset roots to contain
    exactly the configured dataset IDs and current ``profile_data_version``.
    """

    config = load_profile_dataset_config(config_path)
    states = load_atom_states(states_file)
    state_record_sha256_by_id = {state.state_id: state_digest(state.record) for state in states}
    jobs_by_dataset = _group_jobs_by_dataset(
        build_jobs_for_datasets(states, dataset_ids=config.dataset_ids, config=config)
    )
    expected_all = set(config.dataset_ids)
    profile_dirs = _root_dataset_dirs(profiles_root)
    radii_dirs = _root_dataset_dirs(radii_root)
    qa_all_dirs = _root_dataset_dirs(qa_root)
    basis_sensitivity_present = BASIS_SENSITIVITY_DIRNAME in qa_all_dirs
    qa_dirs = qa_all_dirs - SPECIAL_QA_DIRS
    generated_any = bool(profile_dirs or radii_dirs or qa_dirs)
    errors: list[str] = []

    if not generated_any:
        _check_root_files(profiles_root, allowed={ROOT_README}, errors=errors)
        _check_root_files(radii_root, allowed={ROOT_README}, errors=errors)
        _check_root_files(qa_root, allowed={ROOT_README}, errors=errors)
        if basis_sensitivity_present:
            _check_basis_sensitivity_qa(
                qa_root / BASIS_SENSITIVITY_DIRNAME,
                config=config,
                errors=errors,
            )
        if not allow_empty:
            errors.append("no generated profile/radii/QA dataset directories found")
        return GeneratedArtifactCheck(
            profile_data_version=config.profile_data_version,
            configured_dataset_ids=config.dataset_ids,
            checked_dataset_ids=(),
            state_count=0,
            errors=tuple(errors),
        )

    basis_sha256_by_id = _basis_sha256_by_id(errors)
    generated_union = profile_dirs | radii_dirs | qa_dirs
    unexpected = generated_union - expected_all
    if unexpected:
        errors.append(
            "generated dataset directories not in active config: "
            f"{_format_set(unexpected)}"
        )

    if allow_partial:
        expected_dirs = tuple(
            dataset_id for dataset_id in config.dataset_ids if dataset_id in generated_union
        )
    else:
        expected_dirs = config.dataset_ids
        missing = expected_all - generated_union
        if missing:
            errors.append(f"missing generated dataset directories: {_format_set(missing)}")

    expected_set = set(expected_dirs)
    for label, root, actual in (
        ("profiles", profiles_root, profile_dirs),
        ("radii", radii_root, radii_dirs),
        ("qa", qa_root, qa_dirs),
    ):
        extra = actual - expected_set
        missing = expected_set - actual
        if extra:
            errors.append(
                f"{repo_relative_path(root)}: unexpected {label} dataset dirs "
                f"{_format_set(extra)}"
            )
        if missing:
            errors.append(
                f"{repo_relative_path(root)}: missing {label} dataset dirs "
                f"{_format_set(missing)}"
            )

    _check_root_files(profiles_root, allowed={ROOT_README}, errors=errors)
    _check_root_files(radii_root, allowed={ROOT_README}, errors=errors)
    _check_root_files(qa_root, allowed={ROOT_README, *QA_OVERVIEW_FILES}, errors=errors)
    if basis_sensitivity_present:
        _check_basis_sensitivity_qa(
            qa_root / BASIS_SENSITIVITY_DIRNAME,
            config=config,
            errors=errors,
        )

    checked_counts: dict[str, int] = {}
    for dataset_id in expected_dirs:
        jobs = jobs_by_dataset.get(dataset_id, ())
        checked_counts[dataset_id] = len(jobs)
        if not jobs:
            errors.append(f"{dataset_id}: active build plan has no states")
            continue
        _check_profiles_dataset(
            dataset_id=dataset_id,
            dataset_dir=profiles_root / dataset_id,
            radii_root=radii_root,
            qa_root=qa_root,
            jobs=jobs,
            config=config,
            basis_sha256_by_id=basis_sha256_by_id,
            state_record_sha256_by_id=state_record_sha256_by_id,
            errors=errors,
        )
        _check_radii_dataset(
            dataset_id=dataset_id,
            dataset_dir=radii_root / dataset_id,
            jobs=jobs,
            config=config,
            errors=errors,
        )
        _check_qa_dataset(
            dataset_id=dataset_id,
            dataset_dir=qa_root / dataset_id,
            jobs=jobs,
            config=config,
            require_qa_pass=require_qa_pass,
            errors=errors,
        )

    if expected_dirs:
        _check_qa_overview(
            qa_root=qa_root,
            expected_dataset_ids=expected_dirs,
            expected_counts=checked_counts,
            config=config,
            require_qa_pass=require_qa_pass,
            errors=errors,
        )

    return GeneratedArtifactCheck(
        profile_data_version=config.profile_data_version,
        configured_dataset_ids=config.dataset_ids,
        checked_dataset_ids=expected_dirs,
        state_count=sum(checked_counts.values()),
        errors=tuple(errors),
    )
