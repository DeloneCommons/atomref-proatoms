from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

from atomref_proatoms.artifacts import profile_metadata_template, write_state_profile_artifacts
from atomref_proatoms.basis import list_basis_bundles
from atomref_proatoms.dataset_index import build_and_write_dataset_indexes
from atomref_proatoms.datasets import PRIMARY_X2C_QZVPALL
from atomref_proatoms.profiles import derived_radii
from atomref_proatoms.release_package import (
    RELEASE_MANIFEST_NAME,
    check_release_package,
    default_release_archive_path,
    package_dataset_outputs,
)
from atomref_proatoms.states import load_atom_states

ROOT = Path(__file__).resolve().parents[2]
STATES_FILE = ROOT / "data" / "states" / "curated" / "atom_states_v0.json"
BASIS_ROOT = ROOT / "data" / "basis_sets"


def _write_indexed_h_dataset(output_dir: Path) -> Path:
    states = {state.state_id: state for state in load_atom_states(STATES_FILE)}
    bundles = {bundle.basis_id: bundle for bundle in list_basis_bundles(BASIS_ROOT)}
    state = states["H_q0_mult2_hund"]
    bundle = bundles["x2c-QZVPall"]
    profile = {
        "r_bohr": [0.5, 1.0, 2.0, 3.0, 4.0, 5.0],
        "rho_e_bohr3": [0.2, 0.02, 0.004, 0.0015, 0.0004, 0.00005],
        "rho_std_ang_e_bohr3": [0.0] * 6,
        "nelec_cumulative_profile": [0.0, 0.1, 0.4, 0.7, 0.9, 0.99],
    }
    metadata = profile_metadata_template(
        dataset_id=PRIMARY_X2C_QZVPALL,
        state=state,
        basis_id=bundle.basis_id,
        basis_sha256=bundle.basis_sha256,
        engine_version="test",
        derived=derived_radii(profile["r_bohr"], profile["rho_e_bohr3"]),
        qa={
            "scf_converged": True,
            "electron_count_error_qa": 1.0e-9,
            "max_rel_angular_sigma": 1.0e-10,
            "linear_dependency_vectors_removed": None,
            "tail_reaches_min_cutoff": True,
            "radii_monotonic": True,
        },
    )
    dataset_dir = output_dir / PRIMARY_X2C_QZVPALL
    write_state_profile_artifacts(
        dataset_dir, state_id=state.state_id, profile=profile, metadata=metadata
    )
    build_and_write_dataset_indexes(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)
    return dataset_dir


def test_default_release_archive_path_labels_all_or_selected(tmp_path: Path) -> None:
    output_dir = tmp_path / "profile-builds"

    assert default_release_archive_path(output_dir).name == "profile-builds-all_v0-release.zip"
    assert (
        default_release_archive_path(output_dir, (PRIMARY_X2C_QZVPALL,)).name
        == "profile-builds-selected-release.zip"
    )


def test_package_and_check_dataset_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "profile-builds"
    _write_indexed_h_dataset(output_dir)
    archive = tmp_path / "release.zip"

    result = package_dataset_outputs(
        output_dir,
        archive,
        dataset_ids=(PRIMARY_X2C_QZVPALL,),
    )

    assert result.file_count == 5
    assert result.dataset_ids == (PRIMARY_X2C_QZVPALL,)
    check = check_release_package(archive, expected_dataset_ids=(PRIMARY_X2C_QZVPALL,))
    assert check.ok
    assert check.file_count == 5

    with ZipFile(archive) as zip_handle:
        names = set(zip_handle.namelist())
        manifest = json.loads(zip_handle.read(RELEASE_MANIFEST_NAME).decode("utf-8"))
    assert RELEASE_MANIFEST_NAME in names
    assert f"data/profiles/{PRIMARY_X2C_QZVPALL}/dataset_manifest.json" in names
    assert manifest["dataset_ids"] == [PRIMARY_X2C_QZVPALL]


def test_check_release_package_detects_hash_mismatch(tmp_path: Path) -> None:
    output_dir = tmp_path / "profile-builds"
    _write_indexed_h_dataset(output_dir)
    archive = tmp_path / "release.zip"
    package_dataset_outputs(output_dir, archive, dataset_ids=(PRIMARY_X2C_QZVPALL,))

    broken = tmp_path / "broken.zip"
    with ZipFile(archive) as source, ZipFile(broken, "w") as target:
        for name in source.namelist():
            payload = source.read(name)
            if name.endswith("profile_index.csv"):
                payload += b"#tamper\n"
            target.writestr(name, payload)

    result = check_release_package(broken, expected_dataset_ids=(PRIMARY_X2C_QZVPALL,))

    assert not result.ok
    assert any("sha256 mismatch" in error for error in result.errors)


def test_package_dataset_outputs_cli_and_check_release_cli(tmp_path: Path) -> None:
    output_dir = tmp_path / "profile-builds"
    _write_indexed_h_dataset(output_dir)
    archive = tmp_path / "release.zip"

    package = subprocess.run(
        [
            sys.executable,
            "scripts/package_dataset_outputs.py",
            "--output-dir",
            str(output_dir),
            "--dataset-id",
            PRIMARY_X2C_QZVPALL,
            "--archive",
            str(archive),
            "--check-datasets",
            "--require-profile-qa",
            "--check-archive",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Files packaged: 5" in package.stdout
    assert "Status: OK" in package.stdout

    check = subprocess.run(
        [
            sys.executable,
            "scripts/check_release_package.py",
            "--archive",
            str(archive),
            "--dataset-id",
            PRIMARY_X2C_QZVPALL,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Status: OK" in check.stdout
