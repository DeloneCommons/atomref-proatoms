from __future__ import annotations

import json
import sys
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


def test_generate_dry_run_accepts_separated_signed_charge_list(tmp_path: Path, capsys) -> None:
    code = main([
        "generate",
        "--elements", "C",
        "--method", "PBE0",
        "--basis", "STO-3G",
        "--state-policy", "stockholder",
        "--charges", "-1,0,+1",
        "--artifacts", "profiles",
        "--workdir", str(tmp_path),
        "--dry-run",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "selected states: 3" in captured.out
    plan = json.loads((tmp_path / "plan.json").read_text())
    assert plan["selected_state_count"] == 3


def test_generate_entry_point_accepts_separated_signed_charge_list(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "atomref-proatoms",
            "generate",
            "--elements",
            "C",
            "--method",
            "PBE0",
            "--basis",
            "STO-3G",
            "--state-policy",
            "stockholder",
            "--charges",
            "-1,0,+1",
            "--artifacts",
            "profiles",
            "--workdir",
            str(tmp_path),
            "--dry-run",
        ],
    )

    code = main()

    captured = capsys.readouterr()
    assert code == 0
    assert "selected states: 3" in captured.out


def test_generate_rejects_invalid_rad_angular_points_before_planning(
    tmp_path: Path, capsys
) -> None:
    code = main([
        "generate",
        "--elements", "H",
        "--method", "PBE0",
        "--basis", "STO-3G",
        "--rad-angular-points", "3",
        "--workdir", str(tmp_path),
        "--dry-run",
    ])
    captured = capsys.readouterr()
    assert code == 2
    assert "--rad-angular-points" in captured.err
    assert not (tmp_path / "plan.json").exists()


def test_generate_rejects_invalid_rad_eval_chunk_size_before_planning(
    tmp_path: Path, capsys
) -> None:
    code = main([
        "generate",
        "--elements", "H",
        "--method", "PBE0",
        "--basis", "STO-3G",
        "--rad-eval-chunk-size", "0",
        "--workdir", str(tmp_path),
        "--dry-run",
    ])
    captured = capsys.readouterr()
    assert code == 2
    assert "--rad-eval-chunk-size" in captured.err
    assert not (tmp_path / "plan.json").exists()


def test_generate_rejects_invalid_scf_controls_before_planning(
    tmp_path: Path, capsys
) -> None:
    code = main([
        "generate",
        "--elements", "H",
        "--method", "HF",
        "--basis", "STO-3G",
        "--max-cycle", "0",
        "--workdir", str(tmp_path),
        "--dry-run",
    ])

    captured = capsys.readouterr()
    assert code == 2
    assert "--max-cycle" in captured.err
    assert not (tmp_path / "plan.json").exists()


def test_generate_dry_run_records_effective_runtime_controls(tmp_path: Path) -> None:
    code = main([
        "generate",
        "--elements", "H",
        "--method", "HF",
        "--basis", "STO-3G",
        "--conv-tol", "1e-10",
        "--max-cycle", "125",
        "--diis-space", "8",
        "--diis-start-cycle", "0",
        "--grid-level", "0",
        "--verbose", "1",
        "--rad-angular-points", "14",
        "--rad-eval-chunk-size", "2048",
        "--resume",
        "--force",
        "--quiet-scf-log",
        "--workdir", str(tmp_path),
        "--dry-run",
    ])

    assert code == 0
    input_config = json.loads((tmp_path / "run_config.input.json").read_text())
    resolved = json.loads((tmp_path / "run_config.resolved.json").read_text())
    plan = json.loads((tmp_path / "plan.json").read_text())
    assert input_config["max_cycle"] == 125
    assert resolved["scf_settings"] == {
        "engine": "pyscf",
        "expected_engine_version": "2.13.1",
        "conv_tol": 1.0e-10,
        "max_cycle": 125,
        "diis_space": 8,
        "diis_start_cycle": 0,
        "grid_level": 0,
        "verbose": 1,
    }
    assert resolved["execution_policy"]["rad_angular_points"] == 14
    assert resolved["execution_policy"]["rad_eval_chunk_size"] == 2048
    assert resolved["execution_policy"]["resume"] is True
    assert resolved["execution_policy"]["force"] is True
    assert plan["scf_settings"] == resolved["scf_settings"]
    assert plan["execution_policy"] == resolved["execution_policy"]


def test_generate_reports_file_workdir_without_traceback(
    tmp_path: Path, capsys
) -> None:
    workdir = tmp_path / "not-a-directory"
    workdir.write_text("occupied\n", encoding="utf-8")

    code = main([
        "generate",
        "--elements", "H",
        "--method", "HF",
        "--basis", "STO-3G",
        "--workdir", str(workdir),
        "--dry-run",
    ])

    captured = capsys.readouterr()
    assert code == 2
    assert "not a directory" in captured.err
    assert "Traceback" not in captured.err
