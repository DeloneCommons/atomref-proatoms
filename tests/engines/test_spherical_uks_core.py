from __future__ import annotations

import numpy as np
import pytest

from atomref_proatoms.engines.spherical_uks import (
    angular_block_indices,
    ao_angular_momenta,
    configuration_l_counts_after_core_removal,
    effective_l_counts_for_mol,
    expand_configuration_shells,
    occupation_from_l_counts,
    spherical_block_eigh,
    validate_spherical_ao_layout,
)
from atomref_proatoms.states import AtomState


class FakeMol:
    cart = False

    def __init__(self, shell_l: list[int]) -> None:
        self.shell_l = shell_l
        self.nbas = len(shell_l)
        loc = [0]
        for l_value in shell_l:
            loc.append(loc[-1] + 2 * l_value + 1)
        self._ao_loc = np.asarray(loc, dtype=int)

    def nao_nr(self) -> int:
        return int(self._ao_loc[-1])

    def ao_loc_nr(self) -> np.ndarray:
        return self._ao_loc

    def bas_angular(self, ibas: int) -> int:
        return self.shell_l[ibas]


class FakeMF:
    def __init__(self, mol: FakeMol) -> None:
        self.mol = mol

    @staticmethod
    def _eigh(fock: np.ndarray, ovlp: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        assert np.allclose(ovlp, np.eye(ovlp.shape[0]))
        return np.linalg.eigh(fock)


def test_ao_angular_momenta_and_blocks() -> None:
    mol = FakeMol([0, 0, 1])
    assert ao_angular_momenta(mol).tolist() == [0, 0, 1, 1, 1]
    validate_spherical_ao_layout(mol)
    blocks = angular_block_indices(mol)
    assert [(l_value, idx.tolist()) for l_value, idx in blocks] == [(0, [0, 1]), (1, [2, 3, 4])]


def test_occupation_from_l_counts_distributes_fractional_open_shells() -> None:
    mol = FakeMol([0, 0, 1])
    occ = occupation_from_l_counts(mol, {0: 2, 1: 2}, 1.0)
    assert np.allclose(occ, [1.0, 1.0, 2.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0])
    assert float(occ.sum()) == pytest.approx(4.0)


def test_occupation_from_l_counts_rejects_absent_l() -> None:
    mol = FakeMol([0])
    with pytest.raises(ValueError, match="absent from basis"):
        occupation_from_l_counts(mol, {1: 1}, 1.0)


def test_spherical_block_eigh_repeats_radial_eigenvalues_over_m_components() -> None:
    mol = FakeMol([0, 0, 1])
    fock = np.diag([1.0, 2.0, 3.0, 3.0, 3.0])
    overlap = np.eye(5)

    energy, coeff = spherical_block_eigh(FakeMF(mol), fock, overlap)

    assert np.allclose(energy, [1.0, 2.0, 3.0, 3.0, 3.0])
    assert coeff.shape == (5, 5)
    assert np.allclose(coeff.T @ coeff, np.eye(5))


def test_expand_configuration_shells_expands_bracketed_core() -> None:
    shells = expand_configuration_shells("[Ne] 3s2 3p6")

    assert shells == (
        (1, 0, 2.0),
        (2, 0, 2.0),
        (2, 1, 6.0),
        (3, 0, 2.0),
        (3, 1, 6.0),
    )


def test_configuration_l_counts_after_core_removal_for_transition_metal() -> None:
    valence = configuration_l_counts_after_core_removal("[Ar] 3d8 4s2", 18)

    assert valence == {0: 2.0, 2: 8.0}


def test_effective_l_counts_for_ecp_mol_preserve_spin_by_l() -> None:
    state = AtomState(
        {
            "schema_version": "atomref.proatoms.state.v2",
            "state_id": "Ni_q0_mult3_custom",
            "symbol": "Ni",
            "z": 28,
            "charge": 0,
            "electron_count": 28,
            "spin_2s": 2,
            "multiplicity": 3,
            "configuration": "[Ar] 3d8 4s2",
            "state_role": "custom_diagnostic",
            "spin_model": "curated_ground_multiplicity",
            "spin_variant": "curated_multiplicity",
            "occupation_policy": "spherical_l_counts_from_curated_multiplicity_v2",
            "state_category": "nist_reference",
            "curation_status": "custom",
            "alpha_l_counts": {"0": 4, "1": 6, "2": 5},
            "beta_l_counts": {"0": 4, "1": 6, "2": 3},
            "notes": [],
        }
    )
    mol = type("FakeEcpMol", (), {"nelectron": 10, "spin": 2})()

    alpha, beta = effective_l_counts_for_mol(state, mol)

    assert alpha == {0: 1.0, 2: 5.0}
    assert beta == {0: 1.0, 2: 3.0}
