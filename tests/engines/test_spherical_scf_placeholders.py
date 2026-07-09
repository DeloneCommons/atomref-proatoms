from __future__ import annotations

import pytest

from atomref_proatoms.engines.spherical_scf import (
    require_spherical_basis,
    validate_angular_block_size,
)


def test_validate_angular_block_size_accepts_degeneracy_multiples() -> None:
    validate_angular_block_size(0, 3)
    validate_angular_block_size(1, 9)
    validate_angular_block_size(2, 10)


def test_validate_angular_block_size_rejects_invalid_blocks() -> None:
    with pytest.raises(ValueError):
        validate_angular_block_size(1, 4)


def test_require_spherical_basis_checks_mol_cart_false() -> None:
    class Mol:
        cart = False

    require_spherical_basis(Mol())

    class CartesianMol:
        cart = True

    with pytest.raises(ValueError):
        require_spherical_basis(CartesianMol())
