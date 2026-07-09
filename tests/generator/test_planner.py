from __future__ import annotations

import json
from pathlib import Path

from atomref_proatoms.generator.planner import (
    GeneratorRequest,
    build_generation_plan,
    parse_artifacts,
    resolve_requested_elements,
    write_dry_run_files,
)


def test_parse_artifacts_expands_all() -> None:
    defaults = {"default_artifacts": ["profiles", "rad"]}
    assert parse_artifacts(None, defaults=defaults) == ("profiles", "rad")
    assert parse_artifacts("all", defaults=defaults) == ("profiles", "rad", "wfn")
    assert parse_artifacts("rad,wfn", defaults=defaults) == ("rad", "wfn")


def test_resolve_requested_elements_combines_list_and_range() -> None:
    assert resolve_requested_elements(elements=("C",), element_range="H-He") == ("C", "H", "He")


def test_build_generation_plan_dry_run_without_scf(tmp_path: Path) -> None:
    request = GeneratorRequest(
        elements=("C", "O"),
        method="PBE0",
        relativity="x2c",
        basis="bse:x2c-QZVPall",
        state_policy="neutral",
        artifacts=("profiles", "rad"),
        workdir=tmp_path,
        dry_run=True,
    )
    plan = build_generation_plan(request)
    assert plan.run_id == "pbe0_x2c_bse_x2c-qzvpall_neutral"
    assert plan.state_selection.state_ids
    assert len(plan.jobs) == 2
    assert all(job["wfn_eligible"] for job in plan.jobs)
    assert all(
        str(job["output_paths"]["scf_dir"]).startswith(f"scf/{plan.run_id}/")
        for job in plan.jobs
    )
    paths = write_dry_run_files(plan)
    for path in paths.values():
        assert path.is_file()
    payload = json.loads((tmp_path / "plan.json").read_text())
    assert payload["selected_state_count"] == 2
    assert payload["would_write"]["multiwfn_dir"].endswith("multiwfn")


def test_build_generation_plan_accepts_hf_backend(tmp_path: Path) -> None:
    request = GeneratorRequest(
        elements=("H",),
        method="hf",
        relativity="none",
        basis="def2-SVP",
        state_policy="neutral",
        artifacts=("profiles",),
        workdir=tmp_path,
        dry_run=True,
    )
    plan = build_generation_plan(request)

    assert plan.method.method_kind == "hf"
    assert plan.method.scf_type == "UHF"
    assert plan.jobs[0]["method_kind"] == "hf"


def test_wfn_only_non_neutral_selection_records_error(tmp_path: Path) -> None:
    request = GeneratorRequest(
        elements=("C",),
        method="PBE0",
        relativity="x2c",
        basis="def2-SVP",
        state_policy="stockholder",
        charges=(-1,),
        artifacts=("wfn",),
        workdir=tmp_path,
        dry_run=True,
    )
    plan = build_generation_plan(request)
    assert any("WFN-only" in error for error in plan.errors)
    assert plan.jobs[0]["artifacts"] == []
    assert "scf_dir" not in plan.jobs[0]["output_paths"]
