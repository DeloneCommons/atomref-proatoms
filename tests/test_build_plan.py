from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from atomref_proatoms.build_plan import (
    build_jobs_for_dataset,
    build_jobs_for_datasets,
    build_plan_summary,
    filter_build_jobs,
    format_build_plan,
)
from atomref_proatoms.datasets import PRIMARY_DYALL_V4Z, PRIMARY_X2C_QZVPALL
from atomref_proatoms.states import load_atom_states

ROOT = Path(__file__).resolve().parents[1]
STATES_FILE = ROOT / "data" / "states" / "curated" / "atom_states_v1.json"


def _states():
    return load_atom_states(STATES_FILE)


def test_build_plan_dataset_counts_match_neutral_scope_policy() -> None:
    states = _states()
    counts = {
        dataset_id: len(build_jobs_for_dataset(states, dataset_id))
        for dataset_id in (PRIMARY_X2C_QZVPALL, PRIMARY_DYALL_V4Z)
    }
    assert counts == {
        PRIMARY_X2C_QZVPALL: 86,
        PRIMARY_DYALL_V4Z: 103,
    }


def test_build_plan_preserves_state_order_with_dataset_blocks() -> None:
    jobs = build_jobs_for_datasets(_states(), dataset_ids=(PRIMARY_X2C_QZVPALL, PRIMARY_DYALL_V4Z))
    assert jobs[0].state_id == "H_q0_mult2_hund"
    assert jobs[0].dataset_id == PRIMARY_X2C_QZVPALL
    assert jobs[85].state_id == "Rn_q0_mult1_hund"
    assert jobs[85].dataset_id == PRIMARY_X2C_QZVPALL
    assert jobs[86].state_id == "H_q0_mult2_hund"
    assert jobs[86].dataset_id == PRIMARY_DYALL_V4Z
    assert jobs[-1].state_id == "Lr_q0_mult2_hund"


def test_build_plan_summary_counts_charge_classes() -> None:
    jobs = build_jobs_for_datasets(_states(), dataset_ids=(PRIMARY_DYALL_V4Z,))
    summary = build_plan_summary(jobs)
    assert summary["job_count"] == 103
    assert summary["by_charge_class"] == {"neutral": 103, "cation": 0, "anion": 0}
    assert PRIMARY_DYALL_V4Z in format_build_plan(jobs)


def test_filter_build_jobs_rejects_missing_state() -> None:
    jobs = build_jobs_for_datasets(_states(), dataset_ids=(PRIMARY_X2C_QZVPALL,))
    with pytest.raises(ValueError, match="not in the selected build plan"):
        filter_build_jobs(jobs, only_state_ids={"U_q0_mult5_hund"})


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
    assert "Profile data version: 1.0.0.dev0" in result.stdout
    assert "Build jobs: 103" in result.stdout
    assert PRIMARY_DYALL_V4Z in result.stdout
    assert "Lr_q0_mult2_hund" in result.stdout
    assert "Dry run completed before PySCF import/SCF execution" in result.stdout


def test_compute_wavefunctions_dry_run_does_not_import_pyscf() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/compute_wavefunctions.py",
            "--dataset",
            PRIMARY_X2C_QZVPALL,
            "--state",
            "H_q0_mult2_hund",
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
            "H_q0_mult2_hund",
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
    assert "requires" in result.stdout
    assert "Dry run completed before PySCF import/checkpoint reading" in result.stdout
