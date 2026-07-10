from __future__ import annotations

import re
from pathlib import Path


def _extra_block(pyproject_text: str, name: str) -> set[str]:
    match = re.search(rf"^{re.escape(name)} = \[\n(?P<body>.*?)^\]", pyproject_text, re.M | re.S)
    assert match is not None, f"missing {name!r} optional-dependency block"
    body = match.group("body")
    return {line.strip().strip('",') for line in body.splitlines() if line.strip()}


def test_pyproject_has_all_extra() -> None:
    text = Path("pyproject.toml").read_text()
    all_extra = _extra_block(text, "all")
    for extra in ("generator", "audit", "dev", "docs", "release"):
        assert _extra_block(text, extra).issubset(all_extra)
