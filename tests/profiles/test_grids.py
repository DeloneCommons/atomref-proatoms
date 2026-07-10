from __future__ import annotations

import numpy as np
import pytest

from atomref_proatoms.profiles.grids import (
    angular_grid,
    default_profile_grid,
    fibonacci_angular_grid,
    gauss_legendre_log_grid,
    weighted_mean_and_std,
)


def test_default_profile_grid_matches_release_contract() -> None:
    r = default_profile_grid()

    assert r.shape == (1200,)
    assert r[0] == pytest.approx(1.0e-6)
    assert r[-1] == pytest.approx(60.0)


def test_gauss_legendre_log_grid_has_positive_nodes_and_weights() -> None:
    r, w_t = gauss_legendre_log_grid(1e-3, 10.0, 24)
    assert r.shape == (24,)
    assert w_t.shape == (24,)
    assert np.all(r > 0)
    assert np.all(w_t > 0)
    assert np.all(np.diff(r) > 0)


def test_fibonacci_angular_grid_is_normalized() -> None:
    directions, weights = fibonacci_angular_grid(32)
    assert directions.shape == (32, 3)
    assert weights.shape == (32,)
    assert np.allclose(np.linalg.norm(directions, axis=1), 1.0)
    assert float(weights.sum()) == pytest.approx(1.0)


def test_angular_grid_can_force_no_pyscf_fallback() -> None:
    directions, weights = angular_grid(16, prefer_pyscf=False)
    assert directions.shape == (16, 3)
    assert float(weights.sum()) == pytest.approx(1.0)


def test_angular_grid_falls_back_for_unsupported_pyscf_size(monkeypatch) -> None:
    from atomref_proatoms.profiles import grids

    def unsupported_grid(_n_points: int):
        raise ValueError("Unsupported angular grids")

    monkeypatch.setattr(grids, "pyscf_angular_grid", unsupported_grid)

    directions, weights = angular_grid(4, prefer_pyscf=True)

    assert directions.shape == (4, 3)
    assert float(weights.sum()) == pytest.approx(1.0)


def test_weighted_mean_and_std() -> None:
    mean, std = weighted_mean_and_std(np.array([1.0, 3.0]), np.array([0.25, 0.75]))
    assert mean == pytest.approx(2.5)
    assert std == pytest.approx(0.86602540378)
