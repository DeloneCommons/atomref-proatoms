from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_check_states_script_validates_active_v2_table() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_states.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "OK: checked 501 atom states" in result.stdout
    assert "formal_anion_reference=40" in result.stdout
    assert "ning2022_monoanion_reference=72" in result.stdout
    assert "nist_reference=389" in result.stdout
