from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from atomref_proatoms.dataio.paths import STATES_FILE
from atomref_proatoms.profiles.artifact_check import check_generated_artifacts
from atomref_proatoms.states.state_tables import load_atom_states

ROOT = Path(__file__).resolve().parents[2]
DATASET_ID = "test_dataset"
BASIS_ID = "test-basis"


def _h_state_record() -> dict[str, object]:
    for state in load_atom_states(STATES_FILE):
        if state.state_id == "H_q0_mult2_nist":
            return dict(state.record)
    raise AssertionError("H state not found")


def _write_config(path: Path) -> None:
    path.write_text(
        """
schema_version: atomref.proatoms.profile_datasets.v1
profile_data_version: 2.0.0

defaults:
  density_model: self_consistent_fractional_occupation_spherical_uks
  engine: pyscf
  expected_engine_version: 2.13.1
  scf_type: UKS
  xc: PBE0
  relativity: sf-X2C-1e
  spherical_basis: true
  conv_tol: 1.0e-9
  max_cycle: 100
  grid_level: 4

profile_grid:
  type: log
  r_min_bohr: 1.0e-6
  r_max_bohr: 60.0
  n: 2

qa_grid:
  type: gauss_legendre_log_r
  r_min_bohr: 1.0e-7
  r_max_bohr: 120.0
  n: 4
  angular_points: 8

cutoffs_e_bohr3: [0.003, 0.001]

datasets:
  - dataset_id: test_dataset
    role: test
    basis_id: test-basis
    coverage_label: H test state
    z_intervals: [[1, 1]]
    include_charges: neutral_only
    include_state_roles: [reference]
    diffuse: false
""".lstrip(),
        encoding="utf-8",
    )


def _write_states(path: Path) -> None:
    path.write_text(json.dumps([_h_state_record()], indent=2) + "\n", encoding="utf-8")


def _write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_valid_artifacts(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    config = tmp_path / "profile_datasets.yaml"
    states = tmp_path / "states.json"
    profiles_root = tmp_path / "profiles"
    radii_root = tmp_path / "radii"
    qa_root = tmp_path / "qa"
    _write_config(config)
    _write_states(states)

    for root in (profiles_root, radii_root, qa_root):
        root.mkdir()
        (root / "README.md").write_text("placeholder\n", encoding="utf-8")

    profile_dir = profiles_root / DATASET_ID
    profile_dir.mkdir()
    _write_rows(
        profile_dir / "profiles.csv",
        ["r_bohr", "rho_e_bohr3__H_q0_mult2_nist"],
        [
            {"r_bohr": 0.1, "rho_e_bohr3__H_q0_mult2_nist": 1.0},
            {"r_bohr": 0.2, "rho_e_bohr3__H_q0_mult2_nist": 0.5},
        ],
    )
    profile_metadata = {
        "schema_version": "atomref.proatoms.profile_dataset.v1",
        "profile_data_version": "2.0.0",
        "dataset_id": DATASET_ID,
        "basis_id": BASIS_ID,
        "density_model": "self_consistent_fractional_occupation_spherical_uks",
        "columns": {"rho_e_bohr3__H_q0_mult2_nist": {"state_id": "H_q0_mult2_nist"}},
        "states": {"H_q0_mult2_nist": {"symbol": "H"}},
        "related_artifacts": {
            "profiles_csv": str(profile_dir / "profiles.csv"),
            "profile_metadata_json": str(profile_dir / "metadata.json"),
            "radii_csv": str(radii_root / DATASET_ID / "radii.csv"),
            "radii_metadata_json": str(radii_root / DATASET_ID / "metadata.json"),
            "qa_csv": str(qa_root / DATASET_ID / "qa.csv"),
            "qa_metadata_json": str(qa_root / DATASET_ID / "metadata.json"),
        },
    }
    (profile_dir / "metadata.json").write_text(
        json.dumps(profile_metadata, indent=2) + "\n", encoding="utf-8"
    )

    radii_dir = radii_root / DATASET_ID
    radii_dir.mkdir()
    _write_rows(
        radii_dir / "radii.csv",
        ["state_id", "r_iso_0.003_e_bohr3_bohr", "r_iso_0.001_e_bohr3_bohr"],
        [
            {
                "state_id": "H_q0_mult2_nist",
                "r_iso_0.003_e_bohr3_bohr": 1.0,
                "r_iso_0.001_e_bohr3_bohr": 2.0,
            }
        ],
    )
    (radii_dir / "metadata.json").write_text(
        json.dumps(
            {
                "schema_version": "atomref.proatoms.radii_dataset.v1",
                "profile_data_version": "2.0.0",
                "dataset_id": DATASET_ID,
                "basis_id": BASIS_ID,
                "row_count": 1,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    qa_dir = qa_root / DATASET_ID
    qa_dir.mkdir()
    _write_rows(
        qa_dir / "qa.csv",
        ["state_id", "overall_pass"],
        [{"state_id": "H_q0_mult2_nist", "overall_pass": True}],
    )
    (qa_dir / "metadata.json").write_text(
        json.dumps(
            {
                "schema_version": "atomref.proatoms.qa_dataset.v1",
                "profile_data_version": "2.0.0",
                "dataset_id": DATASET_ID,
                "basis_id": BASIS_ID,
                "row_count": 1,
                "failed_count": 0,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    _write_rows(
        qa_root / "qa_summary.csv",
        ["dataset_id", "basis_id", "state_count", "failed_count"],
        [{"dataset_id": DATASET_ID, "basis_id": BASIS_ID, "state_count": 1, "failed_count": 0}],
    )
    (qa_root / "qa_report.md").write_text("# atomref-proatoms QA status: PASS\n", encoding="utf-8")
    (qa_root / "metadata.json").write_text(
        json.dumps(
            {
                "schema_version": "atomref.proatoms.qa_overview.v1",
                "profile_data_version": "2.0.0",
                "dataset_count": 1,
                "state_count": 1,
                "failed_count": 0,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return config, states, profiles_root, radii_root, qa_root


def test_check_profile_artifacts_script_passes_before_generation() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_profile_artifacts.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "OK: no generated profile/radii/QA dataset artifacts found" in result.stdout
    assert "profile_data_version: 2.0.0" in result.stdout


def test_check_generated_artifacts_rejects_stale_unconfigured_dataset(tmp_path: Path) -> None:
    config, states, profiles_root, radii_root, qa_root = _write_valid_artifacts(tmp_path)
    (profiles_root / "stale_dataset").mkdir()

    result = check_generated_artifacts(
        config_path=config,
        states_file=states,
        profiles_root=profiles_root,
        radii_root=radii_root,
        qa_root=qa_root,
    )

    assert not result.ok
    assert any("not in active config" in error for error in result.errors)


def test_check_generated_artifacts_accepts_complete_matching_artifacts(tmp_path: Path) -> None:
    config, states, profiles_root, radii_root, qa_root = _write_valid_artifacts(tmp_path)

    result = check_generated_artifacts(
        config_path=config,
        states_file=states,
        profiles_root=profiles_root,
        radii_root=radii_root,
        qa_root=qa_root,
    )

    assert result.ok, result.errors
    assert result.checked_dataset_ids == (DATASET_ID,)
    assert result.state_count == 1


def test_check_generated_artifacts_require_generated_flag_fails_empty(tmp_path: Path) -> None:
    config = tmp_path / "profile_datasets.yaml"
    states = tmp_path / "states.json"
    _write_config(config)
    _write_states(states)
    profiles_root = tmp_path / "profiles"
    radii_root = tmp_path / "radii"
    qa_root = tmp_path / "qa"
    for root in (profiles_root, radii_root, qa_root):
        root.mkdir()
        (root / "README.md").write_text("placeholder\n", encoding="utf-8")

    result = check_generated_artifacts(
        config_path=config,
        states_file=states,
        profiles_root=profiles_root,
        radii_root=radii_root,
        qa_root=qa_root,
        allow_empty=False,
    )

    assert not result.ok
    assert result.errors == ("no generated profile/radii/QA dataset directories found",)
