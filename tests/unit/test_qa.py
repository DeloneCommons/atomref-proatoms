from __future__ import annotations

import pytest

from atomref_proatoms.qa import (
    electron_count_tolerance,
    max_relative_angular_sigma,
    qa_result_from_profile,
)


def test_electron_count_tolerance_uses_absolute_floor() -> None:
    assert electron_count_tolerance(1) == pytest.approx(2.0e-6)
    assert electron_count_tolerance(2000) == pytest.approx(4.0e-4)
    assert electron_count_tolerance(92) == pytest.approx(1.84e-5)


def test_max_relative_angular_sigma_ignores_tiny_density_tail() -> None:
    summary = max_relative_angular_sigma(
        [1.0, 0.5, 1.0e-12],
        [1.0e-10, 1.0e-9, 1.0],
        rho_floor=1.0e-8,
    )

    assert summary.n_points_used == 2
    assert summary.max_rel_angular_sigma == pytest.approx(2.0e-9)


def test_qa_result_from_profile_records_electron_and_angular_qa() -> None:
    result = qa_result_from_profile(
        scf_converged=True,
        electron_count_exact=1,
        derived={
            "r_iso_0.003_e_bohr3_bohr": 2.0,
            "r_iso_0.001_e_bohr3_bohr": 3.0,
            "r_iso_0.0001_e_bohr3_bohr": 4.0,
        },
        profile={
            "rho_e_bohr3": [1.0, 0.5],
            "rho_std_ang_e_bohr3": [1.0e-10, 1.0e-9],
            "nelec_integrated_qa": 1.00000001,
        },
    )

    assert result.scf_converged is True
    assert result.electron_count_error_qa == pytest.approx(1.0e-8)
    assert result.max_rel_angular_sigma == pytest.approx(2.0e-9)
    assert result.radii_monotonic is True
