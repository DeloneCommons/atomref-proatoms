from __future__ import annotations

import json
from pathlib import Path

from atomref_proatoms.artifacts import profile_metadata_template, write_state_profile_artifacts
from atomref_proatoms.basis import list_basis_bundles
from atomref_proatoms.datasets import PRIMARY_X2C_QZVPALL
from atomref_proatoms.profile_checks import check_profile_dataset, read_profile_table
from atomref_proatoms.profiles import derived_radii
from atomref_proatoms.states import load_atom_states

ROOT = Path(__file__).resolve().parents[2]
STATES_FILE = ROOT / "data" / "states" / "curated" / "atom_states_v0.json"
BASIS_ROOT = ROOT / "data" / "basis_sets"


def _h_state_and_basis():
    states = {state.state_id: state for state in load_atom_states(STATES_FILE)}
    bundles = {bundle.basis_id: bundle for bundle in list_basis_bundles(BASIS_ROOT)}
    return states["H_q0_mult2_hund"], bundles["x2c-QZVPall"]


def _sample_profile() -> dict[str, list[float]]:
    r_bohr = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
    rho_e_bohr3 = [0.2, 0.02, 0.004, 0.0015, 0.0004, 0.00005]
    return {
        "r_bohr": r_bohr,
        "rho_e_bohr3": rho_e_bohr3,
        "rho_std_ang_e_bohr3": [0.0] * len(r_bohr),
        "nelec_cumulative_profile": [0.0, 0.1, 0.4, 0.7, 0.9, 0.99],
    }


def _write_valid_h_artifact(tmp_path: Path, *, electron_count_error_qa: float | None = None) -> Path:
    state, bundle = _h_state_and_basis()
    profile = _sample_profile()
    metadata = profile_metadata_template(
        dataset_id=PRIMARY_X2C_QZVPALL,
        state=state,
        basis_id=bundle.basis_id,
        basis_sha256=bundle.basis_sha256,
        engine_version="test",
        derived=derived_radii(profile["r_bohr"], profile["rho_e_bohr3"]),
        qa={
            "scf_converged": True,
            "electron_count_error_qa": electron_count_error_qa,
            "max_rel_angular_sigma": None,
            "linear_dependency_vectors_removed": None,
            "tail_reaches_min_cutoff": True,
            "radii_monotonic": True,
        },
    )
    dataset_dir = tmp_path / PRIMARY_X2C_QZVPALL
    write_state_profile_artifacts(
        dataset_dir,
        state_id=state.state_id,
        profile=profile,
        metadata=metadata,
    )
    return dataset_dir


def test_check_profile_dataset_accepts_zip_artifact_with_skipped_qa(tmp_path) -> None:
    dataset_dir = _write_valid_h_artifact(tmp_path)

    result = check_profile_dataset(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)

    assert result.ok
    assert result.checked_profiles == 1
    assert any("independent QA electron count was skipped" in item for item in result.warnings)
    archive = dataset_dir / "profiles" / "H_q0_mult2_hund.csv.zip"
    table = read_profile_table(archive)
    assert table.inner_csv_name == "H_q0_mult2_hund.csv"
    assert table.row_count == 6


def test_check_profile_dataset_can_require_profile_qa(tmp_path) -> None:
    dataset_dir = _write_valid_h_artifact(tmp_path)

    result = check_profile_dataset(
        dataset_dir,
        states_file=STATES_FILE,
        basis_root=BASIS_ROOT,
        require_profile_qa=True,
    )

    assert not result.ok
    assert any("independent QA electron count was skipped" in item for item in result.errors)


def test_check_profile_dataset_rejects_non_strict_json_nan(tmp_path) -> None:
    dataset_dir = _write_valid_h_artifact(tmp_path)
    metadata_path = dataset_dir / "metadata" / "H_q0_mult2_hund.json"
    text = metadata_path.read_text()
    text = text.replace('"electron_count_error_qa": null', '"electron_count_error_qa": NaN')
    metadata_path.write_text(text)

    result = check_profile_dataset(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)

    assert not result.ok
    assert any("non-standard JSON constant" in item for item in result.errors)


def test_check_profile_dataset_rejects_profile_metadata_radius_mismatch(tmp_path) -> None:
    dataset_dir = _write_valid_h_artifact(tmp_path)
    metadata_path = dataset_dir / "metadata" / "H_q0_mult2_hund.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["derived"]["r_iso_0.001_e_bohr3_bohr"] += 1.0
    metadata_path.write_text(json.dumps(metadata))

    result = check_profile_dataset(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)

    assert not result.ok
    assert any("does not match profile-derived" in item for item in result.errors)
