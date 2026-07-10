from __future__ import annotations

import numpy as np
import pytest

from atomref_proatoms.exporters.multiwfn_rad import (
    MULTIWFN_ATMRAD_GRID_BOHR,
    evaluate_scf_radial_density,
    multiwfn_rad_filename,
    radial_density_integral,
    read_multiwfn_rad_file,
    write_multiwfn_rad_file,
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


def test_radial_density_integral_includes_origin_endpoint() -> None:
    r = np.array([1.0, 2.0])
    rho = np.ones_like(r)

    observed = radial_density_integral(r, rho)
    expected = float(
        np.trapezoid(4.0 * np.pi * np.array([0.0, 1.0, 2.0]) ** 2, [0.0, 1.0, 2.0])
    )

    assert observed == pytest.approx(expected)


def test_evaluate_scf_radial_density_validates_inputs_before_pyscf_import() -> None:
    with pytest.raises(ValueError, match="square"):
        evaluate_scf_radial_density(object(), np.ones((2, 3)), r_bohr=np.array([0.1]))
    with pytest.raises(ValueError, match="n_ang"):
        evaluate_scf_radial_density(object(), np.eye(2), r_bohr=np.array([0.1]), n_ang=0)
    with pytest.raises(ValueError, match="1 or at least 4"):
        evaluate_scf_radial_density(object(), np.eye(2), r_bohr=np.array([0.1]), n_ang=3)
    with pytest.raises(ValueError, match="coord_block_size"):
        evaluate_scf_radial_density(
            object(),
            np.eye(2),
            r_bohr=np.array([0.1]),
            coord_block_size=0,
        )
