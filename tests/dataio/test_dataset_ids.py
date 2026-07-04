from __future__ import annotations

from pathlib import Path

import pytest

from atomref_proatoms.dataio.basis import basis_covers_z, list_basis_bundles
from atomref_proatoms.dataio.datasets import (
    ANION_DYALL_AV4Z,
    ANION_SENSITIVITY_DATASETS,
    ANION_X2C_QZVPALL_S,
    DATASET_IDS,
    PRIMARY_DYALL_V4Z,
    PRIMARY_PROFILE_DATASETS,
    PRIMARY_X2C_QZVPALL,
    PROFILE_DATA_VERSION,
    PROFILE_DATASETS_SCHEMA_VERSION,
    assert_dataset_basis_match,
    expected_basis_for_dataset,
    load_profile_dataset_config,
    state_allowed_in_dataset,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "data" / "profile_datasets.yaml"
BASIS_ROOT = ROOT / "data" / "basis_sets"


ALL_CURATED_ROLES = {
    "reference",
    "reference_uncertain",
    "bound_experimental",
    "bound_provisional",
    "diagnostic_theory",
    "formal_monoanion",
    "formal_multianion",
}
ANION_ROLES = {
    "bound_experimental",
    "bound_provisional",
    "formal_monoanion",
    "formal_multianion",
}


def test_profile_dataset_yaml_is_the_active_dataset_contract() -> None:
    config = load_profile_dataset_config(CONFIG)
    assert config.schema_version == PROFILE_DATASETS_SCHEMA_VERSION
    assert config.profile_data_version == PROFILE_DATA_VERSION == "2.0.0"
    assert config.dataset_ids == DATASET_IDS
    assert len(config.datasets) == 4
    assert config.defaults["expected_engine_version"] == "2.13.1"


def test_dataset_basis_mapping_is_explicit() -> None:
    assert expected_basis_for_dataset(PRIMARY_X2C_QZVPALL) == "x2c-QZVPall"
    assert expected_basis_for_dataset(PRIMARY_DYALL_V4Z) == "dyall-v4z"
    assert expected_basis_for_dataset(ANION_X2C_QZVPALL_S) == "x2c-QZVPall-s"
    assert expected_basis_for_dataset(ANION_DYALL_AV4Z) == "dyall-av4z"
    assert len(DATASET_IDS) == 4
    assert all(dataset_id.endswith("_v2") for dataset_id in DATASET_IDS)


def test_primary_datasets_are_not_split_by_charge_class() -> None:
    assert PRIMARY_PROFILE_DATASETS == (PRIMARY_X2C_QZVPALL, PRIMARY_DYALL_V4Z)
    assert state_allowed_in_dataset(PRIMARY_X2C_QZVPALL, z=53, charge=0)
    assert state_allowed_in_dataset(
        PRIMARY_X2C_QZVPALL, z=53, charge=-1, state_role="bound_experimental"
    )
    assert state_allowed_in_dataset(PRIMARY_X2C_QZVPALL, z=53, charge=1)
    assert not state_allowed_in_dataset(PRIMARY_X2C_QZVPALL, z=87, charge=0)
    assert state_allowed_in_dataset(PRIMARY_DYALL_V4Z, z=92, charge=3)
    assert state_allowed_in_dataset(
        PRIMARY_DYALL_V4Z, z=6, charge=-3, state_role="formal_multianion"
    )
    assert state_allowed_in_dataset(
        PRIMARY_DYALL_V4Z, z=92, charge=-1, state_role="bound_experimental", symbol="U"
    )
    assert state_allowed_in_dataset(
        PRIMARY_DYALL_V4Z, z=91, charge=-1, state_role="diagnostic_theory", symbol="Pa"
    )
    assert not state_allowed_in_dataset(PRIMARY_DYALL_V4Z, z=104, charge=0)


def test_diffuse_sensitivity_datasets_are_anion_only() -> None:
    assert ANION_SENSITIVITY_DATASETS == (ANION_X2C_QZVPALL_S, ANION_DYALL_AV4Z)
    assert state_allowed_in_dataset(
        ANION_X2C_QZVPALL_S, z=53, charge=-1, state_role="bound_experimental"
    )
    assert state_allowed_in_dataset(
        ANION_X2C_QZVPALL_S, z=6, charge=-3, state_role="formal_multianion"
    )
    assert not state_allowed_in_dataset(ANION_X2C_QZVPALL_S, z=53, charge=0)
    assert not state_allowed_in_dataset(ANION_X2C_QZVPALL_S, z=53, charge=1)
    assert state_allowed_in_dataset(
        ANION_DYALL_AV4Z, z=56, charge=-1, state_role="formal_monoanion"
    )
    assert state_allowed_in_dataset(
        ANION_DYALL_AV4Z, z=72, charge=-1, state_role="bound_experimental"
    )
    assert not state_allowed_in_dataset(
        ANION_DYALL_AV4Z, z=57, charge=-1, state_role="bound_experimental"
    )
    assert not state_allowed_in_dataset(
        ANION_DYALL_AV4Z, z=92, charge=-1, state_role="bound_experimental", symbol="U"
    )
    assert not state_allowed_in_dataset(
        ANION_DYALL_AV4Z, z=88, charge=-1, state_role="bound_provisional", symbol="Ra"
    )


def test_dataset_state_role_scopes_are_explicit() -> None:
    config = load_profile_dataset_config(CONFIG)
    for dataset_id in PRIMARY_PROFILE_DATASETS:
        assert set(config.scope(dataset_id).include_state_roles) == ALL_CURATED_ROLES
    for dataset_id in ANION_SENSITIVITY_DATASETS:
        assert set(config.scope(dataset_id).include_state_roles) == ANION_ROLES


def test_dataset_coverage_is_within_declared_basis_coverage() -> None:
    config = load_profile_dataset_config(CONFIG)
    bundles = {bundle.basis_id: bundle for bundle in list_basis_bundles(BASIS_ROOT)}
    for scope in config.scopes:
        bundle = bundles[scope.basis_id]
        for start, end in scope.z_intervals:
            assert basis_covers_z(bundle, start)
            assert basis_covers_z(bundle, end)


def test_no_silent_basis_fallback() -> None:
    assert_dataset_basis_match(PRIMARY_X2C_QZVPALL, "x2c-QZVPall")
    with pytest.raises(ValueError):
        assert_dataset_basis_match(PRIMARY_X2C_QZVPALL, "x2c-QZVPall-s")
