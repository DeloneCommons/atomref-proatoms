from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from atomref_proatoms.artifacts import profile_metadata_template, write_state_profile_artifacts
from atomref_proatoms.basis import list_basis_bundles
from atomref_proatoms.dataset_index import build_and_write_dataset_indexes
from atomref_proatoms.datasets import ANION_X2C_QZVPALL_S, PRIMARY_X2C_QZVPALL
from atomref_proatoms.pilot_outputs import (
    check_pilot_output_root,
    expected_state_ids_by_dataset,
    format_pilot_output_check,
)
from atomref_proatoms.pilots import ANION_FORMAL_X2C_DIFFUSE, H_SMOKE, NEUTRAL_LIGHT_X2C
from atomref_proatoms.profiles import derived_radii
from atomref_proatoms.states import AtomState, load_atom_states

ROOT = Path(__file__).resolve().parents[2]
STATES_FILE = ROOT / "data" / "states" / "curated" / "atom_states_v0.json"
BASIS_ROOT = ROOT / "data" / "basis_sets"


def _states_by_id() -> dict[str, AtomState]:
    return {state.state_id: state for state in load_atom_states(STATES_FILE)}


def _basis_by_id():
    return {bundle.basis_id: bundle for bundle in list_basis_bundles(BASIS_ROOT)}


def _sample_profile() -> dict[str, list[float]]:
    r_bohr = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
    rho_e_bohr3 = [0.2, 0.02, 0.004, 0.0015, 0.0004, 0.00005]
    return {
        "r_bohr": r_bohr,
        "rho_e_bohr3": rho_e_bohr3,
        "rho_std_ang_e_bohr3": [0.0] * len(r_bohr),
        "nelec_cumulative_profile": [0.0, 0.1, 0.4, 0.7, 0.9, 0.99],
    }


def _write_artifact(
    output_dir: Path,
    *,
    state_id: str,
    dataset_id: str,
    basis_id: str,
) -> Path:
    state = _states_by_id()[state_id]
    bundle = _basis_by_id()[basis_id]
    profile = _sample_profile()
    metadata = profile_metadata_template(
        dataset_id=dataset_id,
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
    dataset_dir = output_dir / dataset_id
    write_state_profile_artifacts(
        dataset_dir,
        state_id=state.state_id,
        profile=profile,
        metadata=metadata,
    )
    return dataset_dir


def test_expected_state_ids_by_dataset_keeps_sensitivity_dataset_separate() -> None:
    expected = expected_state_ids_by_dataset((ANION_FORMAL_X2C_DIFFUSE,))

    assert expected == {
        ANION_X2C_QZVPALL_S: (
            "I_qm1_mult1_hund",
            "O_qm2_mult1_hund",
            "S_qm2_mult1_hund",
        )
    }


def test_check_pilot_output_root_accepts_complete_anion_group(tmp_path: Path) -> None:
    for state_id in ("I_qm1_mult1_hund", "O_qm2_mult1_hund", "S_qm2_mult1_hund"):
        dataset_dir = _write_artifact(
            tmp_path,
            state_id=state_id,
            dataset_id=ANION_X2C_QZVPALL_S,
            basis_id="x2c-QZVPall-s",
        )
    build_and_write_dataset_indexes(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)

    result = check_pilot_output_root(
        tmp_path,
        group_names=(ANION_FORMAL_X2C_DIFFUSE,),
        states_file=STATES_FILE,
        basis_root=BASIS_ROOT,
        require_profile_qa=True,
        include_summaries=True,
    )

    assert result.ok
    assert result.checked_dataset_ids == (ANION_X2C_QZVPALL_S,)
    assert result.summaries
    assert "formal_crystal_ion_reference=2" in result.summaries[0]


def test_check_pilot_output_root_rejects_incomplete_selected_group(tmp_path: Path) -> None:
    dataset_dir = _write_artifact(
        tmp_path,
        state_id="H_q0_mult2_hund",
        dataset_id=PRIMARY_X2C_QZVPALL,
        basis_id="x2c-QZVPall",
    )
    build_and_write_dataset_indexes(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)

    result = check_pilot_output_root(
        tmp_path,
        group_names=(NEUTRAL_LIGHT_X2C,),
        states_file=STATES_FILE,
        basis_root=BASIS_ROOT,
        require_profile_qa=True,
    )

    assert not result.ok
    assert any("missing expected pilot states" in error for error in result.errors)


def test_check_pilot_output_root_h_smoke_cli(tmp_path: Path) -> None:
    dataset_dir = _write_artifact(
        tmp_path,
        state_id="H_q0_mult2_hund",
        dataset_id=PRIMARY_X2C_QZVPALL,
        basis_id="x2c-QZVPall",
    )
    build_and_write_dataset_indexes(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_pilot_outputs.py",
            "--output-dir",
            str(tmp_path),
            "--group",
            H_SMOKE,
            "--require-profile-qa",
            "--summary",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Status: OK" in result.stdout
    assert "Expected pilot states" in result.stdout
    assert "Dataset summaries" in result.stdout


def test_format_pilot_output_check_reports_errors(tmp_path: Path) -> None:
    result = check_pilot_output_root(
        tmp_path,
        group_names=(H_SMOKE,),
        states_file=STATES_FILE,
        basis_root=BASIS_ROOT,
    )

    report = format_pilot_output_check(result)

    assert not result.ok
    assert "missing dataset directory" in report
    assert "Status: FAILED" in report
