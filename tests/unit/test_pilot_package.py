from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

from atomref_proatoms.datasets import (
    ANION_DYALL_AV4Z,
    ANION_X2C_QZVPALL_S,
    PRIMARY_DYALL_V4Z,
    PRIMARY_X2C_QZVPALL,
)
from atomref_proatoms.pilot_package import (
    default_pilot_archive_path,
    package_pilot_outputs,
)
from atomref_proatoms.pilots import FULL_PILOT_SUITE, H_SMOKE

ROOT = Path(__file__).resolve().parents[2]


def _write_dummy_dataset(output_dir: Path, dataset_id: str) -> None:
    metadata_dir = output_dir / dataset_id / "metadata"
    profiles_dir = output_dir / dataset_id / "profiles"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "dummy.json").write_text("{}\n", encoding="utf-8")
    (profiles_dir / "dummy.csv.zip").write_bytes(b"dummy")


def test_default_pilot_archive_path_uses_group_label(tmp_path: Path) -> None:
    output_dir = tmp_path / "pilot-profiles"

    archive = default_pilot_archive_path(output_dir, (FULL_PILOT_SUITE,))

    assert archive == tmp_path / "pilot-profiles-full_pilot_suite.zip"


def test_package_pilot_outputs_includes_only_selected_datasets(tmp_path: Path) -> None:
    output_dir = tmp_path / "pilot-profiles"
    _write_dummy_dataset(output_dir, PRIMARY_X2C_QZVPALL)
    _write_dummy_dataset(output_dir, ANION_X2C_QZVPALL_S)
    archive_path = tmp_path / "h-smoke.zip"

    result = package_pilot_outputs(output_dir, archive_path, group_names=(H_SMOKE,))

    assert result.file_count == 2
    assert result.dataset_ids == (PRIMARY_X2C_QZVPALL,)
    with ZipFile(archive_path) as zip_handle:
        names = sorted(zip_handle.namelist())
    assert names == [
        f"{PRIMARY_X2C_QZVPALL}/metadata/dummy.json",
        f"{PRIMARY_X2C_QZVPALL}/profiles/dummy.csv.zip",
    ]


def test_package_pilot_outputs_cli_full_suite(tmp_path: Path) -> None:
    output_dir = tmp_path / "pilot-profiles"
    for dataset_id in (
        PRIMARY_X2C_QZVPALL,
        ANION_X2C_QZVPALL_S,
        ANION_DYALL_AV4Z,
        PRIMARY_DYALL_V4Z,
    ):
        _write_dummy_dataset(output_dir, dataset_id)
    archive_path = tmp_path / "full.zip"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/package_pilot_outputs.py",
            "--output-dir",
            str(output_dir),
            "--archive",
            str(archive_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "full_pilot_suite" in result.stdout
    assert "Files packaged: 8" in result.stdout
    assert archive_path.exists()
