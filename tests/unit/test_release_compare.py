from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

from atomref_proatoms.artifacts import profile_metadata_template, write_state_profile_artifacts
from atomref_proatoms.basis import list_basis_bundles
from atomref_proatoms.dataset_index import build_and_write_dataset_indexes
from atomref_proatoms.datasets import ANION_X2C_QZVPALL_S, PRIMARY_X2C_QZVPALL
from atomref_proatoms.profiles import derived_radii
from atomref_proatoms.release_compare import (
    compare_release_datasets,
    parse_dataset_pair,
    write_comparison_csv,
)
from atomref_proatoms.release_package import package_dataset_outputs
from atomref_proatoms.states import load_atom_states

ROOT = Path(__file__).resolve().parents[2]
STATES_FILE = ROOT / "data" / "states" / "curated" / "atom_states_v0.json"
BASIS_ROOT = ROOT / "data" / "basis_sets"


def _state_and_basis(state_id: str, basis_id: str):
    states = {state.state_id: state for state in load_atom_states(STATES_FILE)}
    bundles = {bundle.basis_id: bundle for bundle in list_basis_bundles(BASIS_ROOT)}
    return states[state_id], bundles[basis_id]


def _profile(scale: float) -> dict[str, list[float]]:
    r_bohr = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
    rho = [scale * value for value in [0.2, 0.02, 0.004, 0.0015, 0.0004, 0.00005]]
    return {
        "r_bohr": r_bohr,
        "rho_e_bohr3": rho,
        "rho_std_ang_e_bohr3": [0.0] * len(r_bohr),
        "nelec_cumulative_profile": [0.0, 0.1, 0.4, 0.7, 0.9, 0.99],
    }


def _write_one_state_dataset(
    output_dir: Path,
    *,
    dataset_id: str,
    state_id: str,
    basis_id: str,
    scale: float,
) -> Path:
    state, bundle = _state_and_basis(state_id, basis_id)
    profile = _profile(scale)
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
    build_and_write_dataset_indexes(dataset_dir, states_file=STATES_FILE, basis_root=BASIS_ROOT)
    return dataset_dir


def _two_release_archives(tmp_path: Path) -> tuple[Path, Path]:
    left_output = tmp_path / "left-build"
    right_output = tmp_path / "right-build"
    state_id = "F_qm1_mult1_hund"
    _write_one_state_dataset(
        left_output,
        dataset_id=PRIMARY_X2C_QZVPALL,
        state_id=state_id,
        basis_id="x2c-QZVPall",
        scale=1.0,
    )
    _write_one_state_dataset(
        right_output,
        dataset_id=ANION_X2C_QZVPALL_S,
        state_id=state_id,
        basis_id="x2c-QZVPall-s",
        scale=1.05,
    )
    left_archive = tmp_path / "left.zip"
    right_archive = tmp_path / "right.zip"
    package_dataset_outputs(left_output, left_archive, dataset_ids=(PRIMARY_X2C_QZVPALL,))
    package_dataset_outputs(right_output, right_archive, dataset_ids=(ANION_X2C_QZVPALL_S,))
    return left_archive, right_archive


def test_parse_dataset_pair() -> None:
    assert parse_dataset_pair("a:b") == ("a", "b")


def test_compare_release_datasets_common_state(tmp_path: Path) -> None:
    left_archive, right_archive = _two_release_archives(tmp_path)

    result = compare_release_datasets(
        (left_archive, right_archive),
        pairs=((PRIMARY_X2C_QZVPALL, ANION_X2C_QZVPALL_S),),
    )

    assert result.ok
    assert len(result.comparisons) == 1
    comparison = result.comparisons[0]
    assert comparison.common_state_ids == ("F_qm1_mult1_hund",)
    assert comparison.rows
    assert {row["radius_column"] for row in comparison.rows} == {
        "r_iso_0.003_e_bohr3_bohr",
        "r_iso_0.001_e_bohr3_bohr",
        "r_iso_0.0001_e_bohr3_bohr",
    }
    assert all(row["right_basis_id"] == "x2c-QZVPall-s" for row in comparison.rows)
    assert all(item.compared_count == 1 for item in comparison.summaries)


def test_write_comparison_csv(tmp_path: Path) -> None:
    left_archive, right_archive = _two_release_archives(tmp_path)
    result = compare_release_datasets((left_archive, right_archive))
    output_csv = tmp_path / "comparison.csv"

    row_count = write_comparison_csv(result.comparisons, output_csv)

    assert row_count == 3
    with output_csv.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["state_id"] == "F_qm1_mult1_hund"
    assert rows[0]["left_dataset_id"] == PRIMARY_X2C_QZVPALL
    assert rows[0]["right_dataset_id"] == ANION_X2C_QZVPALL_S


def test_compare_release_packages_cli(tmp_path: Path) -> None:
    left_archive, right_archive = _two_release_archives(tmp_path)
    output_csv = tmp_path / "comparison.csv"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/compare_release_packages.py",
            "--archive",
            str(left_archive),
            "--archive",
            str(right_archive),
            "--pair",
            f"{PRIMARY_X2C_QZVPALL}:{ANION_X2C_QZVPALL_S}",
            "--csv",
            str(output_csv),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Status: OK" in result.stdout
    assert "common=1" in result.stdout
    assert "CSV rows written: 3" in result.stdout
    assert output_csv.is_file()


def test_compare_release_datasets_detects_duplicate_dataset_id(tmp_path: Path) -> None:
    output = tmp_path / "build"
    _write_one_state_dataset(
        output,
        dataset_id=PRIMARY_X2C_QZVPALL,
        state_id="H_q0_mult2_hund",
        basis_id="x2c-QZVPall",
        scale=1.0,
    )
    archive_a = tmp_path / "a.zip"
    archive_b = tmp_path / "b.zip"
    package_dataset_outputs(output, archive_a, dataset_ids=(PRIMARY_X2C_QZVPALL,))
    package_dataset_outputs(output, archive_b, dataset_ids=(PRIMARY_X2C_QZVPALL,))

    result = compare_release_datasets((archive_a, archive_b))

    assert not result.ok
    assert any("duplicate dataset_id" in error for error in result.errors)
