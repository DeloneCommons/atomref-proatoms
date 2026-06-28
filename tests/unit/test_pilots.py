from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from atomref_proatoms.datasets import (
    ANION_X2C_QZVPALL_S,
    PRIMARY_DYALL_V4Z,
    PRIMARY_X2C_QZVPALL,
)
from atomref_proatoms.pilots import (
    ANION_FORMAL_X2C_DIFFUSE,
    DEFAULT_PILOT_GROUP,
    HEAVY_DYALL_SMOKE,
    H_SMOKE,
    NEUTRAL_LIGHT_X2C,
    filter_pilots,
    get_pilot_group,
    pilot_group_names,
)

ROOT = Path(__file__).resolve().parents[2]


def test_pilot_group_names_are_ordered() -> None:
    assert pilot_group_names() == (
        H_SMOKE,
        NEUTRAL_LIGHT_X2C,
        ANION_FORMAL_X2C_DIFFUSE,
        HEAVY_DYALL_SMOKE,
    )
    assert DEFAULT_PILOT_GROUP == NEUTRAL_LIGHT_X2C


def test_neutral_light_group_matches_recommended_pilots() -> None:
    pilots = get_pilot_group(NEUTRAL_LIGHT_X2C)
    assert [pilot.state_id for pilot in pilots] == [
        "H_q0_mult2_hund",
        "He_q0_mult1_hund",
        "C_q0_mult3_hund",
        "N_q0_mult4_hund",
        "Ne_q0_mult1_hund",
    ]
    assert {pilot.dataset_id for pilot in pilots} == {PRIMARY_X2C_QZVPALL}


def test_later_pilot_groups_are_explicitly_named() -> None:
    anion_pilots = get_pilot_group(ANION_FORMAL_X2C_DIFFUSE)
    assert [pilot.state_id for pilot in anion_pilots] == [
        "I_qm1_mult1_hund",
        "O_qm2_mult1_hund",
        "S_qm2_mult1_hund",
    ]
    assert {pilot.dataset_id for pilot in anion_pilots} == {ANION_X2C_QZVPALL_S}

    heavy_pilots = get_pilot_group(HEAVY_DYALL_SMOKE)
    assert [pilot.state_id for pilot in heavy_pilots] == [
        "Eu_qp3_mult7_hund",
        "U_q0_mult5_hund",
    ]
    assert {pilot.dataset_id for pilot in heavy_pilots} == {PRIMARY_DYALL_V4Z}


def test_filter_pilots_keeps_order() -> None:
    pilots = get_pilot_group(NEUTRAL_LIGHT_X2C)
    filtered = filter_pilots(pilots, only_state_ids={"Ne_q0_mult1_hund", "H_q0_mult2_hund"})
    assert [pilot.state_id for pilot in filtered] == ["H_q0_mult2_hund", "Ne_q0_mult1_hund"]


def test_filter_pilots_rejects_missing_state() -> None:
    with pytest.raises(ValueError, match="not in the selected pilot group"):
        filter_pilots(get_pilot_group(H_SMOKE), only_state_ids={"He_q0_mult1_hund"})


def test_run_pilots_list_cli() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_pilots.py", "--list"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "neutral_light_x2c" in result.stdout
    assert "H_q0_mult2_hund" in result.stdout


def test_run_pilots_dry_run_h_smoke(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_pilots.py",
            "--group",
            H_SMOKE,
            "--output-dir",
            str(tmp_path),
            "--dry-run",
            "--build-indexes",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Running pilot group 'h_smoke'" in result.stdout
    assert "Dry run completed before PySCF import/SCF execution" in result.stdout
    assert "Pilot batch completed successfully" in result.stdout
    assert "Building dataset indexes" not in result.stdout
