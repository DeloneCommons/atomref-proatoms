"""Diffuse-basis profile-sensitivity QA for generated profile datasets."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..dataio.datasets import (
    ANION_DYALL_AV4Z,
    ANION_X2C_QZVPALL_S,
    PRIMARY_DYALL_V4Z,
    PRIMARY_X2C_QZVPALL,
    ProfileDatasetConfig,
    load_profile_dataset_config,
)
from ..dataio.paths import PROFILE_DATASETS_FILE, PROFILES_ROOT, QA_ROOT, repo_relative_path
from .artifacts import BOHR_TO_ANGSTROM, profile_density_column, write_json
from .radial import radius_at_density

BASIS_SENSITIVITY_SCHEMA_VERSION = "atomref.proatoms.basis_sensitivity_qa.v1"
BASIS_SENSITIVITY_DIRNAME = "basis_sensitivity"
BASIS_SENSITIVITY_FILES = {
    "basis_sensitivity.csv",
    "basis_sensitivity_summary.csv",
    "basis_sensitivity_outliers.csv",
    "metadata.json",
}

DEFAULT_COMPARISON_PAIRS: tuple[tuple[str, str], ...] = (
    (PRIMARY_X2C_QZVPALL, ANION_X2C_QZVPALL_S),
    (PRIMARY_DYALL_V4Z, ANION_DYALL_AV4Z),
)
DEFAULT_QUANTILES = (0.50, 0.90, 0.95, 0.99, 0.999)
DEFAULT_TAIL_RADII_BOHR = (5.0, 10.0, 15.0, 20.0)
DEFAULT_WARN_RELATIVE_L1 = 2.0e-2
DEFAULT_WARN_DELTA_RADIUS_ANGSTROM = 1.5e-1
DENSITY_INTEGRAL_FLOOR = 1.0e-14


@dataclass(frozen=True)
class ProfileDataset:
    """In-memory representation of one generated wide profile dataset."""

    dataset_id: str
    basis_id: str
    metadata: Mapping[str, Any]
    r_bohr: NDArray[np.float64]
    densities_by_state_id: Mapping[str, NDArray[np.float64]]
    state_metadata: Mapping[str, Mapping[str, Any]]

    @property
    def state_ids(self) -> tuple[str, ...]:
        return tuple(self.densities_by_state_id)


@dataclass(frozen=True)
class BasisSensitivityResult:
    """Paths and summary for written basis-sensitivity QA artifacts."""

    output_dir: Path
    rows_csv: Path
    summary_csv: Path
    outliers_csv: Path
    metadata_json: Path
    row_count: int
    summary_count: int
    outlier_count: int
    skipped_pairs: tuple[dict[str, Any], ...]


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{repo_relative_path(path)}: JSON root must be an object")
    return data


def read_profile_dataset(profiles_root: Path, dataset_id: str) -> ProfileDataset:
    """Read one generated wide profile dataset from ``profiles_root``."""

    dataset_dir = profiles_root / dataset_id
    metadata_path = dataset_dir / "metadata.json"
    profiles_path = dataset_dir / "profiles.csv"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"missing profile metadata: {metadata_path}")
    if not profiles_path.is_file():
        raise FileNotFoundError(f"missing profiles CSV: {profiles_path}")

    metadata = _read_json(metadata_path)
    metadata_dataset_id = metadata.get("dataset_id")
    if metadata_dataset_id != dataset_id:
        raise ValueError(
            f"{repo_relative_path(metadata_path)}: dataset_id must be {dataset_id!r}, "
            f"got {metadata_dataset_id!r}"
        )
    basis_id = str(metadata.get("basis_id", ""))
    if not basis_id:
        raise ValueError(f"{repo_relative_path(metadata_path)}: basis_id is required")

    columns = metadata.get("columns", {})
    if not isinstance(columns, Mapping):
        raise ValueError(f"{repo_relative_path(metadata_path)}: columns must be an object")
    column_to_state: dict[str, str] = {}
    for column, column_meta in columns.items():
        if not isinstance(column_meta, Mapping):
            continue
        state_id = str(column_meta.get("state_id", ""))
        if state_id:
            column_to_state[str(column)] = state_id
    if not column_to_state:
        raise ValueError(f"{repo_relative_path(metadata_path)}: no profile state columns found")

    state_metadata_raw = metadata.get("states", {})
    if not isinstance(state_metadata_raw, Mapping):
        raise ValueError(f"{repo_relative_path(metadata_path)}: states must be an object")
    state_metadata: dict[str, Mapping[str, Any]] = {
        str(state_id): dict(state_meta) if isinstance(state_meta, Mapping) else {}
        for state_id, state_meta in state_metadata_raw.items()
    }

    r_values: list[float] = []
    density_values: dict[str, list[float]] = {state_id: [] for state_id in column_to_state.values()}
    with profiles_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "r_bohr" not in reader.fieldnames:
            raise ValueError(
            f"{repo_relative_path(profiles_path)}: first/header column r_bohr missing"
        )
        missing_columns = sorted(set(column_to_state) - set(reader.fieldnames))
        if missing_columns:
            raise ValueError(
                f"{repo_relative_path(profiles_path)}: missing profile columns {missing_columns}"
            )
        for row in reader:
            r_values.append(float(row["r_bohr"]))
            for column, state_id in column_to_state.items():
                density_values[state_id].append(float(row[column]))

    r_bohr = np.asarray(r_values, dtype=float)
    if r_bohr.ndim != 1 or len(r_bohr) < 2:
        raise ValueError(f"{repo_relative_path(profiles_path)}: expected at least two radial rows")
    if not np.all(np.isfinite(r_bohr)) or np.any(np.diff(r_bohr) <= 0.0):
        raise ValueError(f"{repo_relative_path(profiles_path)}: r_bohr must be finite/increasing")

    densities_by_state_id = {
        state_id: np.asarray(values, dtype=float) for state_id, values in density_values.items()
    }
    for state_id, rho in densities_by_state_id.items():
        if rho.shape != r_bohr.shape:
            raise ValueError(f"{dataset_id}/{state_id}: density length does not match r_bohr")
        if not np.all(np.isfinite(rho)):
            raise ValueError(f"{dataset_id}/{state_id}: density contains non-finite values")

    return ProfileDataset(
        dataset_id=dataset_id,
        basis_id=basis_id,
        metadata=metadata,
        r_bohr=r_bohr,
        densities_by_state_id=densities_by_state_id,
        state_metadata=state_metadata,
    )


def _radial_integral(r_bohr: NDArray[np.float64], values: NDArray[np.float64]) -> float:
    integrand = 4.0 * math.pi * r_bohr**2 * values
    return float(np.trapezoid(integrand, r_bohr))


def _tail_integral(
    r_bohr: NDArray[np.float64], rho: NDArray[np.float64], *, tail_start_bohr: float
) -> float:
    if tail_start_bohr <= float(r_bohr[0]):
        return _radial_integral(r_bohr, rho)
    if tail_start_bohr >= float(r_bohr[-1]):
        return 0.0
    start = float(tail_start_bohr)
    start_density = float(np.interp(start, r_bohr, rho))
    mask = r_bohr > start
    tail_r = np.concatenate(([start], r_bohr[mask]))
    tail_rho = np.concatenate(([start_density], rho[mask]))
    return _radial_integral(tail_r, tail_rho)


def _cumulative_electrons(
    r_bohr: NDArray[np.float64], rho: NDArray[np.float64]
) -> NDArray[np.float64]:
    integrand = 4.0 * math.pi * r_bohr**2 * rho
    cumulative = np.zeros_like(r_bohr, dtype=float)
    cumulative[1:] = np.cumsum(0.5 * (integrand[:-1] + integrand[1:]) * np.diff(r_bohr))
    return cumulative


def _quantile_radius(
    r_bohr: NDArray[np.float64], rho: NDArray[np.float64], fraction: float
) -> float | None:
    if not 0.0 < fraction < 1.0:
        raise ValueError("electron-count fraction must be between 0 and 1")
    cumulative = _cumulative_electrons(r_bohr, rho)
    total = float(cumulative[-1])
    if total <= DENSITY_INTEGRAL_FLOOR:
        return None
    target = total * fraction
    index = int(np.searchsorted(cumulative, target, side="left"))
    if index <= 0:
        return float(r_bohr[0])
    if index >= len(r_bohr):
        return float(r_bohr[-1])
    left_e = float(cumulative[index - 1])
    right_e = float(cumulative[index])
    if right_e == left_e:
        return float(r_bohr[index])
    weight = (target - left_e) / (right_e - left_e)
    return float(r_bohr[index - 1] + weight * (r_bohr[index] - r_bohr[index - 1]))


def _safe_radius_at_density(
    r_bohr: NDArray[np.float64], rho: NDArray[np.float64], cutoff: float
) -> float | None:
    try:
        return float(radius_at_density(r_bohr, rho, cutoff))
    except ValueError:
        return None


def _delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return right - left


def _abs_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return abs(value)


def _maybe_float(value: Any) -> float | None:
    if isinstance(value, int | float):
        result = float(value)
        return result if math.isfinite(result) else None
    return None


def _state_prefix(state_id: str, state_meta: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "state_id": state_id,
        "symbol": state_meta.get("symbol"),
        "z": state_meta.get("z"),
        "charge": state_meta.get("charge"),
        "electron_count": state_meta.get("electron_count"),
        "multiplicity": state_meta.get("multiplicity"),
        "state_category": state_meta.get("state_category"),
        "state_role": state_meta.get("state_role"),
    }


def compare_profile_pair(
    base: ProfileDataset,
    diffuse: ProfileDataset,
    *,
    cutoffs_e_bohr3: Sequence[float],
    quantiles: Sequence[float] = DEFAULT_QUANTILES,
    tail_radii_bohr: Sequence[float] = DEFAULT_TAIL_RADII_BOHR,
    warn_relative_l1: float = DEFAULT_WARN_RELATIVE_L1,
    warn_delta_radius_angstrom: float = DEFAULT_WARN_DELTA_RADIUS_ANGSTROM,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compare one primary/diffuse profile pair and return detailed rows and summary."""

    if base.r_bohr.shape != diffuse.r_bohr.shape or not np.allclose(
        base.r_bohr, diffuse.r_bohr, rtol=0.0, atol=0.0
    ):
        raise ValueError(
            f"{base.dataset_id} and {diffuse.dataset_id}: radial grids do not match exactly"
        )
    common_state_ids = tuple(
        state_id for state_id in base.state_ids if state_id in diffuse.densities_by_state_id
    )
    missing_base = tuple(
        state_id for state_id in diffuse.state_ids if state_id not in base.densities_by_state_id
    )
    missing_diffuse = tuple(
        state_id for state_id in base.state_ids if state_id not in diffuse.densities_by_state_id
    )

    comparison_id = f"{base.dataset_id}__vs__{diffuse.dataset_id}"
    rows: list[dict[str, Any]] = []
    for state_id in common_state_ids:
        base_rho = base.densities_by_state_id[state_id]
        diffuse_rho = diffuse.densities_by_state_id[state_id]
        delta_rho = diffuse_rho - base_rho
        state_meta = base.state_metadata.get(state_id, {})
        row: dict[str, Any] = {
            "comparison_id": comparison_id,
            "base_dataset_id": base.dataset_id,
            "diffuse_dataset_id": diffuse.dataset_id,
            "base_basis_id": base.basis_id,
            "diffuse_basis_id": diffuse.basis_id,
            **_state_prefix(state_id, state_meta),
        }
        base_e = _radial_integral(base.r_bohr, base_rho)
        diffuse_e = _radial_integral(base.r_bohr, diffuse_rho)
        signed_delta_e = _radial_integral(base.r_bohr, delta_rho)
        l1_delta_e = _radial_integral(base.r_bohr, np.abs(delta_rho))
        denom = max(0.5 * (abs(base_e) + abs(diffuse_e)), DENSITY_INTEGRAL_FLOOR)
        row.update(
            {
                "base_electron_count_trapz": base_e,
                "diffuse_electron_count_trapz": diffuse_e,
                "signed_delta_electrons_trapz": signed_delta_e,
                "l1_delta_electrons_trapz": l1_delta_e,
                "relative_l1_delta": l1_delta_e / denom,
                "max_abs_density_delta_e_bohr3": float(np.max(np.abs(delta_rho))),
                "r_at_max_abs_density_delta_bohr": float(
                    base.r_bohr[int(np.argmax(np.abs(delta_rho)))]
                ),
            }
        )

        max_abs_quantile_delta_angstrom: float | None = None
        for quantile in quantiles:
            label = f"r{quantile * 100:g}".replace(".", "p")
            base_radius = _quantile_radius(base.r_bohr, base_rho, float(quantile))
            diffuse_radius = _quantile_radius(base.r_bohr, diffuse_rho, float(quantile))
            delta_bohr = _delta(base_radius, diffuse_radius)
            delta_angstrom = None if delta_bohr is None else delta_bohr * BOHR_TO_ANGSTROM
            row[f"base_{label}_bohr"] = base_radius
            row[f"diffuse_{label}_bohr"] = diffuse_radius
            row[f"delta_{label}_bohr"] = delta_bohr
            row[f"delta_{label}_angstrom"] = delta_angstrom
            abs_delta_angstrom = _abs_or_none(delta_angstrom)
            if abs_delta_angstrom is not None:
                max_abs_quantile_delta_angstrom = max(
                    max_abs_quantile_delta_angstrom or 0.0, abs_delta_angstrom
                )

        max_abs_cutoff_delta_angstrom: float | None = None
        for cutoff in cutoffs_e_bohr3:
            label = f"r_iso_{float(cutoff):g}_e_bohr3".replace(".", "p")
            base_radius = _safe_radius_at_density(base.r_bohr, base_rho, float(cutoff))
            diffuse_radius = _safe_radius_at_density(base.r_bohr, diffuse_rho, float(cutoff))
            delta_bohr = _delta(base_radius, diffuse_radius)
            delta_angstrom = None if delta_bohr is None else delta_bohr * BOHR_TO_ANGSTROM
            row[f"base_{label}_bohr"] = base_radius
            row[f"diffuse_{label}_bohr"] = diffuse_radius
            row[f"delta_{label}_bohr"] = delta_bohr
            row[f"delta_{label}_angstrom"] = delta_angstrom
            abs_delta_angstrom = _abs_or_none(delta_angstrom)
            if abs_delta_angstrom is not None:
                max_abs_cutoff_delta_angstrom = max(
                    max_abs_cutoff_delta_angstrom or 0.0, abs_delta_angstrom
                )

        for tail_radius in tail_radii_bohr:
            label = f"tail_electrons_gt_{tail_radius:g}_bohr".replace(".", "p")
            base_tail = _tail_integral(base.r_bohr, base_rho, tail_start_bohr=float(tail_radius))
            diffuse_tail = _tail_integral(
                base.r_bohr, diffuse_rho, tail_start_bohr=float(tail_radius)
            )
            row[f"base_{label}"] = base_tail
            row[f"diffuse_{label}"] = diffuse_tail
            row[f"delta_{label}"] = diffuse_tail - base_tail

        row["max_abs_quantile_radius_delta_angstrom"] = max_abs_quantile_delta_angstrom
        row["max_abs_cutoff_radius_delta_angstrom"] = max_abs_cutoff_delta_angstrom
        warnings: list[str] = []
        if float(row["relative_l1_delta"]) > warn_relative_l1:
            warnings.append("relative_l1_delta")
        radius_deltas = [
            value
            for value in (
                max_abs_quantile_delta_angstrom,
                max_abs_cutoff_delta_angstrom,
            )
            if value is not None
        ]
        if radius_deltas and max(radius_deltas) > warn_delta_radius_angstrom:
            warnings.append("radius_delta")
        row["status"] = "WARN" if warnings else "OK"
        row["warning_flags"] = ";".join(warnings)
        rows.append(row)

    summary = _summarize_pair(
        comparison_id=comparison_id,
        base=base,
        diffuse=diffuse,
        rows=rows,
        missing_base=missing_base,
        missing_diffuse=missing_diffuse,
    )
    return rows, summary


def _max_float(
    rows: Sequence[Mapping[str, Any]], key: str, *, absolute: bool = False
) -> float | None:
    values: list[float] = []
    for row in rows:
        value = _maybe_float(row.get(key))
        if value is None:
            continue
        values.append(abs(value) if absolute else value)
    return max(values) if values else None


def _summarize_pair(
    *,
    comparison_id: str,
    base: ProfileDataset,
    diffuse: ProfileDataset,
    rows: Sequence[Mapping[str, Any]],
    missing_base: Sequence[str],
    missing_diffuse: Sequence[str],
) -> dict[str, Any]:
    return {
        "comparison_id": comparison_id,
        "base_dataset_id": base.dataset_id,
        "diffuse_dataset_id": diffuse.dataset_id,
        "base_basis_id": base.basis_id,
        "diffuse_basis_id": diffuse.basis_id,
        "base_state_count": len(base.state_ids),
        "diffuse_state_count": len(diffuse.state_ids),
        "common_state_count": len(rows),
        "missing_base_state_count": len(missing_base),
        "missing_diffuse_state_count": len(missing_diffuse),
        "missing_base_state_ids": ";".join(missing_base),
        "missing_diffuse_state_ids": ";".join(missing_diffuse),
        "outlier_count": sum(1 for row in rows if row.get("status") == "WARN"),
        "max_relative_l1_delta": _max_float(rows, "relative_l1_delta"),
        "max_abs_signed_delta_electrons_trapz": _max_float(
            rows, "signed_delta_electrons_trapz", absolute=True
        ),
        "max_l1_delta_electrons_trapz": _max_float(rows, "l1_delta_electrons_trapz"),
        "max_abs_quantile_radius_delta_angstrom": _max_float(
            rows, "max_abs_quantile_radius_delta_angstrom"
        ),
        "max_abs_cutoff_radius_delta_angstrom": _max_float(
            rows, "max_abs_cutoff_radius_delta_angstrom"
        ),
    }


def _write_dict_rows_csv(
    path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in fieldnames})


def _ordered_fieldnames(rows: Sequence[Mapping[str, Any]], prefix: Sequence[str]) -> list[str]:
    fields = list(prefix)
    seen = set(fields)
    for row in rows:
        for key in row:
            if key in seen:
                continue
            seen.add(key)
            fields.append(str(key))
    return fields


def configured_basis_sensitivity_pairs(
    config: ProfileDatasetConfig,
) -> tuple[tuple[str, str], ...]:
    """Return default basis-sensitivity pairs present in a dataset config."""

    configured = set(config.dataset_ids)
    return tuple(
        pair for pair in DEFAULT_COMPARISON_PAIRS if pair[0] in configured and pair[1] in configured
    )


def build_basis_sensitivity_qa(
    *,
    config_path: Path = PROFILE_DATASETS_FILE,
    profiles_root: Path = PROFILES_ROOT,
    qa_root: Path = QA_ROOT,
    pairs: Sequence[tuple[str, str]] | None = None,
    force: bool = False,
    warn_relative_l1: float = DEFAULT_WARN_RELATIVE_L1,
    warn_delta_radius_angstrom: float = DEFAULT_WARN_DELTA_RADIUS_ANGSTROM,
) -> BasisSensitivityResult:
    """Build optional diffuse-basis profile-comparison QA artifacts."""

    config = load_profile_dataset_config(config_path)
    selected_pairs = tuple(pairs or configured_basis_sensitivity_pairs(config))
    if not selected_pairs:
        raise ValueError("no configured basis-sensitivity comparison pairs found")

    output_dir = qa_root / BASIS_SENSITIVITY_DIRNAME
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(f"{repo_relative_path(output_dir)} exists; use --force to overwrite")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    skipped_pairs: list[dict[str, Any]] = []
    for base_dataset_id, diffuse_dataset_id in selected_pairs:
        base_dir = profiles_root / base_dataset_id
        diffuse_dir = profiles_root / diffuse_dataset_id
        if not base_dir.is_dir() or not diffuse_dir.is_dir():
            skipped_pairs.append(
                {
                    "base_dataset_id": base_dataset_id,
                    "diffuse_dataset_id": diffuse_dataset_id,
                    "reason": "missing_profile_dataset_dir",
                    "base_present": base_dir.is_dir(),
                    "diffuse_present": diffuse_dir.is_dir(),
                }
            )
            continue
        base = read_profile_dataset(profiles_root, base_dataset_id)
        diffuse = read_profile_dataset(profiles_root, diffuse_dataset_id)
        rows, summary = compare_profile_pair(
            base,
            diffuse,
            cutoffs_e_bohr3=config.cutoffs_e_bohr3,
            warn_relative_l1=warn_relative_l1,
            warn_delta_radius_angstrom=warn_delta_radius_angstrom,
        )
        all_rows.extend(rows)
        summaries.append(summary)

    if not all_rows:
        raise ValueError(
            "no basis-sensitivity profile rows were generated; "
            f"skipped_pairs={skipped_pairs!r}"
        )

    outliers = [row for row in all_rows if row.get("status") == "WARN"]
    rows_csv = output_dir / "basis_sensitivity.csv"
    summary_csv = output_dir / "basis_sensitivity_summary.csv"
    outliers_csv = output_dir / "basis_sensitivity_outliers.csv"
    metadata_json = output_dir / "metadata.json"

    row_prefix = [
        "comparison_id",
        "base_dataset_id",
        "diffuse_dataset_id",
        "base_basis_id",
        "diffuse_basis_id",
        "state_id",
        "symbol",
        "z",
        "charge",
        "electron_count",
        "state_category",
        "state_role",
        "status",
        "warning_flags",
    ]
    summary_prefix = [
        "comparison_id",
        "base_dataset_id",
        "diffuse_dataset_id",
        "base_basis_id",
        "diffuse_basis_id",
        "common_state_count",
        "outlier_count",
    ]
    _write_dict_rows_csv(rows_csv, _ordered_fieldnames(all_rows, row_prefix), all_rows)
    _write_dict_rows_csv(summary_csv, _ordered_fieldnames(summaries, summary_prefix), summaries)
    _write_dict_rows_csv(outliers_csv, _ordered_fieldnames(outliers, row_prefix), outliers)
    write_json(
        metadata_json,
        {
            "schema_version": BASIS_SENSITIVITY_SCHEMA_VERSION,
            "profile_data_version": config.profile_data_version,
            "config": repo_relative_path(config_path),
            "profiles_root": repo_relative_path(profiles_root),
            "qa_root": repo_relative_path(qa_root),
            "files": {
                "basis_sensitivity_csv": repo_relative_path(rows_csv),
                "basis_sensitivity_summary_csv": repo_relative_path(summary_csv),
                "basis_sensitivity_outliers_csv": repo_relative_path(outliers_csv),
                "metadata_json": repo_relative_path(metadata_json),
            },
            "comparison_pairs": [
                {"base_dataset_id": base, "diffuse_dataset_id": diffuse}
                for base, diffuse in selected_pairs
            ],
            "skipped_pairs": skipped_pairs,
            "row_count": len(all_rows),
            "summary_count": len(summaries),
            "outlier_count": len(outliers),
            "thresholds": {
                "warn_relative_l1": warn_relative_l1,
                "warn_delta_radius_angstrom": warn_delta_radius_angstrom,
            },
            "notes": [
                "Basis-sensitivity rows are diagnostic warnings, not automatic release failures.",
                "The compared densities are radial spherical profiles; L1 deltas are "
                "integrated with 4*pi*r^2 dr.",
            ],
        },
    )
    return BasisSensitivityResult(
        output_dir=output_dir,
        rows_csv=rows_csv,
        summary_csv=summary_csv,
        outliers_csv=outliers_csv,
        metadata_json=metadata_json,
        row_count=len(all_rows),
        summary_count=len(summaries),
        outlier_count=len(outliers),
        skipped_pairs=tuple(skipped_pairs),
    )
