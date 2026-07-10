from __future__ import annotations

import csv

import numpy as np
import pytest

from atomref_proatoms.profiles.interpolation import interpolate_density, load_profile_csv


def test_interpolate_density_loglog() -> None:
    r = [1.0, 10.0]
    rho = [100.0, 1.0]
    query = interpolate_density(r, rho, [1.0, np.sqrt(10.0), 10.0])
    assert query[0] == pytest.approx(100.0)
    assert query[1] == pytest.approx(10.0)
    assert query[2] == pytest.approx(1.0)


def test_interpolate_density_linear_fallback_for_zero_density() -> None:
    query = interpolate_density([1.0, 2.0], [1.0, 0.0], [1.5], mode="loglog")
    assert query[0] == pytest.approx(0.5)


def test_load_profile_csv_requires_density_column_for_wide_csv(tmp_path) -> None:
    path = tmp_path / "profiles.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["r_bohr", "rho_e_bohr3__H", "rho_e_bohr3__He"])
        writer.writerow(["1.0", "2.0", "3.0"])
        writer.writerow(["2.0", "1.0", "1.5"])
    with pytest.raises(ValueError, match="density_column"):
        load_profile_csv(path)
    r, rho = load_profile_csv(path, density_column="rho_e_bohr3__H")
    assert r.tolist() == [1.0, 2.0]
    assert rho.tolist() == [2.0, 1.0]
