from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from atomref_proatoms.dataio.datasets import (
    AUGMENTED_DYALL_AV4Z,
    PRIMARY_DYALL_V4Z,
    PRIMARY_X2C_QZVPALL,
    SUPPLEMENTED_X2C_QZVPALL_S,
)
from atomref_proatoms.dataio.paths import STATES_FILE
from atomref_proatoms.profiles.build_plan import (
    build_jobs_for_dataset,
    build_jobs_for_datasets,
    build_plan_summary,
    filter_build_jobs,
    format_build_plan,
)
from atomref_proatoms.states import load_atom_states

ROOT = Path(__file__).resolve().parents[2]


def _states():
    return load_atom_states(STATES_FILE)


def test_build_plan_dataset_counts_match_v2_scope_policy() -> None:
    states = _states()
    counts = {
        dataset_id: len(build_jobs_for_dataset(states, dataset_id))
        for dataset_id in (
            PRIMARY_X2C_QZVPALL,
            PRIMARY_DYALL_V4Z,
            SUPPLEMENTED_X2C_QZVPALL_S,
            AUGMENTED_DYALL_AV4Z,
        )
    }
    assert counts == {
        PRIMARY_X2C_QZVPALL: 430,
        PRIMARY_DYALL_V4Z: 501,
        SUPPLEMENTED_X2C_QZVPALL_S: 192,
        AUGMENTED_DYALL_AV4Z: 166,
    }


def test_build_plan_preserves_state_order_with_dataset_blocks() -> None:
    jobs = build_jobs_for_datasets(
        _states(), dataset_ids=(PRIMARY_X2C_QZVPALL, PRIMARY_DYALL_V4Z)
    )
    assert jobs[0].state_id == "H_qm1_mult1_ning2022"
    assert jobs[0].dataset_id == PRIMARY_X2C_QZVPALL
    assert jobs[429].state_id == "Rn_qp3_mult4_nist"
    assert jobs[429].dataset_id == PRIMARY_X2C_QZVPALL
    assert jobs[430].state_id == "H_qm1_mult1_ning2022"
    assert jobs[430].dataset_id == PRIMARY_DYALL_V4Z
    assert jobs[431].state_id == "H_q0_mult2_nist"
    assert jobs[431].dataset_id == PRIMARY_DYALL_V4Z
    assert jobs[-1].state_id == "Lr_qp3_mult1_nist"
    assert any(job.state_id == "U_qm1_mult6_ning2022" for job in jobs)


def test_supplemented_dataset_order_and_scope() -> None:
    jobs = build_jobs_for_datasets(
        _states(), dataset_ids=(SUPPLEMENTED_X2C_QZVPALL_S, AUGMENTED_DYALL_AV4Z)
    )
    assert jobs[0].state_id == "H_qm1_mult1_ning2022"
    assert jobs[0].dataset_id == SUPPLEMENTED_X2C_QZVPALL_S
    assert jobs[190].state_id == "At_q0_mult2_nist"
    assert jobs[191].state_id == "Rn_q0_mult1_nist"
    assert jobs[192].state_id == "H_qm1_mult1_ning2022"
    assert jobs[192].dataset_id == AUGMENTED_DYALL_AV4Z
    assert jobs[-1].state_id == "Ra_q0_mult1_nist"
    assert any(job.state_id == "Fr_qm1_mult1_ning2022" for job in jobs)
    assert any(job.state_id == "Ra_qm1_mult2_ning2022" for job in jobs)
    assert {job.charge_class for job in jobs} == {"neutral", "anion"}


def test_build_plan_summary_counts_charge_classes() -> None:
    jobs = build_jobs_for_datasets(_states())
    summary = build_plan_summary(jobs)
    assert summary["job_count"] == 1289
    assert summary["by_charge_class"] == {"neutral": 348, "cation": 524, "anion": 417}
    formatted = format_build_plan(jobs)
    assert PRIMARY_DYALL_V4Z in formatted
    assert AUGMENTED_DYALL_AV4Z in formatted


def test_filter_build_jobs_rejects_missing_state() -> None:
    jobs = build_jobs_for_datasets(_states(), dataset_ids=(PRIMARY_X2C_QZVPALL,))
    with pytest.raises(ValueError, match="not in the selected build plan"):
        filter_build_jobs(jobs, only_state_ids={"U_q0_mult5_nist"})


def test_compute_wavefunctions_list_cli() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/compute_wavefunctions.py",
            "--dataset",
            PRIMARY_DYALL_V4Z,
            "--list",
            "--show-jobs",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Profile data version: 2.0.0" in result.stdout
    assert "Build jobs: 501" in result.stdout
    assert PRIMARY_DYALL_V4Z in result.stdout
    assert "Lr_qp3_mult1_nist" in result.stdout
    assert "U_qm1_mult6_ning2022" in result.stdout
    assert "Dry run completed before PySCF import/SCF execution" in result.stdout


def test_compute_wavefunctions_dry_run_does_not_import_pyscf() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/compute_wavefunctions.py",
            "--dataset",
            PRIMARY_X2C_QZVPALL,
            "--state",
            "H_q0_mult2_nist",
            "--dry-run",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Build jobs: 1" in result.stdout
    assert "Dry run completed before PySCF import/SCF execution" in result.stdout
    assert "local-data/scf" in result.stdout


def test_extract_profiles_dry_run_does_not_import_pyscf_or_read_checkpoints(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/extract_profiles.py",
            "--dataset",
            PRIMARY_X2C_QZVPALL,
            "--state",
            "H_q0_mult2_nist",
            "--scf-root",
            str(tmp_path / "scf"),
            "--output-root",
            str(tmp_path / "profiles"),
            "--dry-run",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Build jobs: 1" in result.stdout
    assert "required SCF artifacts" in result.stdout
    assert "Dry run completed before PySCF import/checkpoint reading" in result.stdout
