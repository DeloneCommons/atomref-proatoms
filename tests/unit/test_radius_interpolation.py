from __future__ import annotations

import math

import pytest

from atomref_proatoms.profiles import radius_at_density


def test_radius_at_density_interpolates_log_density_tail() -> None:
    r = [1.0, 2.0, 3.0]
    rho = [math.exp(0.0), math.exp(-1.0), math.exp(-2.0)]
    assert radius_at_density(r, rho, math.exp(-0.5)) == pytest.approx(1.5)


def test_radius_at_density_rejects_missing_crossing() -> None:
    with pytest.raises(ValueError):
        radius_at_density([1.0, 2.0, 3.0], [10.0, 9.0, 8.0], 1.0)


def test_radius_at_density_requires_strictly_increasing_radii() -> None:
    with pytest.raises(ValueError):
        radius_at_density([1.0, 1.0, 3.0], [3.0, 2.0, 1.0], 2.0)
