from __future__ import annotations

import json
from pathlib import Path

from atomref_proatoms.dataio.resources import resource_origin, resource_path, resource_text


def test_package_resource_text_reads_curated_states() -> None:
    text = resource_text("states/atom_states_v2.json")
    records = json.loads(text)
    assert isinstance(records, list)
    assert len(records) == 501
    assert records[0]["state_id"]


def test_resource_path_supports_filesystem_override(tmp_path: Path) -> None:
    root = tmp_path / "resources"
    (root / "states").mkdir(parents=True)
    path = root / "states" / "atom_states_v2.json"
    path.write_text("[]\n", encoding="utf-8")

    with resource_path("states/atom_states_v2.json", resource_root=root) as resolved:
        assert resolved == path.resolve(strict=False)
        assert resolved.read_text(encoding="utf-8") == "[]\n"

    assert resource_origin(resource_root=root)["kind"] == "filesystem"
