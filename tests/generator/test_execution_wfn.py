from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from atomref_proatoms.generator import execution
from atomref_proatoms.generator.execution import ExecutionOptions
from atomref_proatoms.generator.planner import GeneratorRequest, build_generation_plan


def test_write_wfn_outputs_neutral_only(monkeypatch, tmp_path: Path) -> None:
    plan = build_generation_plan(
        GeneratorRequest(
            elements=("C",),
            method="PBE0",
            relativity="x2c",
            basis="bse:x2c-QZVPall",
            state_policy="stockholder",
            charges=(-1, 0),
            artifacts=("wfn", "rad"),
            workdir=tmp_path,
            allow_unverified_basis=True,
            dry_run=True,
        )
    )
    assert any(state.charge < 0 for state in plan.state_selection.states)
    assert any(state.charge == 0 for state in plan.state_selection.states)

    monkeypatch.setattr(execution, "load_mol_from_chk", lambda _path: SimpleNamespace())
    monkeypatch.setattr(execution, "load_scf_npz", lambda _path: {})
    monkeypatch.setattr(
        execution,
        "read_scf_metadata",
        lambda _path: {"results": {"converged": True, "total_energy_hartree": -37.0}},
    )

    def fake_write_wfn(
        path: str | Path, state: Any, mol: Any, arrays: Any, **kwargs: Any
    ) -> dict[str, Any]:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("fake wfn\n", encoding="ascii")
        return {"state_id": state.state_id, "fake_writer": True}

    monkeypatch.setattr(execution, "write_atomref_scf_arrays_wfn", fake_write_wfn)

    failures: list[dict[str, Any]] = []
    paths, records = execution._write_wfn_outputs(  # noqa: SLF001
        plan,
        tmp_path,
        plan.state_selection.states,
        options=ExecutionOptions(force=True),
        failures=failures,
    )

    assert failures == []
    assert [record["format"] for record in records] == ["wfn"]
    assert records[0]["charge"] == 0
    assert records[0]["path"] == "multiwfn/wfn/C .wfn"
    assert len(paths) == 1
    assert paths[0].is_file()


def test_write_multiwfn_manifest_accepts_wfn_records(tmp_path: Path) -> None:
    plan = build_generation_plan(
        GeneratorRequest(
            elements=("C",),
            method="PBE0",
            relativity="x2c",
            basis="bse:x2c-QZVPall",
            state_policy="neutral",
            artifacts=("wfn",),
            workdir=tmp_path,
            allow_unverified_basis=True,
            dry_run=True,
        )
    )
    path = execution._write_multiwfn_manifest(  # noqa: SLF001
        plan,
        tmp_path,
        [
            {
                "format": "wfn",
                "state_id": plan.state_selection.states[0].state_id,
                "path": "multiwfn/wfn/C .wfn",
            }
        ],
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["files"][0]["format"] == "wfn"
    assert payload["notes"]["wfn"].startswith("Neutral-only")
