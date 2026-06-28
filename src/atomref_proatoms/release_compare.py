"""Cross-dataset comparisons for release-candidate profile archives."""

from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from .profile_checks import _reject_json_constant
from .release_package import DEFAULT_ARCHIVE_ROOT, RELEASE_MANIFEST_NAME

DEFAULT_RADIUS_COLUMNS = (
    "r_iso_0.003_e_bohr3_bohr",
    "r_iso_0.001_e_bohr3_bohr",
    "r_iso_0.0001_e_bohr3_bohr",
)


@dataclass(frozen=True)
class ReleaseDatasetTable:
    """Derived-radii/profile-index rows for one dataset in a release archive."""

    archive_path: Path
    archive_root: str
    dataset_id: str
    derived_rows_by_state: dict[str, dict[str, str]]
    profile_rows_by_state: dict[str, dict[str, str]]

    @property
    def state_ids(self) -> set[str]:
        return set(self.derived_rows_by_state)


@dataclass(frozen=True)
class RadiusComparisonSummary:
    """Summary statistics for one radius column in a dataset comparison."""

    radius_column: str
    compared_count: int
    mean_delta_bohr: float | None
    mean_abs_delta_bohr: float | None
    max_abs_delta_bohr: float | None
    max_abs_delta_state_id: str | None
    max_abs_rel_delta: float | None
    max_abs_rel_delta_state_id: str | None


@dataclass(frozen=True)
class ReleaseDatasetComparison:
    """Pairwise comparison of matching states between two profile datasets."""

    left_dataset_id: str
    right_dataset_id: str
    common_state_ids: tuple[str, ...]
    left_only_state_ids: tuple[str, ...]
    right_only_state_ids: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    summaries: tuple[RadiusComparisonSummary, ...]

    @property
    def common_count(self) -> int:
        return len(self.common_state_ids)


@dataclass(frozen=True)
class ReleaseComparisonResult:
    """Result of comparing all requested release dataset pairs."""

    archives: tuple[Path, ...]
    dataset_ids: tuple[str, ...]
    comparisons: tuple[ReleaseDatasetComparison, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def _read_strict_json(payload: bytes, *, label: str) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8"), parse_constant=_reject_json_constant)
    if not isinstance(data, dict):
        raise ValueError(f"{label}: JSON root must be an object")
    return data


def _read_csv_rows(payload: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))


def _float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _safe_rel_delta(delta: float, reference: float) -> float | None:
    if reference == 0.0:
        return None
    return delta / reference


def _radius_columns_from_rows(
    rows_by_state: dict[str, dict[str, str]], requested: tuple[str, ...]
) -> tuple[str, ...]:
    if requested:
        return requested
    for row in rows_by_state.values():
        return tuple(key for key in row if key.startswith("r_iso_") and key.endswith("_bohr"))
    return DEFAULT_RADIUS_COLUMNS


def read_release_dataset_tables(
    archive_path: Path,
    *,
    dataset_ids: tuple[str, ...] = (),
) -> tuple[ReleaseDatasetTable, ...]:
    """Read derived-radii/profile-index tables from one release-candidate archive."""

    tables: list[ReleaseDatasetTable] = []
    with zipfile.ZipFile(archive_path) as zip_handle:
        names = set(zip_handle.namelist())
        if RELEASE_MANIFEST_NAME not in names:
            raise ValueError(f"{archive_path}: missing {RELEASE_MANIFEST_NAME}")
        manifest = _read_strict_json(
            zip_handle.read(RELEASE_MANIFEST_NAME), label=RELEASE_MANIFEST_NAME
        )
        archive_root = str(manifest.get("archive_root") or DEFAULT_ARCHIVE_ROOT).strip("/")
        manifest_dataset_ids = tuple(str(item) for item in manifest.get("dataset_ids", ()))
        selected_dataset_ids = dataset_ids or manifest_dataset_ids
        missing = sorted(set(selected_dataset_ids) - set(manifest_dataset_ids))
        if missing:
            raise ValueError(
                f"{archive_path}: selected dataset(s) not present in release manifest: "
                + ", ".join(missing)
            )
        for dataset_id in selected_dataset_ids:
            prefix = f"{archive_root}/{dataset_id}"
            derived_name = f"{prefix}/derived_radii.csv"
            profile_index_name = f"{prefix}/profile_index.csv"
            if derived_name not in names:
                raise ValueError(f"{archive_path}: missing {derived_name}")
            if profile_index_name not in names:
                raise ValueError(f"{archive_path}: missing {profile_index_name}")
            derived_rows = _read_csv_rows(zip_handle.read(derived_name))
            profile_rows = _read_csv_rows(zip_handle.read(profile_index_name))
            derived_by_state = {
                str(row.get("state_id")): row for row in derived_rows if row.get("state_id")
            }
            profile_by_state = {
                str(row.get("state_id")): row for row in profile_rows if row.get("state_id")
            }
            tables.append(
                ReleaseDatasetTable(
                    archive_path=archive_path,
                    archive_root=archive_root,
                    dataset_id=dataset_id,
                    derived_rows_by_state=derived_by_state,
                    profile_rows_by_state=profile_by_state,
                )
            )
    return tuple(tables)


def load_release_dataset_tables(
    archive_paths: tuple[Path, ...],
    *,
    dataset_ids: tuple[str, ...] = (),
) -> tuple[ReleaseDatasetTable, ...]:
    """Load dataset comparison tables from one or more release archives."""

    tables: list[ReleaseDatasetTable] = []
    seen_dataset_ids: set[str] = set()
    for archive_path in archive_paths:
        archive_tables = read_release_dataset_tables(archive_path, dataset_ids=dataset_ids)
        for table in archive_tables:
            if table.dataset_id in seen_dataset_ids:
                raise ValueError(
                    f"duplicate dataset_id across selected release archives: {table.dataset_id}"
                )
            seen_dataset_ids.add(table.dataset_id)
            tables.append(table)
    return tuple(tables)


def parse_dataset_pair(value: str) -> tuple[str, str]:
    """Parse a CLI pair string of the form ``left_dataset_id:right_dataset_id``."""

    if ":" not in value:
        raise ValueError(f"dataset pair must have form LEFT:RIGHT, got {value!r}")
    left, right = value.split(":", 1)
    left = left.strip()
    right = right.strip()
    if not left or not right:
        raise ValueError(f"dataset pair must have non-empty sides, got {value!r}")
    if left == right:
        raise ValueError(f"dataset pair cannot compare a dataset with itself: {value!r}")
    return left, right


def _state_info(table: ReleaseDatasetTable, state_id: str) -> dict[str, str]:
    return table.profile_rows_by_state.get(state_id) or table.derived_rows_by_state.get(state_id) or {}


def compare_dataset_tables(
    left: ReleaseDatasetTable,
    right: ReleaseDatasetTable,
    *,
    radius_columns: tuple[str, ...] = DEFAULT_RADIUS_COLUMNS,
) -> ReleaseDatasetComparison:
    """Compare radii for matching states in two release datasets."""

    common_state_ids = tuple(sorted(left.state_ids & right.state_ids))
    left_only = tuple(sorted(left.state_ids - right.state_ids))
    right_only = tuple(sorted(right.state_ids - left.state_ids))
    columns = _radius_columns_from_rows(left.derived_rows_by_state, radius_columns)
    rows: list[dict[str, Any]] = []

    for state_id in common_state_ids:
        left_row = left.derived_rows_by_state[state_id]
        right_row = right.derived_rows_by_state[state_id]
        left_info = _state_info(left, state_id)
        right_info = _state_info(right, state_id)
        for column in columns:
            left_value = _float_or_none(left_row.get(column))
            right_value = _float_or_none(right_row.get(column))
            if left_value is None or right_value is None:
                continue
            delta = right_value - left_value
            rel_delta = _safe_rel_delta(delta, left_value)
            rows.append(
                {
                    "left_dataset_id": left.dataset_id,
                    "right_dataset_id": right.dataset_id,
                    "state_id": state_id,
                    "symbol": left_info.get("symbol") or right_info.get("symbol") or "",
                    "charge": left_info.get("charge") or right_info.get("charge") or "",
                    "state_category": left_info.get("state_category")
                    or right_info.get("state_category")
                    or "",
                    "left_basis_id": left_row.get("basis_id") or left_info.get("basis_id") or "",
                    "right_basis_id": right_row.get("basis_id") or right_info.get("basis_id") or "",
                    "radius_column": column,
                    "left_radius_bohr": left_value,
                    "right_radius_bohr": right_value,
                    "delta_right_minus_left_bohr": delta,
                    "abs_delta_bohr": abs(delta),
                    "rel_delta_right_minus_left": rel_delta,
                    "abs_rel_delta": None if rel_delta is None else abs(rel_delta),
                }
            )

    summaries = _summarize_rows(rows, columns)
    return ReleaseDatasetComparison(
        left_dataset_id=left.dataset_id,
        right_dataset_id=right.dataset_id,
        common_state_ids=common_state_ids,
        left_only_state_ids=left_only,
        right_only_state_ids=right_only,
        rows=tuple(rows),
        summaries=summaries,
    )


def _summarize_rows(
    rows: list[dict[str, Any]], radius_columns: tuple[str, ...]
) -> tuple[RadiusComparisonSummary, ...]:
    summaries: list[RadiusComparisonSummary] = []
    for column in radius_columns:
        selected = [row for row in rows if row["radius_column"] == column]
        if not selected:
            summaries.append(
                RadiusComparisonSummary(column, 0, None, None, None, None, None, None)
            )
            continue
        deltas = [float(row["delta_right_minus_left_bohr"]) for row in selected]
        abs_deltas = [float(row["abs_delta_bohr"]) for row in selected]
        rel_values = [
            float(row["abs_rel_delta"])
            for row in selected
            if row.get("abs_rel_delta") is not None
        ]
        max_abs_delta = max(abs_deltas)
        max_abs_delta_row = selected[abs_deltas.index(max_abs_delta)]
        max_abs_rel_delta = max(rel_values) if rel_values else None
        max_abs_rel_delta_state_id = None
        if max_abs_rel_delta is not None:
            for row in selected:
                if row.get("abs_rel_delta") == max_abs_rel_delta:
                    max_abs_rel_delta_state_id = str(row["state_id"])
                    break
        summaries.append(
            RadiusComparisonSummary(
                radius_column=column,
                compared_count=len(selected),
                mean_delta_bohr=sum(deltas) / len(deltas),
                mean_abs_delta_bohr=sum(abs_deltas) / len(abs_deltas),
                max_abs_delta_bohr=max_abs_delta,
                max_abs_delta_state_id=str(max_abs_delta_row["state_id"]),
                max_abs_rel_delta=max_abs_rel_delta,
                max_abs_rel_delta_state_id=max_abs_rel_delta_state_id,
            )
        )
    return tuple(summaries)


def compare_release_datasets(
    archive_paths: tuple[Path, ...],
    *,
    dataset_ids: tuple[str, ...] = (),
    pairs: tuple[tuple[str, str], ...] = (),
    radius_columns: tuple[str, ...] = DEFAULT_RADIUS_COLUMNS,
) -> ReleaseComparisonResult:
    """Compare matching-state radii across release-candidate datasets."""

    errors: list[str] = []
    warnings: list[str] = []
    try:
        tables = load_release_dataset_tables(archive_paths, dataset_ids=dataset_ids)
    except ValueError as exc:
        return ReleaseComparisonResult(
            archives=archive_paths,
            dataset_ids=(),
            comparisons=(),
            errors=(str(exc),),
            warnings=(),
        )
    tables_by_id = {table.dataset_id: table for table in tables}
    if pairs:
        pair_values = pairs
    else:
        pair_values = tuple(
            (left.dataset_id, right.dataset_id)
            for left, right in combinations(tables, 2)
            if left.state_ids & right.state_ids
        )
    comparisons_out: list[ReleaseDatasetComparison] = []
    for left_id, right_id in pair_values:
        left = tables_by_id.get(left_id)
        right = tables_by_id.get(right_id)
        if left is None or right is None:
            errors.append(f"unknown comparison pair {left_id}:{right_id}")
            continue
        comparison = compare_dataset_tables(left, right, radius_columns=radius_columns)
        if comparison.common_count == 0:
            warnings.append(f"{left_id} vs {right_id}: no common state_id values")
        comparisons_out.append(comparison)
    return ReleaseComparisonResult(
        archives=archive_paths,
        dataset_ids=tuple(table.dataset_id for table in tables),
        comparisons=tuple(comparisons_out),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def format_release_comparison(result: ReleaseComparisonResult, *, summary: bool = True) -> str:
    """Format release comparison output as deterministic text."""

    status = "OK" if result.ok else "FAILED"
    lines = [
        f"Status: {status}",
        "Archives: " + ", ".join(str(path) for path in result.archives),
        "Datasets: " + (", ".join(result.dataset_ids) if result.dataset_ids else "<none>"),
        f"Comparisons: {len(result.comparisons)}",
    ]
    if summary:
        for comparison in result.comparisons:
            lines.append(
                f"{comparison.left_dataset_id} -> {comparison.right_dataset_id}: "
                f"common={comparison.common_count}, "
                f"left_only={len(comparison.left_only_state_ids)}, "
                f"right_only={len(comparison.right_only_state_ids)}"
            )
            for item in comparison.summaries:
                lines.append(
                    "  "
                    f"{item.radius_column}: n={item.compared_count}, "
                    f"mean_delta={_format_float(item.mean_delta_bohr)}, "
                    f"mean_abs_delta={_format_float(item.mean_abs_delta_bohr)}, "
                    f"max_abs_delta={_format_float(item.max_abs_delta_bohr)}"
                    f"@{item.max_abs_delta_state_id or '<none>'}, "
                    f"max_abs_rel={_format_float(item.max_abs_rel_delta)}"
                    f"@{item.max_abs_rel_delta_state_id or '<none>'}"
                )
    if result.errors:
        lines.append("Errors:")
        lines.extend(f"  - {error}" for error in result.errors)
    if result.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in result.warnings)
    return "\n".join(lines)


def _format_float(value: float | None) -> str:
    return "<none>" if value is None else f"{value:.6g}"


def write_comparison_csv(comparisons: tuple[ReleaseDatasetComparison, ...], path: Path) -> int:
    """Write long-form comparison rows to CSV and return row count."""

    fieldnames = [
        "left_dataset_id",
        "right_dataset_id",
        "state_id",
        "symbol",
        "charge",
        "state_category",
        "left_basis_id",
        "right_basis_id",
        "radius_column",
        "left_radius_bohr",
        "right_radius_bohr",
        "delta_right_minus_left_bohr",
        "abs_delta_bohr",
        "rel_delta_right_minus_left",
        "abs_rel_delta",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for comparison in comparisons:
            for row in comparison.rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})
                row_count += 1
    return row_count
