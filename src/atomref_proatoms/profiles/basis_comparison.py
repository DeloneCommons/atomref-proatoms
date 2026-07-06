"""Primary basis-family profile comparisons for generated profile datasets.

The primary comparison layer is intentionally separate from supplemented/
augmented basis sensitivity.  It compares named primary basis families over their
shared state coverage and writes auditable, non-SCF QA artifacts under
``data/qa/basis_comparisons``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..dataio.datasets import (
    PRIMARY_DYALL_V4Z,
    PRIMARY_X2C_QZVPALL,
    ProfileDatasetConfig,
    load_profile_dataset_config,
)
from ..dataio.paths import (
    PROFILE_DATASETS_FILE,
    PROFILES_ROOT,
    QA_ROOT,
    STATES_FILE,
    repo_relative_path,
)
from ..states.state_tables import AtomState, load_atom_states
from .artifacts import write_json
from .basis_sensitivity import (
    DEFAULT_MAX_CUMULATIVE_DELTA_OUTLIER_ELECTRONS,
    DEFAULT_MAX_CUMULATIVE_DELTA_WATCH_ELECTRONS,
    DEFAULT_MAX_ELECTRON_COUNT_ERROR,
    DEFAULT_MEAN_RADIAL_SHIFT_OUTLIER_ANGSTROM,
    DEFAULT_MEAN_RADIAL_SHIFT_WATCH_ANGSTROM,
    DEFAULT_RELATIVE_L1_OUTLIER,
    DEFAULT_RELATIVE_L1_WATCH,
    _metric_distribution_rows,
    _ordered_fieldnames,
    _write_dict_rows_csv,
    compare_profile_pair,
    read_profile_dataset,
)
from .build_plan import build_jobs_for_datasets

BASIS_COMPARISON_SCHEMA_VERSION = "atomref.proatoms.basis_comparison.v1"
BASIS_COMPARISONS_DIRNAME = "basis_comparisons"
PRIMARY_BASIS_COMPARISON_KIND = "primary_basis_family_comparison"
BASIS_COMPARISON_FILES = frozenset({"metadata.json"})

# The left/right order fixes the sign convention: all signed deltas are
# right-minus-left, i.e. dyall-v4z minus x2c-QZVPall for the current artifact.
DEFAULT_PRIMARY_BASIS_COMPARISON_PAIRS: tuple[tuple[str, str], ...] = (
    (PRIMARY_X2C_QZVPALL, PRIMARY_DYALL_V4Z),
)

PAIR_OUTPUT_DIRNAMES = {
    (PRIMARY_X2C_QZVPALL, PRIMARY_DYALL_V4Z): "x2c-QZVPall__dyall-v4z",
}

ROW_PREFIX = [
    "comparison_id",
    "comparison_kind",
    "left_dataset_id",
    "right_dataset_id",
    "left_basis_id",
    "right_basis_id",
    "state_id",
    "symbol",
    "z",
    "charge",
    "electron_count",
    "state_category",
    "state_role",
    "integrity_status",
    "comparison_tier",
    "comparison_flags",
    "integrity_flags",
]
SUMMARY_PREFIX = [
    "comparison_id",
    "comparison_kind",
    "left_dataset_id",
    "right_dataset_id",
    "left_basis_id",
    "right_basis_id",
    "expected_state_count",
    "common_state_count",
    "integrity_fail_count",
    "outlier_count",
    "low_comparison_count",
    "moderate_comparison_count",
    "high_comparison_count",
]
DISTRIBUTION_PREFIX = [
    "comparison_id",
    "comparison_kind",
    "group_kind",
    "group_value",
    "metric",
    "n",
    "min",
    "p50",
    "p90",
    "p95",
    "p99",
    "max",
]


@dataclass(frozen=True)
class BasisComparisonResult:
    """Paths and summary for written primary basis-comparison artifacts."""

    output_dir: Path
    metadata_json: Path
    row_count: int
    summary_count: int
    outlier_count: int
    metric_distribution_count: int
    skipped_pairs: tuple[dict[str, Any], ...]
    pair_outputs: Mapping[str, Mapping[str, str]]


def configured_primary_basis_comparison_pairs(
    config: ProfileDatasetConfig,
) -> tuple[tuple[str, str], ...]:
    """Return configured primary basis-family comparison pairs."""

    configured = set(config.dataset_ids)
    return tuple(
        pair
        for pair in DEFAULT_PRIMARY_BASIS_COMPARISON_PAIRS
        if pair[0] in configured and pair[1] in configured
    )


def _expected_state_ids_for_pair(
    *,
    states: Sequence[AtomState] | None,
    config: ProfileDatasetConfig,
    left_dataset_id: str,
    right_dataset_id: str,
) -> tuple[str, ...] | None:
    if states is None:
        return None
    left_state_ids = {
        job.state_id
        for job in build_jobs_for_datasets(
            list(states), dataset_ids=(left_dataset_id,), config=config
        )
    }
    right_state_ids = {
        job.state_id
        for job in build_jobs_for_datasets(
            list(states), dataset_ids=(right_dataset_id,), config=config
        )
    }
    return tuple(
        job.state_id
        for job in build_jobs_for_datasets(
            list(states), dataset_ids=(left_dataset_id,), config=config
        )
        if job.state_id in right_state_ids and job.state_id in left_state_ids
    )


def _comparison_id(left_basis_id: str, right_basis_id: str) -> str:
    return f"{left_basis_id}__{right_basis_id}"


def _pair_output_dirname(left_dataset_id: str, right_dataset_id: str) -> str:
    return PAIR_OUTPUT_DIRNAMES.get(
        (left_dataset_id, right_dataset_id),
        f"{left_dataset_id}__{right_dataset_id}".replace("/", "_"),
    )


def _rename_row(raw: Mapping[str, Any], *, comparison_id: str) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key, value in raw.items():
        new_key = key
        if new_key == "base_dataset_id":
            new_key = "left_dataset_id"
        elif new_key == "diffuse_dataset_id":
            new_key = "right_dataset_id"
        elif new_key == "base_basis_id":
            new_key = "left_basis_id"
        elif new_key == "diffuse_basis_id":
            new_key = "right_basis_id"
        elif new_key == "base_state_record_sha256":
            new_key = "left_state_record_sha256"
        elif new_key == "diffuse_state_record_sha256":
            new_key = "right_state_record_sha256"
        elif new_key == "release_gate_status":
            new_key = "integrity_status"
        elif new_key == "sensitivity_tier":
            new_key = "comparison_tier"
        elif new_key == "sensitivity_flags":
            new_key = "comparison_flags"
        elif new_key == "status":
            continue
        elif new_key.startswith("base_"):
            new_key = "left_" + new_key.removeprefix("base_")
        elif new_key.startswith("diffuse_"):
            new_key = "right_" + new_key.removeprefix("diffuse_")
        row[new_key] = value
    row["comparison_id"] = comparison_id
    row["comparison_kind"] = PRIMARY_BASIS_COMPARISON_KIND
    return row


def _rename_summary(raw: Mapping[str, Any], *, comparison_id: str) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in raw.items():
        new_key = key
        if new_key == "base_dataset_id":
            new_key = "left_dataset_id"
        elif new_key == "diffuse_dataset_id":
            new_key = "right_dataset_id"
        elif new_key == "base_basis_id":
            new_key = "left_basis_id"
        elif new_key == "diffuse_basis_id":
            new_key = "right_basis_id"
        elif new_key == "release_gate_fail_count":
            new_key = "integrity_fail_count"
        elif new_key == "low_sensitivity_count":
            new_key = "low_comparison_count"
        elif new_key == "moderate_sensitivity_count":
            new_key = "moderate_comparison_count"
        elif new_key == "high_sensitivity_count":
            new_key = "high_comparison_count"
        elif new_key.startswith("base_"):
            new_key = "left_" + new_key.removeprefix("base_")
        elif new_key.startswith("diffuse_"):
            new_key = "right_" + new_key.removeprefix("diffuse_")
        summary[new_key] = value
    summary["comparison_id"] = comparison_id
    summary["comparison_kind"] = PRIMARY_BASIS_COMPARISON_KIND
    return summary


def _comparison_outliers(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in rows
        if row.get("integrity_status") == "FAIL" or row.get("comparison_tier") == "high"
    ]


def _root_has_outputs(output_dir: Path) -> bool:
    return output_dir.exists() and any(output_dir.iterdir())


def build_primary_basis_comparisons(
    *,
    config_path: Path = PROFILE_DATASETS_FILE,
    states_file: Path | None = STATES_FILE,
    profiles_root: Path = PROFILES_ROOT,
    qa_root: Path = QA_ROOT,
    pairs: Sequence[tuple[str, str]] | None = None,
    force: bool = False,
    require_complete: bool = True,
    relative_l1_watch: float = DEFAULT_RELATIVE_L1_WATCH,
    relative_l1_outlier: float = DEFAULT_RELATIVE_L1_OUTLIER,
    max_cumulative_delta_watch_electrons: float = DEFAULT_MAX_CUMULATIVE_DELTA_WATCH_ELECTRONS,
    max_cumulative_delta_outlier_electrons: float = DEFAULT_MAX_CUMULATIVE_DELTA_OUTLIER_ELECTRONS,
    mean_radial_shift_watch_angstrom: float = DEFAULT_MEAN_RADIAL_SHIFT_WATCH_ANGSTROM,
    mean_radial_shift_outlier_angstrom: float = DEFAULT_MEAN_RADIAL_SHIFT_OUTLIER_ANGSTROM,
    max_electron_count_error: float = DEFAULT_MAX_ELECTRON_COUNT_ERROR,
) -> BasisComparisonResult:
    """Build primary basis-family comparison artifacts from committed profiles."""

    config = load_profile_dataset_config(config_path)
    selected_pairs = tuple(pairs or configured_primary_basis_comparison_pairs(config))
    if not selected_pairs:
        raise ValueError("no configured primary basis-comparison pairs found")
    states = load_atom_states(states_file) if states_file is not None else None

    output_dir = qa_root / BASIS_COMPARISONS_DIRNAME
    if _root_has_outputs(output_dir) and not force:
        raise FileExistsError(f"{repo_relative_path(output_dir)} exists; use --force to overwrite")
    output_dir.mkdir(parents=True, exist_ok=True)

    pair_outputs: dict[str, dict[str, str]] = {}
    skipped_pairs: list[dict[str, Any]] = []
    completeness_errors: list[str] = []
    total_rows = 0
    total_summaries = 0
    total_outliers = 0
    total_distributions = 0
    comparison_pairs_metadata: list[dict[str, Any]] = []

    for left_dataset_id, right_dataset_id in selected_pairs:
        left_dir = profiles_root / left_dataset_id
        right_dir = profiles_root / right_dataset_id
        if not left_dir.is_dir() or not right_dir.is_dir():
            skipped = {
                "left_dataset_id": left_dataset_id,
                "right_dataset_id": right_dataset_id,
                "reason": "missing_profile_dataset_dir",
                "left_present": left_dir.is_dir(),
                "right_present": right_dir.is_dir(),
            }
            skipped_pairs.append(skipped)
            if require_complete:
                completeness_errors.append(
                    f"{left_dataset_id} -> {right_dataset_id}: missing profile dataset dir"
                )
            continue

        expected_state_ids = _expected_state_ids_for_pair(
            states=states,
            config=config,
            left_dataset_id=left_dataset_id,
            right_dataset_id=right_dataset_id,
        )
        left = read_profile_dataset(profiles_root, left_dataset_id)
        right = read_profile_dataset(profiles_root, right_dataset_id)
        raw_rows, raw_summary = compare_profile_pair(
            left,
            right,
            cutoffs_e_bohr3=config.cutoffs_e_bohr3,
            expected_state_ids=expected_state_ids,
            relative_l1_watch=relative_l1_watch,
            relative_l1_outlier=relative_l1_outlier,
            max_cumulative_delta_watch_electrons=max_cumulative_delta_watch_electrons,
            max_cumulative_delta_outlier_electrons=max_cumulative_delta_outlier_electrons,
            mean_radial_shift_watch_angstrom=mean_radial_shift_watch_angstrom,
            mean_radial_shift_outlier_angstrom=mean_radial_shift_outlier_angstrom,
            max_electron_count_error=max_electron_count_error,
        )
        if require_complete and (
            raw_summary["missing_base_state_count"] or raw_summary["missing_diffuse_state_count"]
        ):
            completeness_errors.append(
                f"{left_dataset_id} -> {right_dataset_id}: missing expected states "
                f"left={raw_summary['missing_base_state_ids']!r}, "
                f"right={raw_summary['missing_diffuse_state_ids']!r}"
            )

        pair_comparison_id = _comparison_id(left.basis_id, right.basis_id)
        rows = [_rename_row(row, comparison_id=pair_comparison_id) for row in raw_rows]
        summary = _rename_summary(raw_summary, comparison_id=pair_comparison_id)
        outliers = _comparison_outliers(rows)
        distributions = _metric_distribution_rows(
            rows,
            comparison_id=pair_comparison_id,
            comparison_kind=PRIMARY_BASIS_COMPARISON_KIND,
        )

        pair_dirname = _pair_output_dirname(left_dataset_id, right_dataset_id)
        pair_output_dir = output_dir / pair_dirname
        pair_output_dir.mkdir(parents=True, exist_ok=True)
        rows_csv = pair_output_dir / "basis_comparison.csv"
        summary_csv = pair_output_dir / "basis_comparison_summary.csv"
        outliers_csv = pair_output_dir / "basis_comparison_outliers.csv"
        distributions_csv = pair_output_dir / "basis_comparison_metric_distributions.csv"
        _write_dict_rows_csv(rows_csv, _ordered_fieldnames(rows, ROW_PREFIX), rows)
        _write_dict_rows_csv(
            summary_csv,
            _ordered_fieldnames([summary], SUMMARY_PREFIX),
            [summary],
        )
        _write_dict_rows_csv(outliers_csv, _ordered_fieldnames(outliers, ROW_PREFIX), outliers)
        _write_dict_rows_csv(
            distributions_csv,
            _ordered_fieldnames(distributions, DISTRIBUTION_PREFIX),
            distributions,
        )
        pair_outputs[pair_comparison_id] = {
            "output_dir": repo_relative_path(pair_output_dir),
            "rows_csv": repo_relative_path(rows_csv),
            "summary_csv": repo_relative_path(summary_csv),
            "outliers_csv": repo_relative_path(outliers_csv),
            "metric_distributions_csv": repo_relative_path(distributions_csv),
            "row_count": str(len(rows)),
            "summary_count": "1",
            "outlier_count": str(len(outliers)),
            "metric_distribution_count": str(len(distributions)),
        }
        comparison_pairs_metadata.append(
            {
                "comparison_id": pair_comparison_id,
                "comparison_kind": PRIMARY_BASIS_COMPARISON_KIND,
                "left_dataset_id": left_dataset_id,
                "right_dataset_id": right_dataset_id,
                "left_basis_id": left.basis_id,
                "right_basis_id": right.basis_id,
                "output_dirname": pair_dirname,
                "delta_convention": "signed deltas are right-minus-left",
                "state_matching": "state_id plus matching state_record_sha256 digest",
            }
        )
        total_rows += len(rows)
        total_summaries += 1
        total_outliers += len(outliers)
        total_distributions += len(distributions)

    if completeness_errors:
        raise ValueError("incomplete primary basis comparison:\n" + "\n".join(completeness_errors))
    if total_rows == 0:
        raise ValueError(
            "no primary basis-comparison rows were generated; "
            f"skipped_pairs={skipped_pairs!r}"
        )

    metadata_json = output_dir / "metadata.json"
    write_json(
        metadata_json,
        {
            "schema_version": BASIS_COMPARISON_SCHEMA_VERSION,
            "profile_data_version": config.profile_data_version,
            "config": repo_relative_path(config_path),
            "states_file": None if states_file is None else repo_relative_path(states_file),
            "profiles_root": repo_relative_path(profiles_root),
            "qa_root": repo_relative_path(qa_root),
            "output_root": repo_relative_path(output_dir),
            "pair_outputs": pair_outputs,
            "comparison_pairs": comparison_pairs_metadata,
            "skipped_pairs": skipped_pairs,
            "row_count": total_rows,
            "summary_count": total_summaries,
            "outlier_count": total_outliers,
            "metric_distribution_count": total_distributions,
            "thresholds": {
                "relative_l1_watch": relative_l1_watch,
                "relative_l1_outlier": relative_l1_outlier,
                "max_cumulative_delta_watch_electrons": max_cumulative_delta_watch_electrons,
                "max_cumulative_delta_outlier_electrons": max_cumulative_delta_outlier_electrons,
                "mean_radial_shift_watch_angstrom": mean_radial_shift_watch_angstrom,
                "mean_radial_shift_outlier_angstrom": mean_radial_shift_outlier_angstrom,
                "max_electron_count_error": max_electron_count_error,
            },
            "interpretation": {
                "comparison_kind": (
                    "Primary basis-family comparison over exact matched states. It is not a "
                    "supplemented/augmented basis-sensitivity comparison."
                ),
                "integrity_status": (
                    "PASS/FAIL metadata, grid, digest, density, "
                    "or electron-count gate"
                ),
                "comparison_tier": "low/moderate/high scientific difference classification",
                "outliers_csv": (
                    "Rows with high basis-family differences or integrity failures; high "
                    "basis-family difference is not by itself a release blocker."
                ),
            },
            "notes": [
                (
                    "The current comparison matches x2c-QZVPall and dyall-v4z over the H-Rn "
                    "overlap by state_id and state_record_sha256."
                ),
                (
                    "Signed metric deltas are right-minus-left: dyall-v4z minus x2c-QZVPall "
                    "for the current comparison."
                ),
            ],
        },
    )
    return BasisComparisonResult(
        output_dir=output_dir,
        metadata_json=metadata_json,
        row_count=total_rows,
        summary_count=total_summaries,
        outlier_count=total_outliers,
        metric_distribution_count=total_distributions,
        skipped_pairs=tuple(skipped_pairs),
        pair_outputs=pair_outputs,
    )
