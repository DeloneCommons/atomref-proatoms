from __future__ import annotations

import csv
import json
import math

import pytest

from atomref_proatoms.artifacts import (
    profile_density_column,
    write_json,
    write_profile_dataset_artifacts,
    write_wide_profiles_csv,
)


def test_write_wide_profiles_csv_contains_shared_radius_and_state_columns(tmp_path) -> None:
    path = tmp_path / "profiles.csv"
    write_wide_profiles_csv(
        path,
        r_bohr=[0.1, 0.2],
        densities_by_state_id={
            "H_q0_mult2_hund": [2.0, 1.0],
            "He_q0_mult1_hund": [4.0, 2.0],
        },
    )

    with path.open(newline="") as handle:
        rows = list(csv.reader(handle))

    assert rows == [
        ["r_bohr", "rho_e_bohr3__H_q0_mult2_hund", "rho_e_bohr3__He_q0_mult1_hund"],
        ["0.10000000000000001", "2", "4"],
        ["0.20000000000000001", "1", "2"],
    ]


def test_write_wide_profiles_csv_rejects_mismatched_lengths(tmp_path) -> None:
    with pytest.raises(ValueError, match="does not match r_bohr length"):
        write_wide_profiles_csv(
            tmp_path / "profiles.csv",
            r_bohr=[0.1, 0.2],
            densities_by_state_id={"H_q0_mult2_hund": [2.0]},
        )


def test_profile_density_column_is_state_id_based() -> None:
    assert profile_density_column("O_qm2_mult1_hund") == "rho_e_bohr3__O_qm2_mult1_hund"


def test_write_json_replaces_nonfinite_numbers_with_null(tmp_path) -> None:
    path = tmp_path / "metadata.json"
    write_json(path, {"finite": 1.0, "nan": math.nan, "inf": math.inf})

    text = path.read_text()
    assert "NaN" not in text
    assert "Infinity" not in text
    assert json.loads(text) == {"finite": 1.0, "nan": None, "inf": None}


def test_write_profile_dataset_artifacts_writes_one_csv_and_one_json(tmp_path) -> None:
    profiles_path, metadata_path = write_profile_dataset_artifacts(
        tmp_path,
        r_bohr=[0.1, 0.2],
        densities_by_state_id={"H_q0_mult2_hund": [2.0, 1.0]},
        metadata={"dataset_id": "test", "qa": {"electron_count_error_qa": None}},
    )

    assert profiles_path.name == "profiles.csv"
    assert metadata_path.name == "metadata.json"
    assert json.loads(metadata_path.read_text()) == {
        "dataset_id": "test",
        "qa": {"electron_count_error_qa": None},
    }
