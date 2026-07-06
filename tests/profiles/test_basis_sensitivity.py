from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from atomref_proatoms.dataio.datasets import (
    AUGMENTED_DYALL_AV4Z,
    PRIMARY_DYALL_V4Z,
    PRIMARY_X2C_QZVPALL,
    SUPPLEMENTED_X2C_QZVPALL_S,
)
from atomref_proatoms.profiles.artifacts import profile_density_column
from atomref_proatoms.profiles.basis_sensitivity import (
    BASIS_SENSITIVITY_SCHEMA_VERSION,
    build_basis_sensitivity_qa,
    read_profile_dataset,
)

STATE_ID = "H_qm1_mult1_test"


def _write_profile_dataset(
    root: Path,
    dataset_id: str,
    basis_id: str,
    densities: list[float],
    *,
    state_digest: str | None = "digest-a",
) -> None:
    dataset_dir = root / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    column = profile_density_column(STATE_ID)
    with (dataset_dir / "profiles.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["r_bohr", column])
        writer.writeheader()
        for radius, density in zip([0.1, 0.2, 0.4, 0.8, 1.6], densities, strict=True):
            writer.writerow({"r_bohr": radius, column: density})
    metadata = {
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
    }
    if state_digest is not None:
        metadata["scf_artifacts"] = {
            STATE_ID: {"fingerprints": {"state_record_sha256": state_digest}}
        }
    (dataset_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )


def test_read_profile_dataset_roundtrips_state_density(tmp_path: Path) -> None:
    _write_profile_dataset(tmp_path, PRIMARY_X2C_QZVPALL, "x2c-QZVPall", [4, 3, 2, 1, 0.5])

    dataset = read_profile_dataset(tmp_path, PRIMARY_X2C_QZVPALL)

    assert dataset.dataset_id == PRIMARY_X2C_QZVPALL
    assert dataset.basis_id == "x2c-QZVPall"
    assert dataset.state_ids == (STATE_ID,)
    assert dataset.densities_by_state_id[STATE_ID].tolist() == pytest.approx([4, 3, 2, 1, 0.5])
    assert dataset.state_record_sha256_by_state_id[STATE_ID] == "digest-a"


def test_build_basis_sensitivity_qa_writes_primary_dyall_artifacts(tmp_path: Path) -> None:
    profiles_root = tmp_path / "profiles"
    qa_root = tmp_path / "qa"
    _write_profile_dataset(
        profiles_root,
        PRIMARY_DYALL_V4Z,
        "dyall-v4z",
        [4.0, 3.0, 2.0, 1.0, 0.5],
    )
    _write_profile_dataset(
        profiles_root,
        AUGMENTED_DYALL_AV4Z,
        "dyall-av4z",
        [4.0, 3.0, 2.0, 1.1, 0.6],
    )

    result = build_basis_sensitivity_qa(
        profiles_root=profiles_root,
        qa_root=qa_root,
        pairs=((PRIMARY_DYALL_V4Z, AUGMENTED_DYALL_AV4Z),),
        states_file=None,
        require_complete=False,
        force=True,
        relative_l1_watch=999.0,
        relative_l1_outlier=999.0,
        max_cumulative_delta_watch_electrons=999.0,
        max_cumulative_delta_outlier_electrons=999.0,
        mean_radial_shift_watch_angstrom=999.0,
        mean_radial_shift_outlier_angstrom=999.0,
        max_electron_count_error=999.0,
    )

    assert result.row_count == 1
    assert result.summary_count == 1
    assert result.outlier_count == 0
    metadata = json.loads(result.metadata_json.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == BASIS_SENSITIVITY_SCHEMA_VERSION
    assert "basis_sensitivity_dyall" in metadata["pair_outputs"]
    dyall_outputs = metadata["pair_outputs"]["basis_sensitivity_dyall"]
    assert Path(dyall_outputs["rows_csv"]).parent.name == "dyall-v4z"
    assert Path(dyall_outputs["rows_csv"]).name == "basis_sensitivity.csv"
    assert (qa_root / "basis_sensitivity" / "dyall-v4z" / "basis_sensitivity.csv").is_file()
    assert not (qa_root / "basis_sensitivity" / "basis_sensitivity_dyall.csv").exists()
    assert result.metric_distribution_count > 0
    with result.rows_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["state_id"] == STATE_ID
    assert rows[0]["base_basis_id"] == "dyall-v4z"
    assert rows[0]["diffuse_basis_id"] == "dyall-av4z"
    assert rows[0]["release_gate_status"] == "PASS"
    assert rows[0]["sensitivity_tier"] == "low"
    assert rows[0]["max_abs_cumulative_delta_electrons"]


def test_build_basis_sensitivity_qa_writes_x2c_artifacts(tmp_path: Path) -> None:
    profiles_root = tmp_path / "profiles"
    _write_profile_dataset(
        profiles_root,
        PRIMARY_X2C_QZVPALL,
        "x2c-QZVPall",
        [4.0, 3.0, 2.0, 1.0, 0.5],
    )
    _write_profile_dataset(
        profiles_root,
        SUPPLEMENTED_X2C_QZVPALL_S,
        "x2c-QZVPall-s",
        [4.0, 3.0, 2.0, 1.1, 0.6],
    )

    result = build_basis_sensitivity_qa(
        profiles_root=profiles_root,
        qa_root=tmp_path / "qa",
        pairs=((PRIMARY_X2C_QZVPALL, SUPPLEMENTED_X2C_QZVPALL_S),),
        states_file=None,
        require_complete=False,
        force=True,
    )

    metadata = json.loads(result.metadata_json.read_text(encoding="utf-8"))
    assert "basis_sensitivity_x2c" in metadata["pair_outputs"]
    x2c_outputs = metadata["pair_outputs"]["basis_sensitivity_x2c"]
    assert Path(x2c_outputs["rows_csv"]).parent.name == "x2c-QZVPall"
    assert Path(x2c_outputs["rows_csv"]).name == "basis_sensitivity.csv"


def test_build_basis_sensitivity_qa_marks_scientific_outlier(tmp_path: Path) -> None:
    profiles_root = tmp_path / "profiles"
    _write_profile_dataset(
        profiles_root,
        PRIMARY_DYALL_V4Z,
        "dyall-v4z",
        [4.0, 3.0, 2.0, 1.0, 0.5],
    )
    _write_profile_dataset(
        profiles_root,
        AUGMENTED_DYALL_AV4Z,
        "dyall-av4z",
        [4.0, 3.0, 2.0, 4.0, 5.0],
    )

    result = build_basis_sensitivity_qa(
        profiles_root=profiles_root,
        qa_root=tmp_path / "qa",
        pairs=((PRIMARY_DYALL_V4Z, AUGMENTED_DYALL_AV4Z),),
        states_file=None,
        require_complete=False,
        force=True,
        relative_l1_watch=1.0e-8,
        relative_l1_outlier=1.0e-8,
        max_cumulative_delta_watch_electrons=1.0e-8,
        max_cumulative_delta_outlier_electrons=1.0e-8,
        mean_radial_shift_watch_angstrom=1.0e-8,
        mean_radial_shift_outlier_angstrom=1.0e-8,
        max_electron_count_error=999.0,
    )

    assert result.outlier_count == 1
    with result.outliers_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["release_gate_status"] == "PASS"
    assert rows[0]["sensitivity_tier"] == "high"


def test_build_basis_sensitivity_qa_rejects_state_digest_mismatch(tmp_path: Path) -> None:
    profiles_root = tmp_path / "profiles"
    _write_profile_dataset(
        profiles_root,
        PRIMARY_DYALL_V4Z,
        "dyall-v4z",
        [4.0, 3.0, 2.0, 1.0, 0.5],
        state_digest="digest-a",
    )
    _write_profile_dataset(
        profiles_root,
        AUGMENTED_DYALL_AV4Z,
        "dyall-av4z",
        [4.0, 3.0, 2.0, 1.1, 0.6],
        state_digest="digest-b",
    )

    with pytest.raises(ValueError, match="state_record_sha256 mismatch"):
        build_basis_sensitivity_qa(
            profiles_root=profiles_root,
            qa_root=tmp_path / "qa",
            pairs=((PRIMARY_DYALL_V4Z, AUGMENTED_DYALL_AV4Z),),
            states_file=None,
            require_complete=False,
            force=True,
        )
