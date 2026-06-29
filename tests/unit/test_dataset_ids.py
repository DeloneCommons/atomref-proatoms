from __future__ import annotations

from pathlib import Path

import pytest

from atomref_proatoms.datasets import (
    DATASET_IDS,
    PROFILE_DATA_VERSION,
    PROFILE_DATASETS_SCHEMA_VERSION,
    PRIMARY_DYALL_V4Z,
    PRIMARY_X2C_QZVPALL,
    assert_dataset_basis_match,
    expected_basis_for_dataset,
    load_profile_dataset_config,
    state_allowed_in_dataset,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "data" / "profile_datasets.yaml"


def test_profile_dataset_yaml_is_the_active_dataset_contract() -> None:
    config = load_profile_dataset_config(CONFIG)
    assert config.schema_version == PROFILE_DATASETS_SCHEMA_VERSION
    assert config.profile_data_version == PROFILE_DATA_VERSION == "1.0.0.dev0"
    assert config.dataset_ids == DATASET_IDS
    assert len(config.datasets) == 2
    assert config.defaults["expected_engine_version"] == "2.13.1"


def test_dataset_basis_mapping_is_explicit() -> None:
    assert expected_basis_for_dataset(PRIMARY_X2C_QZVPALL) == "x2c-QZVPall"
    assert expected_basis_for_dataset(PRIMARY_DYALL_V4Z) == "dyall-v4z"
    assert len(DATASET_IDS) == 2
    assert all(dataset_id.endswith("_v1") for dataset_id in DATASET_IDS)


def test_no_silent_basis_fallback() -> None:
    assert_dataset_basis_match(PRIMARY_X2C_QZVPALL, "x2c-QZVPall")
    with pytest.raises(ValueError):
        assert_dataset_basis_match(PRIMARY_X2C_QZVPALL, "x2c-QZVPall-s")


def test_v1_profile_datasets_are_neutral_only() -> None:
    assert state_allowed_in_dataset(PRIMARY_X2C_QZVPALL, z=53, charge=0)
    assert not state_allowed_in_dataset(PRIMARY_X2C_QZVPALL, z=53, charge=-1)
    assert not state_allowed_in_dataset(PRIMARY_X2C_QZVPALL, z=53, charge=1)
    assert state_allowed_in_dataset(PRIMARY_DYALL_V4Z, z=92, charge=0)
    assert not state_allowed_in_dataset(PRIMARY_DYALL_V4Z, z=92, charge=4)
