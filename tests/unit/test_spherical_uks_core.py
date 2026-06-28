from __future__ import annotations

import numpy as np
import pytest

from atomref_proatoms.spherical_uks import (
    angular_block_indices,
    ao_angular_momenta,
    occupation_from_l_counts,
    spherical_block_eigh,
    validate_spherical_ao_layout,
)


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
