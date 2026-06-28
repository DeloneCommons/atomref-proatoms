from __future__ import annotations

import pytest

from atomref_proatoms.datasets import (
    ANION_X2C_QZVPALL_S,
    DATASET_IDS,
    PRIMARY_X2C_QZVPALL,
    assert_dataset_basis_match,
    expected_basis_for_dataset,
    state_allowed_in_dataset,
)


def test_dataset_basis_mapping_is_explicit() -> None:
    assert expected_basis_for_dataset(PRIMARY_X2C_QZVPALL) == "x2c-QZVPall"
    assert expected_basis_for_dataset(ANION_X2C_QZVPALL_S) == "x2c-QZVPall-s"
    assert len(DATASET_IDS) == 4


def test_no_silent_basis_fallback() -> None:
    assert_dataset_basis_match(PRIMARY_X2C_QZVPALL, "x2c-QZVPall")
    with pytest.raises(ValueError):
        assert_dataset_basis_match(PRIMARY_X2C_QZVPALL, "x2c-QZVPall-s")


def test_diffuse_sensitivity_dataset_is_anion_only() -> None:
    assert state_allowed_in_dataset(ANION_X2C_QZVPALL_S, z=53, charge=-1)
    assert not state_allowed_in_dataset(ANION_X2C_QZVPALL_S, z=53, charge=0)
    assert not state_allowed_in_dataset(ANION_X2C_QZVPALL_S, z=53, charge=1)
