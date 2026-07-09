"""Profile-dataset configuration loading and scope rules."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .paths import PROFILE_DATASETS_FILE

PROFILE_DATASETS_SCHEMA_VERSION = "atomref.proatoms.profile_datasets.v1"
PROFILE_DATA_VERSION = "2.0.0"

PRIMARY_X2C_QZVPALL = "pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2"
PRIMARY_DYALL_V4Z = "pbe0_sfx2c_dyallv4z_h-lr_spherical_v2"
SUPPLEMENTED_X2C_QZVPALL_S = "pbe0_sfx2c_x2cqzvpalls_h-rn_spherical_v2"
AUGMENTED_DYALL_AV4Z = "pbe0_sfx2c_dyallav4z_h-ba_hf-ra_spherical_v2"
PRIMARY_PROFILE_DATASETS = (PRIMARY_X2C_QZVPALL, PRIMARY_DYALL_V4Z)
SUPPLEMENTED_PROFILE_DATASETS = (SUPPLEMENTED_X2C_QZVPALL_S, AUGMENTED_DYALL_AV4Z)
MULTIWFN_ARTIFACT_SCOPE_NONE = "none"
MULTIWFN_ARTIFACT_SCOPE_ALL_STATES = "all_states"
MULTIWFN_ARTIFACT_SCOPE_NEUTRAL_ATOMS = "neutral_atoms"
ALLOWED_MULTIWFN_ARTIFACT_SCOPES = frozenset(
    {
        MULTIWFN_ARTIFACT_SCOPE_NONE,
        MULTIWFN_ARTIFACT_SCOPE_ALL_STATES,
        MULTIWFN_ARTIFACT_SCOPE_NEUTRAL_ATOMS,
    }
)


@dataclass(frozen=True)
class DatasetScope:
    """One configured profile dataset and its state-selection policy."""

    dataset_id: str
    basis_id: str
    role: str
    coverage_label: str
    include_charges: str
    z_intervals: tuple[tuple[int, int], ...]
    include_state_roles: tuple[str, ...]
    diffuse: bool
    multiwfn_rad: str = MULTIWFN_ARTIFACT_SCOPE_NONE
    multiwfn_wfn: str = MULTIWFN_ARTIFACT_SCOPE_NONE
    exclude_symbols: tuple[str, ...] = ()
    exclude_symbols_for_anions: tuple[str, ...] = ()

    @property
    def allow_neutral(self) -> bool:
        return self.include_charges in {"all", "neutral_only", "neutral_and_negative"}

    @property
    def allow_cation(self) -> bool:
        return self.include_charges == "all"

    @property
    def allow_anion(self) -> bool:
        return self.include_charges in {"all", "negative_only", "neutral_and_negative"}

    def covers_z(self, z_value: int) -> bool:
        return any(start <= z_value <= end for start, end in self.z_intervals)

    def allows_symbol(self, symbol: str | None, *, charge: int | None = None) -> bool:
        if symbol is None:
            return True
        if symbol in self.exclude_symbols:
            return False
        return not (
            charge is not None and charge < 0 and symbol in self.exclude_symbols_for_anions
        )

    def allows_charge(self, charge: int) -> bool:
        if charge == 0:
            return self.allow_neutral
        if charge > 0:
            return self.allow_cation
        return self.allow_anion

    def allows_multiwfn_rad(self, *, charge: int) -> bool:
        return _artifact_scope_allows_charge(self.multiwfn_rad, charge=charge)

    def allows_multiwfn_wfn(self, *, charge: int) -> bool:
        return _artifact_scope_allows_charge(self.multiwfn_wfn, charge=charge)


def _artifact_scope_allows_charge(scope: str, *, charge: int) -> bool:
    if scope == MULTIWFN_ARTIFACT_SCOPE_NONE:
        return False
    if scope == MULTIWFN_ARTIFACT_SCOPE_ALL_STATES:
        return True
    if scope == MULTIWFN_ARTIFACT_SCOPE_NEUTRAL_ATOMS:
        return charge == 0
    raise ValueError(f"Unknown Multiwfn artifact scope: {scope!r}")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"profile dataset config not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"profile dataset config must be a mapping: {path}")
    return data


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"profile dataset config key {key!r} must be a mapping")
    return value


def _scope_from_record(record: dict[str, Any]) -> DatasetScope:
    required = {
        "dataset_id",
        "basis_id",
        "role",
        "coverage_label",
        "z_intervals",
        "include_charges",
        "include_state_roles",
        "diffuse",
    }
    missing = sorted(required - set(record))
    if missing:
        raise ValueError(f"dataset record missing fields {missing}: {record!r}")
    intervals_raw = record["z_intervals"]
    if not isinstance(intervals_raw, list) or not intervals_raw:
        raise ValueError(f"dataset {record['dataset_id']}: z_intervals must be a non-empty list")
    intervals: list[tuple[int, int]] = []
    for item in intervals_raw:
        if not isinstance(item, list | tuple) or len(item) != 2:
            raise ValueError(f"dataset {record['dataset_id']}: invalid z interval {item!r}")
        start, end = int(item[0]), int(item[1])
        if start < 1 or end < start:
            raise ValueError(f"dataset {record['dataset_id']}: invalid z interval {item!r}")
        intervals.append((start, end))
    include_charges = str(record["include_charges"])
    if include_charges not in {"all", "neutral_only", "negative_only", "neutral_and_negative"}:
        raise ValueError(
            f"dataset {record['dataset_id']}: include_charges must be 'all', "
            "'neutral_only', 'negative_only', or 'neutral_and_negative'"
        )
    roles_raw = record["include_state_roles"]
    if not isinstance(roles_raw, list) or not roles_raw:
        raise ValueError(f"dataset {record['dataset_id']}: include_state_roles must be non-empty")
    artifacts_raw = record.get("multiwfn_artifacts", {})
    if not isinstance(artifacts_raw, dict):
        raise ValueError(f"dataset {record['dataset_id']}: multiwfn_artifacts must be a mapping")
    multiwfn_rad = str(artifacts_raw.get("rad", MULTIWFN_ARTIFACT_SCOPE_NONE))
    multiwfn_wfn = str(artifacts_raw.get("wfn", MULTIWFN_ARTIFACT_SCOPE_NONE))
    for label, scope in {"rad": multiwfn_rad, "wfn": multiwfn_wfn}.items():
        if scope not in ALLOWED_MULTIWFN_ARTIFACT_SCOPES:
            raise ValueError(
                f"dataset {record['dataset_id']}: multiwfn_artifacts.{label} must be one of "
                f"{sorted(ALLOWED_MULTIWFN_ARTIFACT_SCOPES)}, got {scope!r}"
            )
    exclude_symbols_raw = record.get("exclude_symbols", [])
    if not isinstance(exclude_symbols_raw, list):
        raise ValueError(f"dataset {record['dataset_id']}: exclude_symbols must be a list")
    exclude_symbols_for_anions_raw = record.get("exclude_symbols_for_anions", [])
    if not isinstance(exclude_symbols_for_anions_raw, list):
        raise ValueError(
            f"dataset {record['dataset_id']}: exclude_symbols_for_anions must be a list"
        )
    return DatasetScope(
        dataset_id=str(record["dataset_id"]),
        basis_id=str(record["basis_id"]),
        role=str(record["role"]),
        coverage_label=str(record["coverage_label"]),
        include_charges=include_charges,
        z_intervals=tuple(intervals),
        include_state_roles=tuple(str(role) for role in roles_raw),
        diffuse=bool(record["diffuse"]),
        multiwfn_rad=multiwfn_rad,
        multiwfn_wfn=multiwfn_wfn,
        exclude_symbols=tuple(str(symbol) for symbol in exclude_symbols_raw),
        exclude_symbols_for_anions=tuple(
            str(symbol) for symbol in exclude_symbols_for_anions_raw
        ),
    )


@dataclass(frozen=True)
class ProfileDatasetConfig:
    """Parsed ``data/profile_datasets.yaml`` configuration."""

    path: Path
    schema_version: str
    profile_data_version: str
    defaults: dict[str, Any]
    profile_grid: dict[str, Any]
    qa_grid: dict[str, Any]
    cutoffs_e_bohr3: tuple[float, ...]
    scopes: tuple[DatasetScope, ...]

    @property
    def datasets(self) -> tuple[DatasetScope, ...]:
        return self.scopes

    @property
    def dataset_ids(self) -> tuple[str, ...]:
        return tuple(scope.dataset_id for scope in self.scopes)

    @property
    def data(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile_data_version": self.profile_data_version,
            "defaults": self.defaults,
            "profile_grid": self.profile_grid,
            "qa_grid": self.qa_grid,
            "cutoffs_e_bohr3": list(self.cutoffs_e_bohr3),
            "datasets": [scope.__dict__ for scope in self.scopes],
        }

    def scope(self, dataset_id: str) -> DatasetScope:
        for scope in self.scopes:
            if scope.dataset_id == dataset_id:
                return scope
        raise ValueError(f"Unknown dataset_id: {dataset_id}")


def load_profile_dataset_config(path: Path = PROFILE_DATASETS_FILE) -> ProfileDatasetConfig:
    """Load and validate the single active profile-dataset YAML file."""

    path = Path(path)
    data = _read_yaml(path)
    schema_version = str(data.get("schema_version", ""))
    if schema_version != PROFILE_DATASETS_SCHEMA_VERSION:
        raise ValueError(
            f"unexpected profile dataset schema_version {schema_version!r}; "
            f"expected {PROFILE_DATASETS_SCHEMA_VERSION!r}"
        )
    profile_data_version = str(data.get("profile_data_version", ""))
    if not profile_data_version:
        raise ValueError("profile_data_version is required")
    defaults = _require_mapping(data, "defaults")
    profile_grid = _require_mapping(data, "profile_grid")
    qa_grid = _require_mapping(data, "qa_grid")
    cutoffs_raw = data.get("cutoffs_e_bohr3")
    if not isinstance(cutoffs_raw, list) or not cutoffs_raw:
        raise ValueError("cutoffs_e_bohr3 must be a non-empty list")
    datasets_raw = data.get("datasets")
    if not isinstance(datasets_raw, list) or not datasets_raw:
        raise ValueError("datasets must be a non-empty list")
    scopes = tuple(_scope_from_record(record) for record in datasets_raw)
    ids = [scope.dataset_id for scope in scopes]
    if len(ids) != len(set(ids)):
        raise ValueError("dataset IDs must be unique")
    return ProfileDatasetConfig(
        path=path,
        schema_version=schema_version,
        profile_data_version=profile_data_version,
        defaults=defaults,
        profile_grid=profile_grid,
        qa_grid=qa_grid,
        cutoffs_e_bohr3=tuple(float(value) for value in cutoffs_raw),
        scopes=scopes,
    )


@lru_cache(maxsize=8)
def _cached_profile_dataset_config(path_text: str) -> ProfileDatasetConfig:
    return load_profile_dataset_config(Path(path_text))


def profile_dataset_config(path: Path = PROFILE_DATASETS_FILE) -> ProfileDatasetConfig:
    """Return the cached active profile-dataset config."""

    return _cached_profile_dataset_config(str(Path(path).resolve()))


def _load_default_dataset_indexes() -> tuple[
    tuple[str, ...],
    dict[str, DatasetScope],
    dict[str, tuple[str, ...]],
    dict[str, str],
]:
    """Return repo-default dataset indexes when the repo data file exists.

    Maintainer scripts run from a repository checkout and expect these compatibility
    constants to be populated.  Installed wheels used by the public generator do not
    carry the full repo-root ``data/profile_datasets.yaml`` file, so importing this
    module must remain safe when that default file is absent.
    """

    try:
        config = profile_dataset_config()
    except FileNotFoundError:
        return (), {}, {}, {}
    basis_to_datasets: dict[str, tuple[str, ...]] = {}
    for scope in config.scopes:
        basis_to_datasets.setdefault(scope.basis_id, ())
        basis_to_datasets[scope.basis_id] = (*basis_to_datasets[scope.basis_id], scope.dataset_id)
    return (
        config.dataset_ids,
        {scope.dataset_id: scope for scope in config.scopes},
        basis_to_datasets,
        {scope.dataset_id: scope.basis_id for scope in config.scopes},
    )


DATASET_IDS, DATASET_SCOPES, BASIS_TO_DATASETS, DATASET_TO_BASIS = (
    _load_default_dataset_indexes()
)


def dataset_scope(dataset_id: str, *, config: ProfileDatasetConfig | None = None) -> DatasetScope:
    selected_config = config or profile_dataset_config()
    return selected_config.scope(dataset_id)


def expected_basis_for_dataset(dataset_id: str) -> str:
    return dataset_scope(dataset_id).basis_id


def assert_dataset_basis_match(dataset_id: str, basis_id: str) -> None:
    expected = expected_basis_for_dataset(dataset_id)
    if basis_id != expected:
        raise ValueError(
            f"No silent basis fallback allowed: dataset {dataset_id} "
            f"requires {expected}, got {basis_id}"
        )


def state_allowed_in_dataset(
    dataset_id: str,
    *,
    z: int,
    charge: int,
    state_role: str = "reference",
    symbol: str | None = None,
) -> bool:
    scope = dataset_scope(dataset_id)
    return (
        scope.covers_z(z)
        and scope.allows_symbol(symbol, charge=charge)
        and scope.allows_charge(charge)
        and state_role in scope.include_state_roles
    )


def multiwfn_rad_allowed_for_dataset(dataset_id: str, *, charge: int) -> bool:
    return dataset_scope(dataset_id).allows_multiwfn_rad(charge=charge)


def multiwfn_wfn_allowed_for_dataset(dataset_id: str, *, charge: int) -> bool:
    return dataset_scope(dataset_id).allows_multiwfn_wfn(charge=charge)
