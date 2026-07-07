from __future__ import annotations

import numpy as np
import pytest

from atomref_proatoms.exporters.multiwfn_rad import (
    MULTIWFN_ATMRAD_GRID_BOHR,
    interpolate_density_to_rad_grid,
    multiwfn_rad_filename,
    radial_density_integral,
    read_multiwfn_rad_file,
    write_multiwfn_rad_file,
    write_profile_state_rad,
)


def test_multiwfn_atmrad_grid_matches_exemplar_shape() -> None:
    assert len(MULTIWFN_ATMRAD_GRID_BOHR) == 176
    assert MULTIWFN_ATMRAD_GRID_BOHR[0] == pytest.approx(0.000061075260)
    assert MULTIWFN_ATMRAD_GRID_BOHR[66] == pytest.approx(1.0 / 3.0)
    assert MULTIWFN_ATMRAD_GRID_BOHR[-1] == pytest.approx(25.534147230985)
    assert np.all(np.diff(MULTIWFN_ATMRAD_GRID_BOHR) > 0)


def test_multiwfn_rad_filename_charge_convention() -> None:
    assert multiwfn_rad_filename("H", 0) == "H_0.rad"
    assert multiwfn_rad_filename("O", -1) == "O-1.rad"
    assert multiwfn_rad_filename("Fe", 2) == "Fe+2.rad"


def test_write_and_read_multiwfn_rad_file(tmp_path) -> None:
    path = tmp_path / "H_0.rad"
    r = np.array([0.1, 0.2, 0.4])
    rho = np.array([1.0, 0.5, 0.125])

    info = write_multiwfn_rad_file(path, r, rho)
    parsed = read_multiwfn_rad_file(path)

    assert path.read_text(encoding="ascii").splitlines()[0] == "           3"
    assert info["n_points"] == 3
    assert parsed.r_bohr.tolist() == pytest.approx(r.tolist())
    assert parsed.rho_e_bohr3.tolist() == pytest.approx(rho.tolist())
    assert info["integral_electrons_trapezoid"] == pytest.approx(radial_density_integral(r, rho))


def test_log_density_interpolation_to_rad_grid() -> None:
    source_r = np.array([1.0e-6, 0.1, 1.0, 60.0])
    source_rho = 4.0 * np.exp(-source_r)
    target_r = np.array([0.1, 1.0])

    out = interpolate_density_to_rad_grid(source_r, source_rho, target_r_bohr=target_r)

    assert out.tolist() == pytest.approx((4.0 * np.exp(-target_r)).tolist())


def test_write_profile_state_rad_uses_fixed_grid(tmp_path) -> None:
    source_r = np.geomspace(1.0e-6, 60.0, 400)
    source_rho = np.exp(-source_r)

    info = write_profile_state_rad(
        tmp_path / "H_0.rad",
        profile_r_bohr=source_r,
        profile_rho_e_bohr3=source_rho,
    )
    parsed = read_multiwfn_rad_file(tmp_path / "H_0.rad")

    assert parsed.n_points == len(MULTIWFN_ATMRAD_GRID_BOHR)
    assert info["source"] == "profile_interpolation"
    assert info["source_profile_tail_beyond_rad_grid_electrons_trapezoid"] >= 0.0


def test_write_profile_state_rad_reports_source_tail_without_origin_endpoint(tmp_path) -> None:
    source_r = np.array([0.5, 1.0, 2.0, 3.0])
    source_rho = np.ones_like(source_r)
    rad_grid = np.array([1.0, 2.0])

    info = write_profile_state_rad(
        tmp_path / "H_0.rad",
        profile_r_bohr=source_r,
        profile_rho_e_bohr3=source_rho,
        rad_grid_bohr=rad_grid,
    )

    expected_tail = float(np.trapezoid(4.0 * np.pi * source_r[2:] ** 2, source_r[2:]))
    assert info["source_profile_tail_beyond_rad_grid_electrons_trapezoid"] == pytest.approx(
        expected_tail
    )
