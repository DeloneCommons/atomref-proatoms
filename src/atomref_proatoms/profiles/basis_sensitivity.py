"""Diffuse-basis profile-sensitivity QA for generated profile datasets."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
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
from ..dataio.paths import (
    PROFILE_DATASETS_FILE,
    PROFILES_ROOT,
    QA_ROOT,
    STATES_FILE,
    repo_relative_path,
)
from ..states.state_tables import AtomState, load_atom_states
from .artifacts import BOHR_TO_ANGSTROM, write_json
from .build_plan import build_jobs_for_datasets
from .radial import radius_at_density

BASIS_SENSITIVITY_SCHEMA_VERSION = "atomref.proatoms.basis_sensitivity_qa.v2"
LEGACY_BASIS_SENSITIVITY_SCHEMA_VERSION = "atomref.proatoms.basis_sensitivity_qa.v1"
BASIS_SENSITIVITY_DIRNAME = "basis_sensitivity"

# Root aggregate files are retained for maintainer compatibility.  Pair-specific
# files are written under subdirectories named after the base basis set.
BASIS_SENSITIVITY_FILES = {
    "basis_sensitivity.csv",
    "basis_sensitivity_summary.csv",
    "basis_sensitivity_outliers.csv",
    "basis_sensitivity_metric_distributions.csv",
    "metadata.json",
}
LEGACY_BASIS_SENSITIVITY_FILES = {
    "basis_sensitivity.csv",
    "basis_sensitivity_summary.csv",
    "basis_sensitivity_outliers.csv",
    "metadata.json",
}

PRIMARY_COMPARISON_PAIRS: tuple[tuple[str, str], ...] = (
    (PRIMARY_DYALL_V4Z, ANION_DYALL_AV4Z),
)
OPTIONAL_COMPARISON_PAIRS: tuple[tuple[str, str], ...] = (
    (PRIMARY_X2C_QZVPALL, ANION_X2C_QZVPALL_S),
)
DEFAULT_COMPARISON_PAIRS = PRIMARY_COMPARISON_PAIRS

PAIR_OUTPUT_STEMS = {
    (PRIMARY_DYALL_V4Z, ANION_DYALL_AV4Z): "basis_sensitivity_dyall",
    (PRIMARY_X2C_QZVPALL, ANION_X2C_QZVPALL_S): "basis_sensitivity_x2c_optional",
}
PAIR_KINDS = {
    (PRIMARY_DYALL_V4Z, ANION_DYALL_AV4Z): "primary_dyall_diffuse_augmentation",
    (PRIMARY_X2C_QZVPALL, ANION_X2C_QZVPALL_S): "optional_x2c_qzvpall_s_diagnostic",
}

DEFAULT_QUANTILES = (0.50, 0.90, 0.95, 0.99, 0.995, 0.999, 0.9999)
DEFAULT_TAIL_RADII_BOHR = (5.0, 10.0, 15.0, 20.0)
DEFAULT_RELATIVE_L1_WATCH = 5.0e-2
DEFAULT_RELATIVE_L1_OUTLIER = 1.5e-1
DEFAULT_MAX_CUMULATIVE_DELTA_WATCH_ELECTRONS = 5.0e-1
DEFAULT_MAX_CUMULATIVE_DELTA_OUTLIER_ELECTRONS = 1.0
DEFAULT_MEAN_RADIAL_SHIFT_WATCH_ANGSTROM = 1.0e-1
DEFAULT_MEAN_RADIAL_SHIFT_OUTLIER_ANGSTROM = 3.0e-1
DEFAULT_MAX_ELECTRON_COUNT_ERROR = 5.0e-3

# Backward-compatible names used by the previous CLI.  They now control scientific
# watch thresholds rather than release-failure cutoffs.
DEFAULT_WARN_RELATIVE_L1 = DEFAULT_RELATIVE_L1_WATCH
DEFAULT_WARN_DELTA_RADIUS_ANGSTROM = DEFAULT_MEAN_RADIAL_SHIFT_WATCH_ANGSTROM

DENSITY_INTEGRAL_FLOOR = 1.0e-14
DENSITY_NEGATIVE_TOLERANCE = -1.0e-12
METRIC_DISTRIBUTION_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("all", ()),
    ("charge", ("charge",)),
    ("state_role", ("state_role",)),
    ("charge_state_role", ("charge", "state_role")),
)
METRIC_DISTRIBUTION_METRICS = (
    "relative_l1_delta",
    "l1_delta_electrons_trapz",
    "max_abs_cumulative_delta_electrons",
    "mean_abs_radial_shift_angstrom",
    "delta_mean_r_angstrom",
    "delta_rms_r_angstrom",
    "max_abs_quantile_radius_delta_angstrom",
    "max_abs_cutoff_radius_delta_angstrom",
    "delta_tail_electrons_gt_10_bohr",
    "delta_tail_electrons_gt_15_bohr",
    "delta_tail_electrons_gt_20_bohr",
)


@dataclass(frozen=True)
class ProfileDataset:
    """In-memory representation of one generated wide profile dataset."""

    dataset_id: str
    basis_id: str
    metadata: Mapping[str, Any]
    r_bohr: NDArray[np.float64]
    densities_by_state_id: Mapping[str, NDArray[np.float64]]
    state_metadata: Mapping[str, Mapping[str, Any]]
    state_record_sha256_by_state_id: Mapping[str, str]

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
    metric_distribution_count: int
    skipped_pairs: tuple[dict[str, Any], ...]
    pair_outputs: Mapping[str, Mapping[str, str]]


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


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

    state_record_sha256_by_state_id: dict[str, str] = {}
    scf_artifacts = metadata.get("scf_artifacts", {})
    if isinstance(scf_artifacts, Mapping):
        for state_id, artifact in scf_artifacts.items():
            if not isinstance(artifact, Mapping):
                continue
            fingerprints = artifact.get("fingerprints", {})
            if not isinstance(fingerprints, Mapping):
                continue
            digest = fingerprints.get("state_record_sha256")
            if digest:
                state_record_sha256_by_state_id[str(state_id)] = str(digest)

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
        if np.min(rho) < DENSITY_NEGATIVE_TOLERANCE:
            raise ValueError(f"{dataset_id}/{state_id}: density contains negative values")

    return ProfileDataset(
        dataset_id=dataset_id,
        basis_id=basis_id,
        metadata=metadata,
        r_bohr=r_bohr,
        densities_by_state_id=densities_by_state_id,
        state_metadata=state_metadata,
        state_record_sha256_by_state_id=state_record_sha256_by_state_id,
    )


def _radial_distribution(
    r_bohr: NDArray[np.float64], rho: NDArray[np.float64]
) -> NDArray[np.float64]:
    return 4.0 * math.pi * r_bohr**2 * rho


def _integral_on_r(r_bohr: NDArray[np.float64], values: NDArray[np.float64]) -> float:
    return float(np.trapezoid(values, r_bohr))


def _radial_integral(r_bohr: NDArray[np.float64], values: NDArray[np.float64]) -> float:
    return _integral_on_r(r_bohr, _radial_distribution(r_bohr, values))


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


def _cumulative_from_distribution(
    r_bohr: NDArray[np.float64], distribution: NDArray[np.float64]
) -> NDArray[np.float64]:
    cumulative = np.zeros_like(r_bohr, dtype=float)
    cumulative[1:] = np.cumsum(0.5 * (distribution[:-1] + distribution[1:]) * np.diff(r_bohr))
    return cumulative


def _cumulative_electrons(
    r_bohr: NDArray[np.float64], rho: NDArray[np.float64]
) -> NDArray[np.float64]:
    return _cumulative_from_distribution(r_bohr, _radial_distribution(r_bohr, rho))


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
    return _as_float(value)


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


def _moment_metrics(
    r_bohr: NDArray[np.float64], distribution: NDArray[np.float64], total: float
) -> dict[str, float | None]:
    if total <= DENSITY_INTEGRAL_FLOOR:
        return {"mean_r_bohr": None, "mean_r2_bohr2": None, "rms_r_bohr": None}
    mean_r = _integral_on_r(r_bohr, r_bohr * distribution) / total
    mean_r2 = _integral_on_r(r_bohr, r_bohr**2 * distribution) / total
    return {
        "mean_r_bohr": float(mean_r),
        "mean_r2_bohr2": float(mean_r2),
        "rms_r_bohr": float(math.sqrt(max(mean_r2, 0.0))),
    }


def _pair_key(base_dataset_id: str, diffuse_dataset_id: str) -> tuple[str, str]:
    return (base_dataset_id, diffuse_dataset_id)


def _pair_kind(base_dataset_id: str, diffuse_dataset_id: str) -> str:
    return PAIR_KINDS.get(_pair_key(base_dataset_id, diffuse_dataset_id), "custom")


def _pair_output_stem(base_dataset_id: str, diffuse_dataset_id: str) -> str:
    key = _pair_key(base_dataset_id, diffuse_dataset_id)
    if key in PAIR_OUTPUT_STEMS:
        return PAIR_OUTPUT_STEMS[key]
    return "basis_sensitivity_" + f"{base_dataset_id}__vs__{diffuse_dataset_id}".replace(
        "-", "_"
    ).replace(".", "_")


def _safe_path_component(value: str, *, fallback: str) -> str:
    cleaned = value.strip().replace("/", "_").replace("\\", "_")
    return cleaned or fallback


def _pair_output_dirname(
    base_dataset_id: str, diffuse_dataset_id: str, base_basis_id: str
) -> str:
    return _safe_path_component(
        base_basis_id, fallback=_pair_output_stem(base_dataset_id, diffuse_dataset_id)
    )


def _expected_state_ids_for_pair(
    *,
    states: Sequence[AtomState] | None,
    config: ProfileDatasetConfig,
    base_dataset_id: str,
    diffuse_dataset_id: str,
) -> tuple[str, ...] | None:
    if states is None:
        return None
    base_state_ids = {
        job.state_id
        for job in build_jobs_for_datasets(
            list(states), dataset_ids=(base_dataset_id,), config=config
        )
    }
    diffuse_jobs = build_jobs_for_datasets(
        list(states), dataset_ids=(diffuse_dataset_id,), config=config
    )
    return tuple(job.state_id for job in diffuse_jobs if job.state_id in base_state_ids)


def _sensitivity_tier_and_flags(
    row: Mapping[str, Any],
    *,
    relative_l1_watch: float,
    relative_l1_outlier: float,
    max_cumulative_delta_watch_electrons: float,
    max_cumulative_delta_outlier_electrons: float,
    mean_radial_shift_watch_angstrom: float,
    mean_radial_shift_outlier_angstrom: float,
) -> tuple[str, tuple[str, ...]]:
    severe = False
    watch = False
    flags: list[str] = []

    relative_l1 = _maybe_float(row.get("relative_l1_delta"))
    if relative_l1 is not None:
        if relative_l1 >= relative_l1_outlier:
            severe = True
            flags.append("relative_l1_outlier")
        elif relative_l1 >= relative_l1_watch:
            watch = True
            flags.append("relative_l1_watch")

    max_cumulative = _maybe_float(row.get("max_abs_cumulative_delta_electrons"))
    if max_cumulative is not None:
        if max_cumulative >= max_cumulative_delta_outlier_electrons:
            severe = True
            flags.append("cumulative_delta_outlier")
        elif max_cumulative >= max_cumulative_delta_watch_electrons:
            watch = True
            flags.append("cumulative_delta_watch")

    mean_shift = _maybe_float(row.get("mean_abs_radial_shift_angstrom"))
    if mean_shift is not None:
        if mean_shift >= mean_radial_shift_outlier_angstrom:
            severe = True
            flags.append("mean_radial_shift_outlier")
        elif mean_shift >= mean_radial_shift_watch_angstrom:
            watch = True
            flags.append("mean_radial_shift_watch")

    if severe:
        return "high", tuple(flags)
    if watch:
        return "moderate", tuple(flags)
    return "low", tuple(flags)


def compare_profile_pair(
    base: ProfileDataset,
    diffuse: ProfileDataset,
    *,
    cutoffs_e_bohr3: Sequence[float],
    expected_state_ids: Sequence[str] | None = None,
    quantiles: Sequence[float] = DEFAULT_QUANTILES,
    tail_radii_bohr: Sequence[float] = DEFAULT_TAIL_RADII_BOHR,
    relative_l1_watch: float = DEFAULT_RELATIVE_L1_WATCH,
    relative_l1_outlier: float = DEFAULT_RELATIVE_L1_OUTLIER,
    max_cumulative_delta_watch_electrons: float = DEFAULT_MAX_CUMULATIVE_DELTA_WATCH_ELECTRONS,
    max_cumulative_delta_outlier_electrons: float = DEFAULT_MAX_CUMULATIVE_DELTA_OUTLIER_ELECTRONS,
    mean_radial_shift_watch_angstrom: float = DEFAULT_MEAN_RADIAL_SHIFT_WATCH_ANGSTROM,
    mean_radial_shift_outlier_angstrom: float = DEFAULT_MEAN_RADIAL_SHIFT_OUTLIER_ANGSTROM,
    max_electron_count_error: float = DEFAULT_MAX_ELECTRON_COUNT_ERROR,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compare one primary/diffuse profile pair and return detailed rows and summary."""

    if base.r_bohr.shape != diffuse.r_bohr.shape or not np.allclose(
        base.r_bohr, diffuse.r_bohr, rtol=0.0, atol=0.0
    ):
        raise ValueError(
            f"{base.dataset_id} and {diffuse.dataset_id}: radial grids do not match exactly"
        )
    base_state_ids = set(base.state_ids)
    diffuse_state_ids = set(diffuse.state_ids)
    if expected_state_ids is None:
        expected = tuple(state_id for state_id in base.state_ids if state_id in diffuse_state_ids)
    else:
        expected = tuple(expected_state_ids)
    missing_base = tuple(state_id for state_id in expected if state_id not in base_state_ids)
    missing_diffuse = tuple(state_id for state_id in expected if state_id not in diffuse_state_ids)
    common_state_ids = tuple(
        state_id
        for state_id in expected
        if state_id in base_state_ids and state_id in diffuse_state_ids
    )
    unexpected_common = tuple(
        sorted((base_state_ids & diffuse_state_ids) - set(expected))
    )

    comparison_id = f"{base.dataset_id}__vs__{diffuse.dataset_id}"
    pair_kind = _pair_kind(base.dataset_id, diffuse.dataset_id)
    rows: list[dict[str, Any]] = []
    for state_id in common_state_ids:
        base_digest = base.state_record_sha256_by_state_id.get(state_id)
        diffuse_digest = diffuse.state_record_sha256_by_state_id.get(state_id)
        if base_digest and diffuse_digest and base_digest != diffuse_digest:
            raise ValueError(
                f"{comparison_id}/{state_id}: state_record_sha256 mismatch "
                f"({base_digest} != {diffuse_digest})"
            )

        base_rho = base.densities_by_state_id[state_id]
        diffuse_rho = diffuse.densities_by_state_id[state_id]
        delta_rho = diffuse_rho - base_rho
        base_distribution = _radial_distribution(base.r_bohr, base_rho)
        diffuse_distribution = _radial_distribution(base.r_bohr, diffuse_rho)
        delta_distribution = diffuse_distribution - base_distribution
        base_cumulative = _cumulative_from_distribution(base.r_bohr, base_distribution)
        diffuse_cumulative = _cumulative_from_distribution(base.r_bohr, diffuse_distribution)
        delta_cumulative = diffuse_cumulative - base_cumulative

        state_meta = base.state_metadata.get(state_id, diffuse.state_metadata.get(state_id, {}))
        row: dict[str, Any] = {
            "comparison_id": comparison_id,
            "comparison_kind": pair_kind,
            "base_dataset_id": base.dataset_id,
            "diffuse_dataset_id": diffuse.dataset_id,
            "base_basis_id": base.basis_id,
            "diffuse_basis_id": diffuse.basis_id,
            **_state_prefix(state_id, state_meta),
            "base_state_record_sha256": base_digest,
            "diffuse_state_record_sha256": diffuse_digest,
            "state_record_sha256_match": bool(
                base_digest and diffuse_digest and base_digest == diffuse_digest
            ),
        }
        base_e = float(base_cumulative[-1])
        diffuse_e = float(diffuse_cumulative[-1])
        signed_delta_e = _integral_on_r(base.r_bohr, delta_distribution)
        l1_delta_e = _integral_on_r(base.r_bohr, np.abs(delta_distribution))
        denom = max(0.5 * (abs(base_e) + abs(diffuse_e)), DENSITY_INTEGRAL_FLOOR)
        integrated_abs_cumulative_delta = _integral_on_r(base.r_bohr, np.abs(delta_cumulative))
        mean_abs_shift_bohr = integrated_abs_cumulative_delta / denom
        expected_electron_count = _maybe_float(state_meta.get("electron_count"))
        base_electron_count_error = (
            None if expected_electron_count is None else base_e - expected_electron_count
        )
        diffuse_electron_count_error = (
            None if expected_electron_count is None else diffuse_e - expected_electron_count
        )
        max_abs_electron_count_error = max(
            abs(value)
            for value in (base_electron_count_error, diffuse_electron_count_error)
            if value is not None
        )
        base_moments = _moment_metrics(base.r_bohr, base_distribution, base_e)
        diffuse_moments = _moment_metrics(base.r_bohr, diffuse_distribution, diffuse_e)
        delta_mean_r_bohr = _delta(base_moments["mean_r_bohr"], diffuse_moments["mean_r_bohr"])
        delta_mean_r2_bohr2 = _delta(
            base_moments["mean_r2_bohr2"], diffuse_moments["mean_r2_bohr2"]
        )
        delta_rms_r_bohr = _delta(base_moments["rms_r_bohr"], diffuse_moments["rms_r_bohr"])
        row.update(
            {
                "base_electron_count_trapz": base_e,
                "diffuse_electron_count_trapz": diffuse_e,
                "base_electron_count_error": base_electron_count_error,
                "diffuse_electron_count_error": diffuse_electron_count_error,
                "max_abs_electron_count_error": max_abs_electron_count_error,
                "signed_delta_electrons_trapz": signed_delta_e,
                "abs_signed_delta_electrons_trapz": abs(signed_delta_e),
                "l1_delta_electrons_trapz": l1_delta_e,
                "radial_distribution_l1_delta_electrons": l1_delta_e,
                "relative_l1_delta": l1_delta_e / denom,
                "relative_radial_distribution_l1_delta": l1_delta_e / denom,
                "max_abs_radial_distribution_delta_e_per_bohr": float(
                    np.max(np.abs(delta_distribution))
                ),
                "r_at_max_abs_radial_distribution_delta_bohr": float(
                    base.r_bohr[int(np.argmax(np.abs(delta_distribution)))]
                ),
                "max_abs_density_delta_e_bohr3": float(np.max(np.abs(delta_rho))),
                "r_at_max_abs_density_delta_bohr": float(
                    base.r_bohr[int(np.argmax(np.abs(delta_rho)))]
                ),
                "max_abs_cumulative_delta_electrons": float(np.max(np.abs(delta_cumulative))),
                "r_at_max_abs_cumulative_delta_bohr": float(
                    base.r_bohr[int(np.argmax(np.abs(delta_cumulative)))]
                ),
                "integrated_abs_cumulative_delta_electron_bohr": integrated_abs_cumulative_delta,
                "integrated_abs_cumulative_delta_electron_angstrom": (
                    integrated_abs_cumulative_delta * BOHR_TO_ANGSTROM
                ),
                "mean_abs_radial_shift_bohr": mean_abs_shift_bohr,
                "mean_abs_radial_shift_angstrom": mean_abs_shift_bohr * BOHR_TO_ANGSTROM,
                "base_mean_r_bohr": base_moments["mean_r_bohr"],
                "diffuse_mean_r_bohr": diffuse_moments["mean_r_bohr"],
                "delta_mean_r_bohr": delta_mean_r_bohr,
                "delta_mean_r_angstrom": None
                if delta_mean_r_bohr is None
                else delta_mean_r_bohr * BOHR_TO_ANGSTROM,
                "base_mean_r2_bohr2": base_moments["mean_r2_bohr2"],
                "diffuse_mean_r2_bohr2": diffuse_moments["mean_r2_bohr2"],
                "delta_mean_r2_bohr2": delta_mean_r2_bohr2,
                "base_rms_r_bohr": base_moments["rms_r_bohr"],
                "diffuse_rms_r_bohr": diffuse_moments["rms_r_bohr"],
                "delta_rms_r_bohr": delta_rms_r_bohr,
                "delta_rms_r_angstrom": None
                if delta_rms_r_bohr is None
                else delta_rms_r_bohr * BOHR_TO_ANGSTROM,
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
            row[f"abs_delta_{label}"] = abs(diffuse_tail - base_tail)

        row["max_abs_quantile_radius_delta_angstrom"] = max_abs_quantile_delta_angstrom
        row["max_abs_cutoff_radius_delta_angstrom"] = max_abs_cutoff_delta_angstrom

        integrity_flags: list[str] = []
        if max_abs_electron_count_error > max_electron_count_error:
            integrity_flags.append("electron_count_integral")
        row["release_gate_status"] = "FAIL" if integrity_flags else "PASS"
        row["integrity_flags"] = ";".join(integrity_flags)
        tier, flags = _sensitivity_tier_and_flags(
            row,
            relative_l1_watch=relative_l1_watch,
            relative_l1_outlier=relative_l1_outlier,
            max_cumulative_delta_watch_electrons=max_cumulative_delta_watch_electrons,
            max_cumulative_delta_outlier_electrons=max_cumulative_delta_outlier_electrons,
            mean_radial_shift_watch_angstrom=mean_radial_shift_watch_angstrom,
            mean_radial_shift_outlier_angstrom=mean_radial_shift_outlier_angstrom,
        )
        row["sensitivity_tier"] = tier
        row["sensitivity_flags"] = ";".join(flags)
        row["status"] = row["release_gate_status"]
        rows.append(row)

    summary = _summarize_pair(
        comparison_id=comparison_id,
        pair_kind=pair_kind,
        base=base,
        diffuse=diffuse,
        rows=rows,
        expected_state_count=len(expected),
        missing_base=missing_base,
        missing_diffuse=missing_diffuse,
        unexpected_common=unexpected_common,
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
    pair_kind: str,
    base: ProfileDataset,
    diffuse: ProfileDataset,
    rows: Sequence[Mapping[str, Any]],
    expected_state_count: int,
    missing_base: Sequence[str],
    missing_diffuse: Sequence[str],
    unexpected_common: Sequence[str],
) -> dict[str, Any]:
    tier_counts = Counter(str(row.get("sensitivity_tier", "")) for row in rows)
    release_gate_fail_count = sum(1 for row in rows if row.get("release_gate_status") == "FAIL")
    return {
        "comparison_id": comparison_id,
        "comparison_kind": pair_kind,
        "base_dataset_id": base.dataset_id,
        "diffuse_dataset_id": diffuse.dataset_id,
        "base_basis_id": base.basis_id,
        "diffuse_basis_id": diffuse.basis_id,
        "expected_state_count": expected_state_count,
        "base_state_count": len(base.state_ids),
        "diffuse_state_count": len(diffuse.state_ids),
        "common_state_count": len(rows),
        "missing_base_state_count": len(missing_base),
        "missing_diffuse_state_count": len(missing_diffuse),
        "unexpected_common_state_count": len(unexpected_common),
        "missing_base_state_ids": ";".join(missing_base),
        "missing_diffuse_state_ids": ";".join(missing_diffuse),
        "unexpected_common_state_ids": ";".join(unexpected_common),
        "release_gate_fail_count": release_gate_fail_count,
        "low_sensitivity_count": tier_counts.get("low", 0),
        "moderate_sensitivity_count": tier_counts.get("moderate", 0),
        "high_sensitivity_count": tier_counts.get("high", 0),
        "outlier_count": tier_counts.get("high", 0) + release_gate_fail_count,
        "max_relative_l1_delta": _max_float(rows, "relative_l1_delta"),
        "max_abs_signed_delta_electrons_trapz": _max_float(
            rows, "signed_delta_electrons_trapz", absolute=True
        ),
        "max_l1_delta_electrons_trapz": _max_float(rows, "l1_delta_electrons_trapz"),
        "max_abs_cumulative_delta_electrons": _max_float(
            rows, "max_abs_cumulative_delta_electrons"
        ),
        "max_mean_abs_radial_shift_angstrom": _max_float(
            rows, "mean_abs_radial_shift_angstrom"
        ),
        "max_abs_delta_mean_r_angstrom": _max_float(
            rows, "delta_mean_r_angstrom", absolute=True
        ),
        "max_abs_delta_rms_r_angstrom": _max_float(
            rows, "delta_rms_r_angstrom", absolute=True
        ),
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


def _percentile(sorted_values: Sequence[float], fraction: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * fraction
    left = math.floor(position)
    right = math.ceil(position)
    if left == right:
        return float(sorted_values[left])
    weight = position - left
    return float(sorted_values[left] * (1.0 - weight) + sorted_values[right] * weight)


def _distribution_values(rows: Sequence[Mapping[str, Any]], metric: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _maybe_float(row.get(metric))
        if value is None:
            continue
        if metric.startswith("delta_") or metric.startswith("signed_"):
            value = abs(value)
        values.append(value)
    return sorted(values)


def _metric_distribution_rows(
    rows: Sequence[Mapping[str, Any]], *, comparison_id: str, comparison_kind: str
) -> list[dict[str, Any]]:
    distribution_rows: list[dict[str, Any]] = []
    for group_kind, group_fields in METRIC_DISTRIBUTION_GROUPS:
        grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
        if not group_fields:
            grouped[()] = list(rows)
        else:
            for row in rows:
                key = tuple(row.get(field) for field in group_fields)
                grouped.setdefault(key, []).append(row)
        for group_key, group_rows in sorted(grouped.items(), key=lambda item: str(item[0])):
            group_value = "all" if not group_fields else ";".join(str(part) for part in group_key)
            for metric in METRIC_DISTRIBUTION_METRICS:
                values = _distribution_values(group_rows, metric)
                if not values:
                    continue
                distribution_rows.append(
                    {
                        "comparison_id": comparison_id,
                        "comparison_kind": comparison_kind,
                        "group_kind": group_kind,
                        "group_value": group_value,
                        "metric": metric,
                        "n": len(values),
                        "min": values[0],
                        "p50": _percentile(values, 0.50),
                        "p90": _percentile(values, 0.90),
                        "p95": _percentile(values, 0.95),
                        "p99": _percentile(values, 0.99),
                        "max": values[-1],
                    }
                )
    return distribution_rows


def _is_outlier_row(row: Mapping[str, Any]) -> bool:
    return row.get("release_gate_status") == "FAIL" or row.get("sensitivity_tier") == "high"


def configured_basis_sensitivity_pairs(
    config: ProfileDatasetConfig, *, include_optional_x2c: bool = False
) -> tuple[tuple[str, str], ...]:
    """Return basis-sensitivity pairs present in a dataset config.

    The dyall-v4z/dyall-av4z anion comparison is the default scientific check.
    The x2c-QZVPall/x2c-QZVPall-s comparison is intentionally opt-in because it is
    an NMR-specialized diagnostic pair rather than the primary diffuse-augmentation test.
    """

    configured = set(config.dataset_ids)
    candidates = list(PRIMARY_COMPARISON_PAIRS)
    if include_optional_x2c:
        candidates.extend(OPTIONAL_COMPARISON_PAIRS)
    return tuple(pair for pair in candidates if pair[0] in configured and pair[1] in configured)


def build_basis_sensitivity_qa(
    *,
    config_path: Path = PROFILE_DATASETS_FILE,
    states_file: Path | None = STATES_FILE,
    profiles_root: Path = PROFILES_ROOT,
    qa_root: Path = QA_ROOT,
    pairs: Sequence[tuple[str, str]] | None = None,
    include_optional_x2c: bool = False,
    force: bool = False,
    require_complete: bool = True,
    warn_relative_l1: float | None = None,
    warn_delta_radius_angstrom: float | None = None,
    relative_l1_watch: float = DEFAULT_RELATIVE_L1_WATCH,
    relative_l1_outlier: float = DEFAULT_RELATIVE_L1_OUTLIER,
    max_cumulative_delta_watch_electrons: float = DEFAULT_MAX_CUMULATIVE_DELTA_WATCH_ELECTRONS,
    max_cumulative_delta_outlier_electrons: float = DEFAULT_MAX_CUMULATIVE_DELTA_OUTLIER_ELECTRONS,
    mean_radial_shift_watch_angstrom: float = DEFAULT_MEAN_RADIAL_SHIFT_WATCH_ANGSTROM,
    mean_radial_shift_outlier_angstrom: float = DEFAULT_MEAN_RADIAL_SHIFT_OUTLIER_ANGSTROM,
    max_electron_count_error: float = DEFAULT_MAX_ELECTRON_COUNT_ERROR,
) -> BasisSensitivityResult:
    """Build optional diffuse-basis profile-comparison QA artifacts."""

    if warn_relative_l1 is not None:
        relative_l1_watch = warn_relative_l1
    if warn_delta_radius_angstrom is not None:
        mean_radial_shift_watch_angstrom = warn_delta_radius_angstrom

    config = load_profile_dataset_config(config_path)
    selected_pairs = tuple(
        pairs
        or configured_basis_sensitivity_pairs(config, include_optional_x2c=include_optional_x2c)
    )
    if not selected_pairs:
        raise ValueError("no configured basis-sensitivity comparison pairs found")
    states = load_atom_states(states_file) if states_file is not None else None

    output_dir = qa_root / BASIS_SENSITIVITY_DIRNAME
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(f"{repo_relative_path(output_dir)} exists; use --force to overwrite")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    distribution_rows: list[dict[str, Any]] = []
    skipped_pairs: list[dict[str, Any]] = []
    completeness_errors: list[str] = []
    rows_by_stem: dict[str, list[dict[str, Any]]] = {}
    summaries_by_stem: dict[str, list[dict[str, Any]]] = {}
    distributions_by_stem: dict[str, list[dict[str, Any]]] = {}
    output_dirnames_by_stem: dict[str, str] = {}

    for base_dataset_id, diffuse_dataset_id in selected_pairs:
        base_dir = profiles_root / base_dataset_id
        diffuse_dir = profiles_root / diffuse_dataset_id
        if not base_dir.is_dir() or not diffuse_dir.is_dir():
            skipped = {
                "base_dataset_id": base_dataset_id,
                "diffuse_dataset_id": diffuse_dataset_id,
                "reason": "missing_profile_dataset_dir",
                "base_present": base_dir.is_dir(),
                "diffuse_present": diffuse_dir.is_dir(),
            }
            skipped_pairs.append(skipped)
            if require_complete:
                completeness_errors.append(
                    f"{base_dataset_id} -> {diffuse_dataset_id}: missing profile dataset dir"
                )
            continue
        expected_state_ids = _expected_state_ids_for_pair(
            states=states,
            config=config,
            base_dataset_id=base_dataset_id,
            diffuse_dataset_id=diffuse_dataset_id,
        )
        base = read_profile_dataset(profiles_root, base_dataset_id)
        diffuse = read_profile_dataset(profiles_root, diffuse_dataset_id)
        rows, summary = compare_profile_pair(
            base,
            diffuse,
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
            summary["missing_base_state_count"] or summary["missing_diffuse_state_count"]
        ):
            completeness_errors.append(
                f"{base_dataset_id} -> {diffuse_dataset_id}: missing expected states "
                f"base={summary['missing_base_state_ids']!r}, "
                f"diffuse={summary['missing_diffuse_state_ids']!r}"
            )
        stem = _pair_output_stem(base_dataset_id, diffuse_dataset_id)
        output_dirnames_by_stem[stem] = _pair_output_dirname(
            base_dataset_id, diffuse_dataset_id, base.basis_id
        )
        pair_distributions = _metric_distribution_rows(
            rows, comparison_id=summary["comparison_id"], comparison_kind=summary["comparison_kind"]
        )
        rows_by_stem[stem] = rows
        summaries_by_stem[stem] = [summary]
        distributions_by_stem[stem] = pair_distributions
        all_rows.extend(rows)
        summaries.append(summary)
        distribution_rows.extend(pair_distributions)

    if completeness_errors:
        raise ValueError(
            "incomplete basis-sensitivity comparison:\n" + "\n".join(completeness_errors)
        )
    if not all_rows:
        raise ValueError(
            "no basis-sensitivity profile rows were generated; "
            f"skipped_pairs={skipped_pairs!r}"
        )

    outliers = [row for row in all_rows if _is_outlier_row(row)]
    rows_csv = output_dir / "basis_sensitivity.csv"
    summary_csv = output_dir / "basis_sensitivity_summary.csv"
    outliers_csv = output_dir / "basis_sensitivity_outliers.csv"
    distributions_csv = output_dir / "basis_sensitivity_metric_distributions.csv"
    metadata_json = output_dir / "metadata.json"

    row_prefix = [
        "comparison_id",
        "comparison_kind",
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
        "release_gate_status",
        "sensitivity_tier",
        "sensitivity_flags",
        "integrity_flags",
        "status",
    ]
    summary_prefix = [
        "comparison_id",
        "comparison_kind",
        "base_dataset_id",
        "diffuse_dataset_id",
        "base_basis_id",
        "diffuse_basis_id",
        "expected_state_count",
        "common_state_count",
        "release_gate_fail_count",
        "outlier_count",
        "low_sensitivity_count",
        "moderate_sensitivity_count",
        "high_sensitivity_count",
    ]
    distribution_prefix = [
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
    _write_dict_rows_csv(rows_csv, _ordered_fieldnames(all_rows, row_prefix), all_rows)
    _write_dict_rows_csv(summary_csv, _ordered_fieldnames(summaries, summary_prefix), summaries)
    _write_dict_rows_csv(outliers_csv, _ordered_fieldnames(outliers, row_prefix), outliers)
    _write_dict_rows_csv(
        distributions_csv,
        _ordered_fieldnames(distribution_rows, distribution_prefix),
        distribution_rows,
    )

    pair_outputs: dict[str, dict[str, str]] = {}
    for stem, stem_rows in rows_by_stem.items():
        stem_summaries = summaries_by_stem[stem]
        stem_distributions = distributions_by_stem[stem]
        stem_outliers = [row for row in stem_rows if _is_outlier_row(row)]
        pair_output_dir = output_dir / output_dirnames_by_stem[stem]
        pair_output_dir.mkdir(parents=True, exist_ok=True)
        stem_rows_csv = pair_output_dir / "basis_sensitivity.csv"
        stem_summary_csv = pair_output_dir / "basis_sensitivity_summary.csv"
        stem_outliers_csv = pair_output_dir / "basis_sensitivity_outliers.csv"
        stem_distributions_csv = pair_output_dir / "basis_sensitivity_metric_distributions.csv"
        _write_dict_rows_csv(stem_rows_csv, _ordered_fieldnames(stem_rows, row_prefix), stem_rows)
        _write_dict_rows_csv(
            stem_summary_csv, _ordered_fieldnames(stem_summaries, summary_prefix), stem_summaries
        )
        _write_dict_rows_csv(
            stem_outliers_csv, _ordered_fieldnames(stem_outliers, row_prefix), stem_outliers
        )
        _write_dict_rows_csv(
            stem_distributions_csv,
            _ordered_fieldnames(stem_distributions, distribution_prefix),
            stem_distributions,
        )
        pair_outputs[stem] = {
            "output_dir": repo_relative_path(pair_output_dir),
            "rows_csv": repo_relative_path(stem_rows_csv),
            "summary_csv": repo_relative_path(stem_summary_csv),
            "outliers_csv": repo_relative_path(stem_outliers_csv),
            "metric_distributions_csv": repo_relative_path(stem_distributions_csv),
            "row_count": str(len(stem_rows)),
            "summary_count": str(len(stem_summaries)),
            "outlier_count": str(len(stem_outliers)),
            "metric_distribution_count": str(len(stem_distributions)),
        }

    write_json(
        metadata_json,
        {
            "schema_version": BASIS_SENSITIVITY_SCHEMA_VERSION,
            "profile_data_version": config.profile_data_version,
            "config": repo_relative_path(config_path),
            "states_file": None if states_file is None else repo_relative_path(states_file),
            "profiles_root": repo_relative_path(profiles_root),
            "qa_root": repo_relative_path(qa_root),
            "files": {
                "basis_sensitivity_csv": repo_relative_path(rows_csv),
                "basis_sensitivity_summary_csv": repo_relative_path(summary_csv),
                "basis_sensitivity_outliers_csv": repo_relative_path(outliers_csv),
                "basis_sensitivity_metric_distributions_csv": repo_relative_path(
                    distributions_csv
                ),
                "metadata_json": repo_relative_path(metadata_json),
            },
            "pair_outputs": pair_outputs,
            "comparison_pairs": [
                {
                    "base_dataset_id": base,
                    "diffuse_dataset_id": diffuse,
                    "comparison_kind": _pair_kind(base, diffuse),
                    "output_stem": _pair_output_stem(base, diffuse),
                    "output_dirname": output_dirnames_by_stem.get(
                        _pair_output_stem(base, diffuse)
                    ),
                    "required": _pair_key(base, diffuse) in PRIMARY_COMPARISON_PAIRS,
                }
                for base, diffuse in selected_pairs
            ],
            "skipped_pairs": skipped_pairs,
            "row_count": len(all_rows),
            "summary_count": len(summaries),
            "outlier_count": len(outliers),
            "metric_distribution_count": len(distribution_rows),
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
                "primary_pair": "dyall-v4z vs dyall-av4z",
                "optional_pair": "x2c-QZVPall vs x2c-QZVPall-s",
                "release_gate_status": "PASS/FAIL corruption or metadata-integrity gate",
                "sensitivity_tier": "low/moderate/high scientific sensitivity classification",
                "outliers_csv": (
                    "Rows with high sensitivity or release-gate failures; high sensitivity is "
                    "not by itself a release blocker."
                ),
            },
            "notes": [
                (
                    "The dyall-v4z/dyall-av4z comparison is the primary "
                    "diffuse-augmentation sensitivity check for anions."
                ),
                (
                    "The x2c-QZVPall/x2c-QZVPall-s pair is optional and diagnostic; "
                    "it is not used to summarize the dyall diffuse issue unless explicitly "
                    "requested."
                ),
                (
                    "Basis-sensitivity rows classify profile sensitivity. Large sensitivity "
                    "can be scientifically expected for formal or highly charged anions and "
                    "is not automatically a release failure."
                ),
                (
                    "Hard failures are reserved for metadata, state-digest, grid, "
                    "density, missing-expected-state, or electron-count-integrity problems."
                ),
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
        metric_distribution_count=len(distribution_rows),
        skipped_pairs=tuple(skipped_pairs),
        pair_outputs=pair_outputs,
    )
