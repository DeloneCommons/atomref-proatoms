from __future__ import annotations

import numpy as np
import pytest

from atomref_proatoms.exporters.proaim_wfn import (
    MOSPIN_ALPHA,
    MOSPIN_BETA,
    atom_wfn_filename,
    collect_unrestricted_spin_orbitals_from_arrays,
    format_mospin_lines,
    strict_atom_wfn_mospin_qa,
    write_proaim_wfn,
)
from atomref_proatoms.validation.wfn_density import parse_wfn_file


def test_atom_wfn_filename_uses_multiwfn_trailing_space_convention() -> None:
    assert atom_wfn_filename("H") == "H .wfn"
    assert atom_wfn_filename("O") == "O .wfn"
    assert atom_wfn_filename("Fe") == "Fe.wfn"


def test_format_mospin_lines_rejects_spatial_reconstruction_value() -> None:
    assert format_mospin_lines([MOSPIN_ALPHA, MOSPIN_BETA]) == ["$MOSPIN", " 1 2", "$END"]
    with pytest.raises(ValueError, match="only"):
        format_mospin_lines([MOSPIN_ALPHA, 3])


def test_write_proaim_wfn_spin_orbital_policy_with_pyscf(tmp_path) -> None:
    pytest.importorskip("pyscf")
    from pyscf import gto  # type: ignore[import-not-found]

    mol = gto.M(atom="H 0 0 0", basis="6-31g", spin=1, unit="Bohr", cart=False, verbose=0)
    coeff = np.eye(mol.nao_nr())[:, :2]
    occ = np.array([1.0, 0.5])
    energy = np.array([-0.5, -0.25])
    path = tmp_path / "H .wfn"

    info = write_proaim_wfn(
        path,
        mol,
        coeff,
        occ,
        energy,
        title="writer test",
        total_energy=-0.75,
        spin_types=[MOSPIN_ALPHA, MOSPIN_BETA],
    )
    qa = strict_atom_wfn_mospin_qa(path, expected_total=1.5, expected_alpha=1.0, expected_beta=0.5)
    wfn = parse_wfn_file(path)

    assert info["strict_atom_mospin_qa_ok"] is True
    assert info["mo_index_gap_written"] is True
    assert qa["strict_no_occupation_above_one"] is True
    assert wfn.spin_types.tolist() == [MOSPIN_ALPHA, MOSPIN_BETA]
    assert wfn.mo_indices.tolist() == [1, 3]


def test_write_proaim_wfn_rejects_spin_occupation_above_one(tmp_path) -> None:
    pytest.importorskip("pyscf")
    from pyscf import gto  # type: ignore[import-not-found]

    mol = gto.M(atom="H 0 0 0", basis="sto-3g", spin=1, unit="Bohr", cart=False, verbose=0)
    coeff = np.eye(mol.nao_nr())[:, :1]
    with pytest.raises(ValueError, match="occupations <= 1"):
        write_proaim_wfn(
            tmp_path / "bad.wfn",
            mol,
            coeff,
            np.array([2.0]),
            np.array([-0.5]),
            title="bad",
            spin_types=[MOSPIN_ALPHA],
        )


def test_collect_unrestricted_spin_orbitals_from_saved_arrays_alpha_then_beta() -> None:
    export = collect_unrestricted_spin_orbitals_from_arrays(
        mo_coeff_alpha=np.eye(3),
        mo_coeff_beta=np.eye(3),
        mo_occ_alpha=np.array([1.0, 0.5, 0.0]),
        mo_occ_beta=np.array([1.0, 0.0, 0.25]),
        mo_energy_alpha=np.array([-3.0, -2.0, -1.0]),
        mo_energy_beta=np.array([-2.5, -1.5, -0.5]),
        n_ao=3,
    )

    assert export.occupations.tolist() == [1.0, 0.5, 1.0, 0.25]
    assert export.energies.tolist() == [-3.0, -2.0, -2.5, -0.5]
    assert export.spin_types == [MOSPIN_ALPHA, MOSPIN_ALPHA, MOSPIN_BETA, MOSPIN_BETA]
    assert export.coefficients.shape == (3, 4)
