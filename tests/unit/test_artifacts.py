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

from atomref_proatoms.artifacts import (  # noqa: E402
    qa_overall_pass,
    write_qa_dataset_artifacts,
    write_qa_overview,
    write_radii_dataset_artifacts,
)


def _state_table_metadata() -> dict[str, dict[str, object]]:
    return {
        "H_q0_mult2_hund": {
            "symbol": "H",
            "z": 1,
            "charge": 0,
            "electron_count": 1,
            "multiplicity": 2,
            "state_category": "nist_ground_state",
            "state_role": "recommended",
        }
    }


def test_write_radii_dataset_artifacts_writes_csv_and_metadata(tmp_path) -> None:
    radii_csv, metadata_json = write_radii_dataset_artifacts(
        tmp_path / "radii" / "dataset",
        dataset_id="dataset",
        profile_data_version="1.0.0.dev0",
        basis_id="basis",
        cutoffs_e_bohr3=[0.003, 0.001],
        states=_state_table_metadata(),
        derived_radii_by_state_id={
            "H_q0_mult2_hund": {
                "r_iso_0.003_e_bohr3_bohr": 1.0,
                "r_iso_0.001_e_bohr3_bohr": 2.0,
            }
        },
        source_profiles_csv="data/profiles/dataset/profiles.csv",
        source_metadata_json="data/profiles/dataset/metadata.json",
    )

    with radii_csv.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["state_id"] == "H_q0_mult2_hund"
    assert rows[0]["r_iso_0.003_e_bohr3_bohr"] == "1.0"
    metadata = json.loads(metadata_json.read_text())
    assert metadata["schema_version"] == "atomref.proatoms.radii_dataset.v1"
    assert metadata["row_count"] == 1


def test_write_qa_dataset_artifacts_and_overview(tmp_path) -> None:
    qa = {
        "H_q0_mult2_hund": {
            "scf_converged": True,
            "electron_count_error_qa": 1.0e-12,
            "electron_count_tolerance": 2.0e-6,
            "electron_count_pass": True,
            "max_rel_angular_sigma": 0.0,
            "max_rel_angular_sigma_tolerance": 1.0e-8,
            "angular_sigma_pass": True,
            "tail_reaches_min_cutoff": True,
            "radii_monotonic": True,
            "linear_dependency_warning_count": 0,
            "linear_dependency_vectors_removed": None,
        }
    }
    qa_csv, metadata_json = write_qa_dataset_artifacts(
        tmp_path / "qa" / "dataset",
        dataset_id="dataset",
        profile_data_version="1.0.0.dev0",
        basis_id="basis",
        states=_state_table_metadata(),
        qa_by_state_id=qa,
        source_profiles_csv="data/profiles/dataset/profiles.csv",
        source_metadata_json="data/profiles/dataset/metadata.json",
    )

    with qa_csv.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["overall_pass"] == "True"
    assert qa_overall_pass({**qa["H_q0_mult2_hund"], "overall_pass": True})
    metadata = json.loads(metadata_json.read_text())
    assert metadata["schema_version"] == "atomref.proatoms.qa_dataset.v1"
    assert metadata["failed_count"] == 0

    outputs = write_qa_overview(
        tmp_path / "qa",
        profile_data_version="1.0.0.dev0",
        dataset_summaries=[
            {
                "dataset_id": "dataset",
                "basis_id": "basis",
                "state_count": 1,
                "passed_count": 1,
                "failed_count": 0,
                "max_abs_electron_count_error_qa": 1.0e-12,
                "max_rel_angular_sigma": 0.0,
                "linear_dependency_warning_count": 0,
            }
        ],
    )
    assert outputs["qa_report"].read_text().startswith("# atomref-proatoms QA status: PASS")
