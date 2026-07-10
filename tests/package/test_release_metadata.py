from __future__ import annotations

from pathlib import Path

import yaml

from atomref_proatoms import __version__


def test_citation_metadata_matches_package_version() -> None:
    citation = yaml.safe_load(Path("CITATION.cff").read_text(encoding="utf-8"))
    assert citation["cff-version"] == "1.2.0"
    assert citation["version"] == __version__
    assert str(citation["date-released"]) == "2026-07-10"
    assert citation["type"] == "software"
    assert citation["repository-code"].endswith("/atomref-proatoms")
    assert {"MIT", "CC-BY-4.0"}.issubset(citation["license"])


def test_changelog_has_current_version() -> None:
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## {__version__} -" in changelog
