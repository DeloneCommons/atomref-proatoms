from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from atomref_proatoms.generator import execution
from atomref_proatoms.generator.execution import ExecutionOptions
from atomref_proatoms.generator.planner import GeneratorRequest, build_generation_plan


def test_resume_with_force_reuses_matching_scf(monkeypatch, tmp_path: Path) -> None:
    plan = build_generation_plan(
        GeneratorRequest(
            elements=("H",),
            method="HF",
            relativity="none",
            basis="STO-3G",
            state_policy="neutral",
            artifacts=("profiles", "rad"),
            workdir=tmp_path,
            dry_run=True,
        )
    )
    monkeypatch.setattr(execution, "scf_fingerprints", lambda **_kwargs: {})
    monkeypatch.setattr(execution, "scf_artifact_is_reusable", lambda *_args: True)

    def unexpected_scf(**_kwargs: Any) -> Any:
        raise AssertionError("matching SCF cache should have been reused")

    monkeypatch.setattr(execution, "_build_atom_mol", unexpected_scf)

    status = execution._ensure_scf_artifacts(  # noqa: SLF001
        plan=plan,
        state=plan.state_selection.states[0],
        basis_check=plan.basis_check,
        pyscf_version="2.13.1",
        options=ExecutionOptions(resume=True, force=True),
    )

    assert status == "reused"


def test_ecp_state_metadata_uses_explicit_density_electron_count(tmp_path: Path) -> None:
    state = SimpleNamespace(
        symbol="Cu",
        z=29,
        charge=0,
        electron_count=29,
        spin_2s=1,
        multiplicity=2,
        record={
            "configuration": "[Ar] 3d10 4s1",
            "spin_model": "term_multiplicity",
            "spin_variant": "curated_multiplicity",
            "occupation_policy": "spherical_fractional",
            "state_category": "nist_reference",
            "state_role": "reference",
            "curation_status": "curated",
        },
    )

    metadata = execution._state_metadata(  # noqa: SLF001
        state,
        {"results": {"nelectron": 19, "effective_core_electrons": 10}},
    )

    assert metadata["electron_count"] == 19
    assert metadata["explicit_electron_count"] == 19
    assert metadata["state_electron_count"] == 29
    assert metadata["effective_core_electrons"] == 10

    qa_csv, _metadata_json = execution.write_qa_dataset_artifacts(
        tmp_path / "qa",
        dataset_id="pbe0_none_pyscf_lanl2dz_neutral",
        profile_data_version="2.0.0",
        basis_id="pyscf:LANL2DZ",
        states={"Cu_q0_mult2_nist": metadata},
        qa_by_state_id={
            "Cu_q0_mult2_nist": {
                "scf_converged": True,
                "electron_count_error_qa": 1.0e-12,
                "electron_count_tolerance": 3.8e-6,
                "electron_count_pass": True,
                "max_rel_angular_sigma": 0.0,
                "max_rel_angular_sigma_tolerance": 1.0e-8,
                "angular_sigma_pass": True,
                "tail_reaches_min_cutoff": True,
                "radii_monotonic": True,
                "linear_dependency_warning_count": 0,
                "linear_dependency_vectors_removed": 0,
            }
        },
        source_profiles_csv="profiles/profiles.csv",
        source_metadata_json="profiles/metadata.json",
    )
    with qa_csv.open(newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["electron_count"] == "19"
