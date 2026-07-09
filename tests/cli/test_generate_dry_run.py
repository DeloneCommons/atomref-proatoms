from __future__ import annotations

import json
from pathlib import Path

from atomref_proatoms.cli.main import main


def test_top_level_help(capsys) -> None:
    assert main(["--help"]) == 0
    assert "atomref-proatoms" in capsys.readouterr().out


def test_version(capsys) -> None:
    assert main(["--version"]) == 0
    assert "atomref-proatoms" in capsys.readouterr().out


def test_generate_without_optional_pyscf_reports_execution_dependency(
    tmp_path: Path, capsys
) -> None:
    code = main([
        "generate",
        "--elements", "C",
        "--method", "PBE0",
        "--basis", "def2-SVP",
        "--workdir", str(tmp_path),
    ])
    captured = capsys.readouterr()
    assert code == 2
    assert (
        "could not be resolved for execution" in captured.err
        or "PySCF is required" in captured.err
    )
    assert not (tmp_path / "plan.json").exists()


def test_generate_dry_run_writes_plan(tmp_path: Path, capsys) -> None:
    code = main([
        "generate",
        "--elements", "C,N,O",
        "--method", "PBE0",
        "--relativity", "x2c",
        "--basis", "bse:x2c-QZVPall",
        "--state-policy", "neutral",
        "--artifacts", "profiles,rad",
        "--workdir", str(tmp_path),
        "--dry-run",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "generate dry run" in captured.out
    assert (tmp_path / "atomref_proatoms_workspace.json").is_file()
    plan = json.loads((tmp_path / "plan.json").read_text())
    assert plan["selected_state_count"] == 3
    assert plan["artifacts"] == ["profiles", "rad"]
    assert len(plan["jobs"]) == 3
