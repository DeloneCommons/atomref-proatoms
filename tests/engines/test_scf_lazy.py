from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from atomref_proatoms.dataio.basis import BasisBundle
from atomref_proatoms.engines.pyscf_backend import (
    SCF_REUSE_FINGERPRINT_KEYS,
    SCFSettings,
    import_pyscf_modules,
    load_scf_npz,
    scf_fingerprints,
    scf_state_record_digest,
)
from atomref_proatoms.engines.spherical_uks import get_atom_spherical_uks_class
from atomref_proatoms.states import AtomState


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


def test_scf_fingerprints_are_release_version_independent(tmp_path) -> None:
    bundle_dir = tmp_path / "basis"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text("{}")
    state = AtomState(
        {
            "state_id": "H_q0_mult2_nist",
            "symbol": "H",
            "z": 1,
            "charge": 0,
            "electron_count": 1,
        }
    )
    bundle = BasisBundle(
        basis_id="x2c-QZVPall",
        path=bundle_dir,
        manifest={"files": {"basis_file": "basis.nw", "basis_sha256": "basis-sha"}},
        summary_row={},
    )

    fingerprints = scf_fingerprints(
        config_path=tmp_path / "profile_datasets.yaml",
        config=SimpleNamespace(data={"profile_data_version": "1.0.0"}),
        state=state,
        bundle=bundle,
        settings=SCFSettings(),
    )

    for key in SCF_REUSE_FINGERPRINT_KEYS:
        assert key in fingerprints
    assert "profile_data_version" not in fingerprints
    assert "profile_datasets_yaml_sha256" not in fingerprints
    assert "profile_dataset_config_sha256" not in fingerprints


def test_scf_state_fingerprint_tracks_active_v2_state_definition() -> None:
    record = {
        "schema_version": "atomref.proatoms.state.v2",
        "state_id": "H_q0_mult2_nist",
        "symbol": "H",
        "z": 1,
        "charge": 0,
        "electron_count": 1,
        "occupation_policy": "spherical_l_counts_from_curated_multiplicity_v2",
    }
    changed_record = {**record, "multiplicity": 1}

    assert scf_state_record_digest(changed_record) != scf_state_record_digest(record)
