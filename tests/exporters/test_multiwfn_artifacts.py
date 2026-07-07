from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from atomref_proatoms.dataio.datasets import (
    AUGMENTED_DYALL_AV4Z,
    PRIMARY_DYALL_V4Z,
    PRIMARY_X2C_QZVPALL,
    SUPPLEMENTED_X2C_QZVPALL_S,
    load_profile_dataset_config,
    multiwfn_rad_allowed_for_dataset,
    multiwfn_wfn_allowed_for_dataset,
)
from atomref_proatoms.dataio.paths import STATES_FILE
from atomref_proatoms.exporters.multiwfn_artifacts import (
    build_multiwfn_artifact_jobs,
    format_multiwfn_artifact_plan,
    multiwfn_artifact_plan_summary,
)
from atomref_proatoms.states.state_tables import load_atom_states

ROOT = Path(__file__).resolve().parents[2]


def test_dataset_multiwfn_artifact_policy_is_explicit() -> None:
    config = load_profile_dataset_config()
    assert config.scope(PRIMARY_X2C_QZVPALL).multiwfn_rad == "all_states"
    assert config.scope(PRIMARY_X2C_QZVPALL).multiwfn_wfn == "neutral_atoms"
    assert config.scope(PRIMARY_DYALL_V4Z).multiwfn_rad == "all_states"
    assert config.scope(PRIMARY_DYALL_V4Z).multiwfn_wfn == "none"
    assert config.scope(SUPPLEMENTED_X2C_QZVPALL_S).multiwfn_rad == "none"
    assert config.scope(AUGMENTED_DYALL_AV4Z).multiwfn_wfn == "none"
    assert multiwfn_rad_allowed_for_dataset(PRIMARY_X2C_QZVPALL, charge=-1)
    assert multiwfn_rad_allowed_for_dataset(PRIMARY_DYALL_V4Z, charge=3)
    assert multiwfn_wfn_allowed_for_dataset(PRIMARY_X2C_QZVPALL, charge=0)
    assert not multiwfn_wfn_allowed_for_dataset(PRIMARY_X2C_QZVPALL, charge=-1)
    assert not multiwfn_rad_allowed_for_dataset(SUPPLEMENTED_X2C_QZVPALL_S, charge=0)


def test_multiwfn_artifact_plan_counts() -> None:
    states = load_atom_states(STATES_FILE)
    jobs = build_multiwfn_artifact_jobs(states)
    summary = multiwfn_artifact_plan_summary(jobs)
    formatted = format_multiwfn_artifact_plan(jobs)

    assert summary["rad_file_count"] == 430 + 501
    assert summary["wfn_file_count"] == 86
    assert summary["job_count"] == 430 + 501
    assert summary["by_dataset"][PRIMARY_X2C_QZVPALL] == {"rad": 430, "wfn": 86, "total": 430}
    assert summary["by_dataset"][PRIMARY_DYALL_V4Z] == {"rad": 501, "wfn": 0, "total": 501}
    assert SUPPLEMENTED_X2C_QZVPALL_S not in summary["by_dataset"]
    assert ".rad files: 931" in formatted
    assert ".wfn files: 86" in formatted


def test_export_multiwfn_artifacts_dry_run_does_not_require_pyscf_or_write(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_multiwfn_artifacts.py",
            "--dataset",
            PRIMARY_X2C_QZVPALL,
            "--state",
            "H_q0_mult2_nist",
            "--output-root",
            str(tmp_path / "multiwfn"),
            "--dry-run",
            "--show-jobs",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Multiwfn export jobs: 1" in result.stdout
    assert ".rad files: 1" in result.stdout
    assert ".wfn files: 1" in result.stdout
    assert "H_0.rad" in result.stdout
    assert "H .wfn" in result.stdout
    assert "Dry run completed before Multiwfn artifact export" in result.stdout
    assert not (tmp_path / "multiwfn").exists()


def test_check_multiwfn_artifacts_round_trips_generated_rad(tmp_path: Path) -> None:
    out = tmp_path / "multiwfn"
    subprocess.run(
        [
            sys.executable,
            "scripts/export_multiwfn_artifacts.py",
            "--dataset",
            PRIMARY_X2C_QZVPALL,
            "--state",
            "H_q0_mult2_nist",
            "--format",
            "rad",
            "--output-root",
            str(out),
            "--force",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_multiwfn_artifacts.py",
            "--artifact-root",
            str(out),
            "--require-generated",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "OK: checked 1 Multiwfn interoperability files" in result.stdout
    assert ".rad files: 1" in result.stdout
    assert ".wfn files: 0" in result.stdout
