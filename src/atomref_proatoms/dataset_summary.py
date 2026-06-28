"""Compact summaries for generated profile datasets."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .profile_checks import read_strict_json

RADIUS_COLUMNS = (
    "r_iso_0.003_e_bohr3_bohr",
    "r_iso_0.001_e_bohr3_bohr",
    "r_iso_0.0001_e_bohr3_bohr",
)


@dataclass(frozen=True)
class RadiusRange:
    """Minimum/maximum radius values for one derived-radii column."""

    column: str
    count: int
    minimum: float | None
    maximum: float | None


@dataclass(frozen=True)
class DatasetSummary:
    """Human-oriented summary of one generated dataset directory."""

    dataset_dir: Path
    dataset_id: str
    profile_count: int
    basis_ids: tuple[str, ...]
    symbols: tuple[str, ...]
    state_ids: tuple[str, ...]
    charge_counts: tuple[tuple[str, int], ...]
    state_category_counts: tuple[tuple[str, int], ...]
    spin_model_counts: tuple[tuple[str, int], ...]
    scf_converged_count: int | None
    electron_count_qa_count: int | None
    angular_sigma_qa_count: int | None
    max_abs_electron_count_error_qa: float | None
    max_rel_angular_sigma: float | None
    spin_square_diagnostic_count: int | None
    max_abs_spin_square_deviation: float | None
    linear_dependency_warning_count: int | None
    linear_dependency_profile_count: int | None
    max_linear_dependency_vectors_removed: int | None
    all_tail_reaches_min_cutoff: bool | None
    all_radii_monotonic: bool | None
    radius_ranges: tuple[RadiusRange, ...]


def _read_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return tuple(dict(row) for row in reader)


def _count_values(rows: tuple[dict[str, str], ...], key: str) -> tuple[tuple[str, int], ...]:
    counter = Counter(row.get(key, "") or "<missing>" for row in rows)
    return tuple(sorted(counter.items(), key=lambda item: item[0]))


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
    return None


def _radius_ranges(rows: tuple[dict[str, str], ...]) -> tuple[RadiusRange, ...]:
    ranges: list[RadiusRange] = []
    for column in RADIUS_COLUMNS:
        values = [_float_or_none(row.get(column)) for row in rows]
        finite_values = [value for value in values if value is not None]
        ranges.append(
            RadiusRange(
                column=column,
                count=len(finite_values),
                minimum=min(finite_values) if finite_values else None,
                maximum=max(finite_values) if finite_values else None,
            )
        )
    return tuple(ranges)


def summarize_dataset_indexes(dataset_dir: Path) -> DatasetSummary:
    """Read dataset-level index files and return a compact summary."""

    manifest_path = dataset_dir / "dataset_manifest.json"
    profile_index_path = dataset_dir / "profile_index.csv"
    derived_radii_path = dataset_dir / "derived_radii.csv"
    for path in (manifest_path, profile_index_path, derived_radii_path):
        if not path.exists():
            raise FileNotFoundError(f"missing dataset index file: {path}")

    manifest = read_strict_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path}: manifest root must be an object")
    profile_rows = _read_csv_rows(profile_index_path)
    radii_rows = _read_csv_rows(derived_radii_path)
    qa_summary = manifest.get("qa_summary", {})
    if not isinstance(qa_summary, dict):
        qa_summary = {}

    return DatasetSummary(
        dataset_dir=dataset_dir,
        dataset_id=str(manifest.get("dataset_id", "")),
        profile_count=int(manifest.get("profile_count", len(profile_rows))),
        basis_ids=tuple(str(value) for value in manifest.get("basis_ids", [])),
        symbols=tuple(sorted({row.get("symbol", "") for row in profile_rows if row.get("symbol")})),
        state_ids=tuple(str(value) for value in manifest.get("state_ids", [])),
        charge_counts=_count_values(profile_rows, "charge"),
        state_category_counts=_count_values(profile_rows, "state_category"),
        spin_model_counts=_count_values(profile_rows, "spin_model"),
        scf_converged_count=_int_or_none(qa_summary.get("scf_converged_count")),
        electron_count_qa_count=_int_or_none(qa_summary.get("electron_count_qa_count")),
        angular_sigma_qa_count=_int_or_none(qa_summary.get("angular_sigma_qa_count")),
        max_abs_electron_count_error_qa=_float_or_none(
            qa_summary.get("max_abs_electron_count_error_qa")
        ),
        max_rel_angular_sigma=_float_or_none(qa_summary.get("max_rel_angular_sigma")),
        spin_square_diagnostic_count=_int_or_none(
            qa_summary.get("spin_square_diagnostic_count")
        ),
        max_abs_spin_square_deviation=_float_or_none(
            qa_summary.get("max_abs_spin_square_deviation")
        ),
        linear_dependency_warning_count=_int_or_none(
            qa_summary.get("linear_dependency_warning_count")
        ),
        linear_dependency_profile_count=_int_or_none(
            qa_summary.get("linear_dependency_profile_count")
        ),
        max_linear_dependency_vectors_removed=_int_or_none(
            qa_summary.get("max_linear_dependency_vectors_removed")
        ),
        all_tail_reaches_min_cutoff=_bool_or_none(
            qa_summary.get("all_tail_reaches_min_cutoff")
        ),
        all_radii_monotonic=_bool_or_none(qa_summary.get("all_radii_monotonic")),
        radius_ranges=_radius_ranges(radii_rows),
    )


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _format_counts(counts: tuple[tuple[str, int], ...]) -> str:
    return ", ".join(f"{key}={count}" for key, count in counts) if counts else "<none>"


def _format_optional_float(value: float | None, *, precision: int = 6) -> str:
    if value is None:
        return "null"
    return f"{value:.{precision}g}"


def _format_optional_bool(value: bool | None) -> str:
    if value is None:
        return "null"
    return "true" if value else "false"


def format_dataset_summary(summary: DatasetSummary) -> str:
    """Format a dataset summary as a small deterministic text report."""

    lines = [
        f"Dataset: {summary.dataset_id}",
        f"Directory: {summary.dataset_dir}",
        f"Profiles: {summary.profile_count}",
        f"Basis IDs: {', '.join(summary.basis_ids) if summary.basis_ids else '<none>'}",
        f"Elements: {', '.join(summary.symbols) if summary.symbols else '<none>'}",
        f"Charges: {_format_counts(summary.charge_counts)}",
        f"State categories: {_format_counts(summary.state_category_counts)}",
        f"Spin models: {_format_counts(summary.spin_model_counts)}",
        "QA:",
        f"  SCF converged: {summary.scf_converged_count}/{summary.profile_count}",
        f"  Electron-count QA: {summary.electron_count_qa_count}/{summary.profile_count}",
        f"  Angular-sigma QA: {summary.angular_sigma_qa_count}/{summary.profile_count}",
        "  Max |electron-count error|: "
        f"{_format_optional_float(summary.max_abs_electron_count_error_qa)}",
        f"  Max relative angular sigma: {_format_optional_float(summary.max_rel_angular_sigma)}",
        "Diagnostics:",
        f"  Spin-square diagnostics: {summary.spin_square_diagnostic_count or 0}/{summary.profile_count}",
        "  Max |spin-square diagnostic deviation|: "
        f"{_format_optional_float(summary.max_abs_spin_square_deviation)}",
        "  Linear-dependency warnings: "
        f"{summary.linear_dependency_warning_count or 0} "
        f"across {summary.linear_dependency_profile_count or 0} profile(s)",
        "  Max linear-dependency vectors removed: "
        f"{summary.max_linear_dependency_vectors_removed or 0}",
        "  All tails reach min cutoff: "
        f"{_format_optional_bool(summary.all_tail_reaches_min_cutoff)}",
        f"  All radii monotonic: {_format_optional_bool(summary.all_radii_monotonic)}",
        "Derived-radii ranges:",
    ]
    for item in summary.radius_ranges:
        lines.append(
            f"  {item.column}: "
            f"count={item.count}, "
            f"min={_format_optional_float(item.minimum)}, "
            f"max={_format_optional_float(item.maximum)}"
        )
    return "\n".join(lines)
