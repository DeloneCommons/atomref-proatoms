from __future__ import annotations

from atomref_proatoms.generator.workspace import (
    WorkspaceContext,
    check_or_initialize_workspace,
    read_workspace_context,
)


def test_workspace_initializes_and_detects_conflict(tmp_path) -> None:
    context = WorkspaceContext(
        method="PBE0",
        relativity="x2c",
        basis_key="bse:x2c-QZVPall",
        state_policy="neutral",
    )
    status = check_or_initialize_workspace(tmp_path, context)
    assert status.status == "initialized"
    assert read_workspace_context(tmp_path) == context
    assert check_or_initialize_workspace(tmp_path, context).status == "compatible"

    other = WorkspaceContext(
        method="HF",
        relativity="x2c",
        basis_key="bse:x2c-QZVPall",
        state_policy="neutral",
    )
    conflict = check_or_initialize_workspace(tmp_path, other)
    assert conflict.status == "conflict"
    assert "different --workdir" in conflict.message
