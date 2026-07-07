from __future__ import annotations

import numpy as np
import pytest

from atomref_proatoms.validation.multiwfn_plane import (
    parse_multiwfn_point_density_log,
    plane_error_metrics,
    read_multiwfn_plane,
)
from atomref_proatoms.validation.wfn_density import ANGSTROM_TO_BOHR


def test_read_multiwfn_plane_four_column_format(tmp_path) -> None:
    path = tmp_path / "plane.txt"
    path.write_text("0.0 1.0 2.0 3.0\n4.0 5.0 6.0 7.0\n", encoding="utf-8")

    plane = read_multiwfn_plane(path)

    assert plane.n_points == 2
    assert plane.points_angstrom.tolist() == [[0.0, 1.0, 2.0], [4.0, 5.0, 6.0]]
    assert plane.points_bohr[0, 1] == pytest.approx(ANGSTROM_TO_BOHR)
    assert plane.values.tolist() == [3.0, 7.0]
    assert plane.plot_x_angstrom is None


def test_read_multiwfn_plane_six_column_format_and_metrics(tmp_path) -> None:
    path = tmp_path / "plane.txt"
    path.write_text("0 0 0 -1 -2 1.0\n1 0 0 3 4 1.5\n", encoding="utf-8")

    plane = read_multiwfn_plane(path)
    metrics = plane_error_metrics(plane.values, np.array([1.0, 1.0]), prefix="mw")

    assert plane.plot_x_angstrom is not None
    assert plane.plot_x_angstrom.tolist() == [-1.0, 3.0]
    assert plane.plot_y_angstrom.tolist() == [-2.0, 4.0]
    assert metrics["mw_max_abs_error"] == pytest.approx(0.5)
    assert metrics["mw_rmse"] == pytest.approx(np.sqrt(0.25 / 2.0))


def test_parse_multiwfn_point_density_log_accepts_plain_and_fortran_numbers(tmp_path) -> None:
    path = tmp_path / "point.log"
    path.write_text(
        """
 Density of all electrons: 1.250000D-02
 Density of Alpha electrons: 0.0075
 Density of Beta electrons: 5.0e-3
 Spin density of electrons: 2.500000E-03
""",
        encoding="utf-8",
    )

    parsed = parse_multiwfn_point_density_log(path)

    assert parsed["multiwfn_total_density"] == pytest.approx(0.0125)
    assert parsed["multiwfn_alpha_density"] == pytest.approx(0.0075)
    assert parsed["multiwfn_beta_density"] == pytest.approx(0.005)
    assert parsed["multiwfn_spin_density"] == pytest.approx(0.0025)
