from __future__ import annotations

import csv
import json

from atomref_proatoms.artifacts import write_profile_dataset_artifacts
from atomref_proatoms.report import build_report, load_profile_dataset


DATASET_ID = "pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v1"
STATE_ID = "H_q0_mult2_hund"


def _metadata() -> dict[str, object]:
    return {
        "schema_version": "atomref.proatoms.profile_dataset.v1",
        "profile_data_version": "1.0.0.dev0",
        "dataset_id": DATASET_ID,
        "basis_id": "x2c-QZVPall",
        "basis_sha256": "0" * 64,
        "density_model": "self_consistent_fractional_occupation_spherical_uks",
        "method": {
            "engine": "pyscf",
            "engine_version": "test",
            "scf_type": "UKS",
            "xc": "PBE0",
            "relativity": "sf-X2C-1e",
            "basis_id": "x2c-QZVPall",
            "basis_sha256": "0" * 64,
        },
        "units": {"r": "bohr", "rho": "electron/bohr^3"},
        "profile_grid": {"type": "log", "n": 2, "r_min_bohr": 0.1, "r_max_bohr": 0.2},
        "qa_grid": {"type": "gauss_legendre_log_r", "n": 2},
        "cutoffs_e_bohr3": [0.003, 0.001, 0.0001],
        "columns": {
            f"rho_e_bohr3__{STATE_ID}": {
                "state_id": STATE_ID,
                "symbol": "H",
                "z": 1,
                "charge": 0,
                "electron_count": 1,
                "multiplicity": 2,
            }
        },
        "states": {
            STATE_ID: {
                "symbol": "H",
                "z": 1,
                "charge": 0,
                "electron_count": 1,
                "spin_2s": 1,
                "multiplicity": 2,
                "state_category": "nist_ground_state",
                "state_role": "recommended",
            }
        },
        "derived_radii": {
            STATE_ID: {
                "r_iso_0.003_e_bohr3_bohr": 1.0,
                "r_iso_0.001_e_bohr3_bohr": 2.0,
                "r_iso_0.0001_e_bohr3_bohr": 3.0,
            }
        },
        "qa": {
            STATE_ID: {
                "scf_converged": True,
                "electron_count_error_qa": 1.0e-12,
                "electron_count_tolerance": 2.0e-6,
                "electron_count_pass": True,
                "max_rel_angular_sigma": 0.0,
                "linear_dependency_warning_count": 0,
                "linear_dependency_vectors_removed": None,
                "tail_reaches_min_cutoff": True,
                "radii_monotonic": True,
            }
        },
        "scf_artifacts": {},
        "provenance": {"profile_datasets_yaml_sha256": "1" * 64},
    }


def test_load_profile_dataset_validates_wide_csv(tmp_path) -> None:
    dataset_dir = tmp_path / DATASET_ID
    write_profile_dataset_artifacts(
        dataset_dir,
        r_bohr=[0.1, 0.2],
        densities_by_state_id={STATE_ID: [2.0, 1.0]},
        metadata=_metadata(),
    )

    dataset = load_profile_dataset(dataset_dir)

    assert dataset.dataset_id == DATASET_ID
    assert dataset.row_count == 2
    assert dataset.state_ids == [STATE_ID]


def test_build_report_writes_markdown_manifest_tables_and_svg(tmp_path) -> None:
    profiles_root = tmp_path / "profiles"
    dataset_dir = profiles_root / DATASET_ID
    write_profile_dataset_artifacts(
        dataset_dir,
        r_bohr=[0.1, 0.2],
        densities_by_state_id={STATE_ID: [2.0, 1.0]},
        metadata=_metadata(),
    )

    outputs = build_report(profiles_root=profiles_root, report_dir=tmp_path / "report")

    assert outputs["report"].read_text().startswith("# atomref-proatoms radial profiles v1.0.0.dev0")
    manifest = json.loads(outputs["manifest"].read_text())
    assert manifest["schema_version"] == "atomref.proatoms.report.v1"
    with outputs["dataset_summary"].open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["dataset_id"] == DATASET_ID
    assert outputs["electron_error_svg"].read_text().startswith("<svg")
