"""Report builders for the active atomref-proatoms profile release."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .artifacts import profile_density_column, write_json

REPORT_SCHEMA_VERSION = "atomref.proatoms.report.v1"
PROFILE_DATASET_SCHEMA_VERSION = "atomref.proatoms.profile_dataset.v1"


@dataclass(frozen=True)
class LoadedProfileDataset:
    """Profile dataset artifacts loaded from ``data/profiles/<dataset_id>``."""

    dataset_dir: Path
    metadata: dict[str, Any]
    csv_header: list[str]
    row_count: int

    @property
    def dataset_id(self) -> str:
        return str(self.metadata["dataset_id"])

    @property
    def state_ids(self) -> list[str]:
        return list(self.metadata.get("states", {}))


def _read_profile_csv_header_and_count(path: Path) -> tuple[list[str], int]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"empty profile CSV: {path}") from exc
        row_count = sum(1 for _row in reader)
    if not header or header[0] != "r_bohr":
        raise ValueError(f"profile CSV first column must be r_bohr: {path}")
    if row_count < 2:
        raise ValueError(f"profile CSV must contain at least two grid rows: {path}")
    return header, row_count


def load_profile_dataset(dataset_dir: Path) -> LoadedProfileDataset:
    """Load and lightly validate one generated profile dataset directory."""

    metadata_path = dataset_dir / "metadata.json"
    profiles_path = dataset_dir / "profiles.csv"
    if not metadata_path.exists():
        raise FileNotFoundError(f"missing profile metadata: {metadata_path}")
    if not profiles_path.exists():
        raise FileNotFoundError(f"missing profile CSV: {profiles_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("schema_version") != PROFILE_DATASET_SCHEMA_VERSION:
        raise ValueError(f"unexpected profile dataset schema_version in {metadata_path}")
    dataset_id = metadata.get("dataset_id")
    if not dataset_id or dataset_id != dataset_dir.name:
        raise ValueError(f"metadata dataset_id does not match directory name: {dataset_dir}")
    header, row_count = _read_profile_csv_header_and_count(profiles_path)
    expected_columns = {profile_density_column(state_id) for state_id in metadata.get("states", {})}
    missing = sorted(expected_columns - set(header))
    if missing:
        raise ValueError(f"profile CSV {profiles_path} is missing density columns {missing}")
    return LoadedProfileDataset(dataset_dir=dataset_dir, metadata=metadata, csv_header=header, row_count=row_count)


def discover_profile_datasets(
    profiles_root: Path, *, dataset_ids: tuple[str, ...] | None = None
) -> list[LoadedProfileDataset]:
    """Discover generated profile datasets under ``profiles_root``."""

    profiles_root = Path(profiles_root)
    if dataset_ids:
        dirs = [profiles_root / dataset_id for dataset_id in dataset_ids]
    elif profiles_root.exists():
        dirs = sorted(path for path in profiles_root.iterdir() if path.is_dir())
    else:
        dirs = []
    return [load_profile_dataset(path) for path in dirs]


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _max_abs(values: list[float | None]) -> float | None:
    present = [abs(value) for value in values if value is not None]
    return max(present) if present else None


def dataset_summary_rows(datasets: list[LoadedProfileDataset]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in datasets:
        metadata = dataset.metadata
        qa = metadata.get("qa", {})
        qa_values = list(qa.values()) if isinstance(qa, dict) else []
        electron_errors = [_float_or_none(row.get("electron_count_error_qa")) for row in qa_values]
        converged_count = sum(1 for row in qa_values if row.get("scf_converged") is True)
        pass_count = sum(1 for row in qa_values if row.get("electron_count_pass") is True)
        method = metadata.get("method", {})
        rows.append(
            {
                "dataset_id": metadata.get("dataset_id"),
                "profile_data_version": metadata.get("profile_data_version"),
                "basis_id": metadata.get("basis_id"),
                "n_states": len(metadata.get("states", {})),
                "n_grid_points": dataset.row_count,
                "density_model": metadata.get("density_model"),
                "engine_version": method.get("engine_version"),
                "xc": method.get("xc"),
                "relativity": method.get("relativity"),
                "scf_converged_count": converged_count,
                "electron_count_pass_count": pass_count,
                "max_abs_electron_count_error_qa": _max_abs(electron_errors),
            }
        )
    return rows


def state_summary_rows(datasets: list[LoadedProfileDataset]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in datasets:
        metadata = dataset.metadata
        derived = metadata.get("derived_radii", {})
        for state_id, state in metadata.get("states", {}).items():
            row = {
                "dataset_id": dataset.dataset_id,
                "state_id": state_id,
                "symbol": state.get("symbol"),
                "z": state.get("z"),
                "charge": state.get("charge"),
                "electron_count": state.get("electron_count"),
                "multiplicity": state.get("multiplicity"),
                "state_category": state.get("state_category"),
                "state_role": state.get("state_role"),
            }
            row.update(derived.get(state_id, {}))
            rows.append(row)
    return rows


def qa_summary_rows(datasets: list[LoadedProfileDataset]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in datasets:
        for state_id, qa in dataset.metadata.get("qa", {}).items():
            rows.append(
                {
                    "dataset_id": dataset.dataset_id,
                    "state_id": state_id,
                    "scf_converged": qa.get("scf_converged"),
                    "electron_count_error_qa": qa.get("electron_count_error_qa"),
                    "electron_count_tolerance": qa.get("electron_count_tolerance"),
                    "electron_count_pass": qa.get("electron_count_pass"),
                    "max_rel_angular_sigma": qa.get("max_rel_angular_sigma"),
                    "linear_dependency_warning_count": qa.get("linear_dependency_warning_count"),
                    "linear_dependency_vectors_removed": qa.get(
                        "linear_dependency_vectors_removed"
                    ),
                    "tail_reaches_min_cutoff": qa.get("tail_reaches_min_cutoff"),
                    "radii_monotonic": qa.get("radii_monotonic"),
                }
            )
    return rows


def derived_radii_rows(datasets: list[LoadedProfileDataset]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in datasets:
        for state_id, radii in dataset.metadata.get("derived_radii", {}).items():
            row = {"dataset_id": dataset.dataset_id, "state_id": state_id}
            row.update(radii)
            rows.append(row)
    return rows


def _fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                names.append(key)
    return names


def write_csv_table(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write a deterministic CSV table."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = _fieldnames(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _markdown_table(rows: list[dict[str, Any]], columns: list[str], *, limit: int | None = None) -> str:
    selected = rows[:limit] if limit is not None else rows
    if not selected:
        return "No rows."
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in selected:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines)


def write_electron_error_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write a tiny dependency-free SVG bar chart for dataset electron-count QA."""

    values = [
        (str(row["dataset_id"]), _float_or_none(row.get("max_abs_electron_count_error_qa")) or 0.0)
        for row in rows
    ]
    width = 920
    height = 160 + 34 * max(len(values), 1)
    left = 260
    right = 40
    max_value = max((value for _label, value in values), default=0.0) or 1.0
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,sans-serif;font-size:12px}.title{font-size:16px;font-weight:bold}.bar{fill:#777}</style>',
        '<text class="title" x="20" y="28">Max absolute electron-count QA error by dataset</text>',
    ]
    for index, (label, value) in enumerate(values):
        y = 58 + index * 34
        bar_width = 0.0 if max_value == 0 else (width - left - right) * value / max_value
        lines.append(f'<text x="20" y="{y + 14}">{label}</text>')
        lines.append(f'<rect class="bar" x="{left}" y="{y}" width="{bar_width:.3f}" height="18"/>')
        lines.append(f'<text x="{left + bar_width + 8:.3f}" y="{y + 14}">{value:.3e}</text>')
    lines.append("</svg>\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_markdown_report(
    path: Path,
    *,
    profile_data_version: str,
    dataset_rows: list[dict[str, Any]],
    state_rows: list[dict[str, Any]],
    qa_rows: list[dict[str, Any]],
) -> None:
    total_states = sum(int(row.get("n_states") or 0) for row in dataset_rows)
    max_error = _max_abs([_float_or_none(row.get("electron_count_error_qa")) for row in qa_rows])
    lines = [
        f"# atomref-proatoms radial profiles v{profile_data_version}",
        "",
        "This report is generated from the active `data/profiles/` profile datasets.",
        "",
        "## Summary",
        "",
        f"- Datasets: {len(dataset_rows)}",
        f"- State/profile columns: {total_states}",
        f"- Max absolute electron-count QA error: {max_error:.6e}" if max_error is not None else "- Max absolute electron-count QA error: n/a",
        "",
        "## Dataset summary",
        "",
        _markdown_table(
            dataset_rows,
            [
                "dataset_id",
                "basis_id",
                "n_states",
                "n_grid_points",
                "xc",
                "relativity",
                "max_abs_electron_count_error_qa",
            ],
        ),
        "",
        "## QA notes",
        "",
        "Detailed QA values are written to `tables/qa_summary.csv`. Derived cutoff radii are written to `tables/derived_radii.csv`.",
        "",
        "## First state rows",
        "",
        _markdown_table(
            state_rows,
            ["dataset_id", "state_id", "symbol", "charge", "multiplicity", "state_category"],
            limit=25,
        ),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_report(
    *,
    profiles_root: Path,
    report_dir: Path,
    dataset_ids: tuple[str, ...] | None = None,
) -> dict[str, Path]:
    """Build report markdown, tables, and a small SVG figure from generated profiles."""

    datasets = discover_profile_datasets(profiles_root, dataset_ids=dataset_ids)
    if not datasets:
        raise FileNotFoundError(f"No generated profile datasets found under {profiles_root}")

    versions = sorted({str(dataset.metadata.get("profile_data_version")) for dataset in datasets})
    profile_data_version = versions[0] if len(versions) == 1 else ", ".join(versions)
    dataset_rows = dataset_summary_rows(datasets)
    state_rows = state_summary_rows(datasets)
    qa_rows = qa_summary_rows(datasets)
    radii_rows = derived_radii_rows(datasets)

    tables_dir = report_dir / "tables"
    figures_dir = report_dir / "figures"
    outputs = {
        "report": report_dir / "report.md",
        "manifest": report_dir / "report_manifest.json",
        "dataset_summary": tables_dir / "dataset_summary.csv",
        "state_summary": tables_dir / "state_summary.csv",
        "qa_summary": tables_dir / "qa_summary.csv",
        "derived_radii": tables_dir / "derived_radii.csv",
        "electron_error_svg": figures_dir / "electron_count_error.svg",
    }
    write_csv_table(outputs["dataset_summary"], dataset_rows)
    write_csv_table(outputs["state_summary"], state_rows)
    write_csv_table(outputs["qa_summary"], qa_rows)
    write_csv_table(outputs["derived_radii"], radii_rows)
    write_electron_error_svg(outputs["electron_error_svg"], dataset_rows)
    write_markdown_report(
        outputs["report"],
        profile_data_version=profile_data_version,
        dataset_rows=dataset_rows,
        state_rows=state_rows,
        qa_rows=qa_rows,
    )
    write_json(
        outputs["manifest"],
        {
            "schema_version": REPORT_SCHEMA_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "profile_data_version": profile_data_version,
            "profiles_root": str(profiles_root),
            "dataset_ids": [dataset.dataset_id for dataset in datasets],
            "outputs": {name: str(path) for name, path in outputs.items()},
        },
    )
    return outputs
