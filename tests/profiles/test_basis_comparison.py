from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from atomref_proatoms.dataio.datasets import PRIMARY_DYALL_V4Z, PRIMARY_X2C_QZVPALL
from atomref_proatoms.profiles.artifacts import profile_density_column
from atomref_proatoms.profiles.basis_comparison import (
    BASIS_COMPARISON_SCHEMA_VERSION,
    build_primary_basis_comparisons,
)

STATE_ID = "H_q0_mult2_test"


def _write_profile_dataset(
    root: Path,
    dataset_id: str,
    basis_id: str,
    densities: list[float],
    *,
    state_digest: str = "digest-a",
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
                "charge": 0,
                "electron_count": 1,
                "multiplicity": 2,
                "state_category": "test",
                "state_role": "reference",
            }
        },
        "scf_artifacts": {
            STATE_ID: {"fingerprints": {"state_record_sha256": state_digest}}
        },
    }
    (dataset_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )


def test_build_primary_basis_comparisons_writes_pair_directory(tmp_path: Path) -> None:
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
        PRIMARY_DYALL_V4Z,
        "dyall-v4z",
        [4.0, 3.0, 2.0, 1.1, 0.6],
    )

    result = build_primary_basis_comparisons(
        profiles_root=profiles_root,
        qa_root=qa_root,
        pairs=((PRIMARY_X2C_QZVPALL, PRIMARY_DYALL_V4Z),),
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
    assert metadata["schema_version"] == BASIS_COMPARISON_SCHEMA_VERSION
    assert "x2c-QZVPall__dyall-v4z" in metadata["pair_outputs"]
    rows_csv = qa_root / "basis_comparisons" / "x2c-QZVPall__dyall-v4z" / "basis_comparison.csv"
    assert rows_csv.is_file()
    with rows_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["state_id"] == STATE_ID
    assert rows[0]["left_basis_id"] == "x2c-QZVPall"
    assert rows[0]["right_basis_id"] == "dyall-v4z"
    assert rows[0]["integrity_status"] == "PASS"
    assert rows[0]["comparison_tier"] == "low"
    assert rows[0]["signed_delta_electrons_trapz"]
    assert rows[0]["left_state_record_sha256"] == "digest-a"
    assert rows[0]["right_state_record_sha256"] == "digest-a"


def test_build_primary_basis_comparisons_rejects_state_digest_mismatch(
    tmp_path: Path,
) -> None:
    profiles_root = tmp_path / "profiles"
    _write_profile_dataset(
        profiles_root,
        PRIMARY_X2C_QZVPALL,
        "x2c-QZVPall",
        [4.0, 3.0, 2.0, 1.0, 0.5],
        state_digest="digest-a",
    )
    _write_profile_dataset(
        profiles_root,
        PRIMARY_DYALL_V4Z,
        "dyall-v4z",
        [4.0, 3.0, 2.0, 1.1, 0.6],
        state_digest="digest-b",
    )

    with pytest.raises(ValueError, match="state_record_sha256 mismatch"):
        build_primary_basis_comparisons(
            profiles_root=profiles_root,
            qa_root=tmp_path / "qa",
            pairs=((PRIMARY_X2C_QZVPALL, PRIMARY_DYALL_V4Z),),
            states_file=None,
            require_complete=False,
            force=True,
        )
