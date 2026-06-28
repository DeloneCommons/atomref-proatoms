from __future__ import annotations

import pytest
import numpy as np

from atomref_proatoms.scf import SCFSettings, load_scf_npz, import_pyscf_modules
from atomref_proatoms.spherical_uks import get_atom_spherical_uks_class


def test_scf_settings_defaults_are_production_defaults() -> None:
    settings = SCFSettings()
    assert settings.xc == "PBE0"
    assert settings.use_x2c is True
    assert settings.conv_tol == pytest.approx(1e-9)
    assert settings.max_cycle == 100


def test_pyscf_import_failure_has_clear_message_when_missing() -> None:
    pytest.importorskip("pyscf")
    _gto, _dft, _basis, version = import_pyscf_modules()
    assert version


def test_spherical_uks_class_factory_is_lazy() -> None:
    pytest.importorskip("pyscf")
    cls = get_atom_spherical_uks_class()
    assert cls.__name__ == "AtomSphAverageUKS"


def test_load_scf_npz_requires_project_native_arrays(tmp_path) -> None:
    path = tmp_path / "scf.npz"
    matrix = np.eye(2)
    vector = np.ones(2)
    np.savez_compressed(
        path,
        dm_alpha=matrix,
        dm_beta=matrix,
        mo_coeff_alpha=matrix,
        mo_coeff_beta=matrix,
        mo_occ_alpha=vector,
        mo_occ_beta=vector,
        mo_energy_alpha=vector,
        mo_energy_beta=vector,
    )

    arrays = load_scf_npz(path)

    assert arrays["dm_alpha"].shape == (2, 2)
    assert arrays["mo_occ_beta"].shape == (2,)
