from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from atomref_proatoms.artifacts import profile_metadata_template, write_state_profile_artifacts
from atomref_proatoms.basis import list_basis_bundles
from atomref_proatoms.dataset_index import (
    build_and_write_dataset_indexes,
    check_dataset_indexes,
)
from atomref_proatoms.dataset_summary import format_dataset_summary, summarize_dataset_indexes
from atomref_proatoms.datasets import PRIMARY_X2C_QZVPALL
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


def _write_h_dataset(tmp_path: Path) -> Path:
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
            "electron_count_error_qa": 1.0e-9,
            "max_rel_angular_sigma": 1.0e-10,
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


def test_build_and_check_dataset_indexes(tmp_path: Path) -> None:
    dataset_dir = _write_h_dataset(tmp_path)

    tables = build_and_write_dataset_indexes(
        dataset_dir,
        states_file=STATES_FILE,
        basis_root=BASIS_ROOT,
    )

    assert tables.dataset_id == PRIMARY_X2C_QZVPALL
    assert tables.profile_count == 1
    manifest = json.loads((dataset_dir / "dataset_manifest.json").read_text())
    assert manifest["profile_count"] == 1
    assert manifest["qa_summary"]["electron_count_qa_count"] == 1

    with (dataset_dir / "profile_index.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["state_id"] == "H_q0_mult2_hund"
    assert rows[0]["profile_archive"] == "profiles/H_q0_mult2_hund.csv.zip"
    assert rows[0]["state_category"] == "nist_ground_state"
    assert rows[0]["spin_model"] == "free_ion_hund_high_spin"
    assert rows[0]["electron_count_error_qa"] == "1e-09"

    result = check_dataset_indexes(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)
    assert result.ok


def test_check_dataset_indexes_detects_stale_profile_index(tmp_path: Path) -> None:
    dataset_dir = _write_h_dataset(tmp_path)
    build_and_write_dataset_indexes(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)
    profile_index_path = dataset_dir / "profile_index.csv"
    profile_index_path.write_text(profile_index_path.read_text().replace("H_q0", "X_q0"))

    result = check_dataset_indexes(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)

    assert not result.ok
    assert any("profile_index.csv" in error for error in result.errors)


def test_build_dataset_index_cli_and_check_dataset_cli(tmp_path: Path) -> None:
    dataset_dir = _write_h_dataset(tmp_path)

    build = subprocess.run(
        [
            sys.executable,
            "scripts/build_dataset_index.py",
            "--dataset-dir",
            str(dataset_dir),
            "--require-profile-qa",
            "--summary",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "OK: wrote dataset indexes for 1 profile(s)" in build.stdout
    assert "State categories: nist_ground_state=1" in build.stdout

    check = subprocess.run(
        [
            sys.executable,
            "scripts/check_dataset.py",
            "--dataset-dir",
            str(dataset_dir),
            "--require-profile-qa",
            "--summary",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "OK: checked dataset" in check.stdout
    assert "State categories: nist_ground_state=1" in check.stdout


def test_dataset_summary_from_indexes(tmp_path: Path) -> None:
    dataset_dir = _write_h_dataset(tmp_path)
    build_and_write_dataset_indexes(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)

    summary = summarize_dataset_indexes(dataset_dir)
    report = format_dataset_summary(summary)

    assert summary.dataset_id == PRIMARY_X2C_QZVPALL
    assert summary.profile_count == 1
    assert summary.symbols == ("H",)
    assert summary.charge_counts == (("0", 1),)
    assert summary.state_category_counts == (("nist_ground_state", 1),)
    assert summary.electron_count_qa_count == 1
    assert "Dataset:" in report
    assert "State categories: nist_ground_state=1" in report
    assert "Max |electron-count error|: 1e-09" in report


def test_summarize_dataset_cli(tmp_path: Path) -> None:
    dataset_dir = _write_h_dataset(tmp_path)
    build_and_write_dataset_indexes(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/summarize_dataset.py",
            "--dataset-dir",
            str(dataset_dir),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Dataset:" in result.stdout
    assert "Profiles: 1" in result.stdout
