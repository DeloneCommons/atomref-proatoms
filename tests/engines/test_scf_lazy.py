from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from atomref_proatoms.dataio.basis import BasisBundle
from atomref_proatoms.engines.pyscf_backend import (
    SCF_ARTIFACT_SCHEMA_VERSION,
    SCF_REUSE_FINGERPRINT_KEYS,
    SCFSettings,
    import_pyscf_modules,
    load_scf_npz,
    scf_artifact_is_reusable,
    scf_artifact_paths,
    scf_artifacts_complete,
    scf_fingerprints,
    scf_settings_reuse_digest,
    scf_state_record_digest,
    stable_json_digest,
)
from atomref_proatoms.engines.spherical_uks import get_atom_spherical_uks_class
from atomref_proatoms.states import AtomState


def test_scf_settings_defaults_are_production_defaults() -> None:
    settings = SCFSettings()
    assert settings.xc == "PBE0"
    assert settings.use_x2c is True
    assert settings.conv_tol == pytest.approx(1e-9)
    assert settings.max_cycle == 300
    assert settings.diis_space == 12
    assert settings.diis_start_cycle == 1


def test_scf_reuse_fingerprint_excludes_max_cycle() -> None:
    base = SCFSettings(max_cycle=100)
    longer = SCFSettings(max_cycle=300)

    assert base.to_fingerprint_json() != longer.to_fingerprint_json()
    assert base.to_reuse_fingerprint_json() == longer.to_reuse_fingerprint_json()

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


def test_scf_artifact_reuse_accepts_legacy_max_cycle_digest(tmp_path) -> None:
    paths = scf_artifact_paths(tmp_path, "dataset", "state")
    paths.state_dir.mkdir(parents=True)
    current = {key: f"expected-{key}" for key in SCF_REUSE_FINGERPRINT_KEYS}
    current["scf_settings_sha256"] = scf_settings_reuse_digest(
        SCFSettings(max_cycle=300).to_fingerprint_json()
    )
    legacy = stable_json_digest(SCFSettings(max_cycle=100).to_fingerprint_json())

    for path in paths.required_files():
        path.write_text("x", encoding="utf-8")
    metadata = {
        "schema_version": SCF_ARTIFACT_SCHEMA_VERSION,
        "dataset_id": "dataset",
        "state_id": "state",
        "settings": SCFSettings(max_cycle=100).to_fingerprint_json(),
        "results": {"converged": True},
        "fingerprints": {**current, "scf_settings_sha256": legacy},
    }
    paths.metadata.write_text(json.dumps(metadata), encoding="utf-8")

    assert scf_artifact_is_reusable(paths, current)


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


def test_scf_artifact_reuse_requires_complete_nonempty_files_and_convergence(tmp_path) -> None:
    paths = scf_artifact_paths(tmp_path, "dataset", "state")
    paths.state_dir.mkdir(parents=True)
    expected = {key: f"expected-{key}" for key in SCF_REUSE_FINGERPRINT_KEYS}

    for path in paths.required_files():
        path.write_text("x", encoding="utf-8")
    metadata = {
        "schema_version": SCF_ARTIFACT_SCHEMA_VERSION,
        "dataset_id": "dataset",
        "state_id": "state",
        "results": {"converged": True},
        "fingerprints": dict(expected),
    }
    paths.metadata.write_text(json.dumps(metadata), encoding="utf-8")

    assert scf_artifacts_complete(paths)
    assert scf_artifact_is_reusable(paths, expected)

    metadata["results"]["converged"] = False
    paths.metadata.write_text(json.dumps(metadata), encoding="utf-8")
    assert not scf_artifact_is_reusable(paths, expected)

    paths.npz.write_text("", encoding="utf-8")
    assert not scf_artifacts_complete(paths)
