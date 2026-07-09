from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from atomref_proatoms.cli.main import main


def test_top_level_help(capsys) -> None:
    assert main(["--help"]) == 0
    assert "atomref-proatoms" in capsys.readouterr().out


def test_version(capsys) -> None:
    assert main(["--version"]) == 0
    assert "atomref-proatoms" in capsys.readouterr().out


def test_generate_execution_runtime_error_is_reported(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from atomref_proatoms.cli import generate as generate_cli

    def fail_execution(*_args, **_kwargs):
        raise RuntimeError("PySCF is required for generator execution")

    monkeypatch.setattr(generate_cli, "execute_generation_plan", fail_execution)
    code = main([
        "generate",
        "--elements", "C",
        "--method", "PBE0",
        "--basis", "def2-SVP",
        "--workdir", str(tmp_path),
    ])
    captured = capsys.readouterr()
    assert code == 2
    assert "PySCF is required" in captured.err


def test_generate_execution_success_is_reported_without_running_scf(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from atomref_proatoms.cli import generate as generate_cli

    manifest = tmp_path / "manifest.json"
    failures = tmp_path / "failures.csv"
    manifest.write_text("{}\n", encoding="utf-8")
    failures.write_text("stage,state_id,error\n", encoding="utf-8")

    def fake_execution(*_args, **_kwargs):
        return SimpleNamespace(
            status="ok",
            computed_scf=1,
            reused_scf=0,
            failed_jobs=0,
            manifest_path=manifest,
            failures_path=failures,
            written_files=(manifest,),
        )

    monkeypatch.setattr(generate_cli, "execute_generation_plan", fake_execution)
    code = main([
        "generate",
        "--elements", "C",
        "--method", "PBE0",
        "--basis", "def2-SVP",
        "--workdir", str(tmp_path),
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "generate execution" in captured.out
    assert "scf computed: 1" in captured.out
    assert (tmp_path / "run_config.input.json").is_file()
    assert (tmp_path / "run_config.resolved.json").is_file()
    assert (tmp_path / "plan.json").is_file()


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
