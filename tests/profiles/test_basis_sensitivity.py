from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from atomref_proatoms.dataio.datasets import ANION_X2C_QZVPALL_S, PRIMARY_X2C_QZVPALL
from atomref_proatoms.profiles.basis_sensitivity import (
    BASIS_SENSITIVITY_SCHEMA_VERSION,
    build_basis_sensitivity_qa,
    read_profile_dataset,
)
from atomref_proatoms.profiles.artifacts import profile_density_column

STATE_ID = "H_qm1_mult1_test"


def _write_profile_dataset(
    root: Path,
    dataset_id: str,
    basis_id: str,
    densities: list[float],
) -> None:
    dataset_dir = root / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    column = profile_density_column(STATE_ID)
    with (dataset_dir / "profiles.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["r_bohr", column])
        writer.writeheader()
        for radius, density in zip([0.1, 0.2, 0.4, 0.8, 1.6], densities, strict=True):
            writer.writerow({"r_bohr": radius, column: density})
    (dataset_dir / "metadata.json").write_text(
        json.dumps(
            {
                "schema_version": "atomref.proatoms.profile_dataset.v1",
                "profile_data_version": "2.0.0",
                "dataset_id": dataset_id,
                "basis_id": basis_id,
                "columns": {column: {"state_id": STATE_ID}},
                "states": {
                    STATE_ID: {
                        "symbol": "H",
                        "z": 1,
                        "charge": -1,
                        "electron_count": 2,
                        "multiplicity": 1,
                        "state_category": "test",
                        "state_role": "bound_experimental",
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_read_profile_dataset_roundtrips_state_density(tmp_path: Path) -> None:
    _write_profile_dataset(tmp_path, PRIMARY_X2C_QZVPALL, "x2c-QZVPall", [4, 3, 2, 1, 0.5])

    dataset = read_profile_dataset(tmp_path, PRIMARY_X2C_QZVPALL)

    assert dataset.dataset_id == PRIMARY_X2C_QZVPALL
    assert dataset.basis_id == "x2c-QZVPall"
    assert dataset.state_ids == (STATE_ID,)
    assert dataset.densities_by_state_id[STATE_ID].tolist() == pytest.approx([4, 3, 2, 1, 0.5])


def test_build_basis_sensitivity_qa_writes_optional_artifacts(tmp_path: Path) -> None:
    profiles_root = tmp_path / "profiles"
    qa_root = tmp_path / "qa"
    _write_profile_dataset(
        profiles_root,
        PRIMARY_X2C_QZVPALL,
        "x2c-QZVPall",
        [4.0, 3.0, 2.0, 1.0, 0.5],
    )
    _write_profile_dataset(
        profiles_root,
        ANION_X2C_QZVPALL_S,
        "x2c-QZVPall-s",
        [4.0, 3.0, 2.0, 1.1, 0.6],
    )

    result = build_basis_sensitivity_qa(
        profiles_root=profiles_root,
        qa_root=qa_root,
        force=True,
        warn_relative_l1=999.0,
        warn_delta_radius_angstrom=999.0,
    )

    assert result.row_count == 1
    assert result.summary_count == 1
    assert result.outlier_count == 0
    metadata = json.loads(result.metadata_json.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == BASIS_SENSITIVITY_SCHEMA_VERSION
    assert metadata["skipped_pairs"]
    with result.rows_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["state_id"] == STATE_ID
    assert rows[0]["base_basis_id"] == "x2c-QZVPall"
    assert rows[0]["diffuse_basis_id"] == "x2c-QZVPall-s"
    assert rows[0]["status"] == "OK"


def test_build_basis_sensitivity_qa_marks_outlier(tmp_path: Path) -> None:
    profiles_root = tmp_path / "profiles"
    _write_profile_dataset(
        profiles_root,
        PRIMARY_X2C_QZVPALL,
        "x2c-QZVPall",
        [4.0, 3.0, 2.0, 1.0, 0.5],
    )
    _write_profile_dataset(
        profiles_root,
        ANION_X2C_QZVPALL_S,
        "x2c-QZVPall-s",
        [4.0, 3.0, 2.0, 4.0, 5.0],
    )

    result = build_basis_sensitivity_qa(
        profiles_root=profiles_root,
        qa_root=tmp_path / "qa",
        force=True,
        warn_relative_l1=1.0e-8,
        warn_delta_radius_angstrom=1.0e-8,
    )

    assert result.outlier_count == 1
    with result.outliers_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["status"] == "WARN"
