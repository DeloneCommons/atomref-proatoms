"""Placeholders and light checks for the future spherical UKS generator.

The full self-consistent spherical fractional-occupation UKS implementation should be
extracted from the proof-of-concept notebook only after the frozen data-layer tests pass.
"""

from __future__ import annotations


def validate_angular_block_size(l_value: int, block_size: int) -> None:
    if l_value < 0:
        raise ValueError("l_value must be non-negative")
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    degeneracy = 2 * l_value + 1
    if block_size % degeneracy != 0:
        raise ValueError(
            f"angular-momentum block size {block_size} is not divisible by 2*l+1={degeneracy}"
        )


def require_spherical_basis(mol: object) -> None:
    cart = getattr(mol, "cart", None)
    if cart is not False:
        raise ValueError("production spherical proatoms require mol.cart is False")
