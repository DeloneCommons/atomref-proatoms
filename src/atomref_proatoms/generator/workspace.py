"""Workspace marker helpers for generator work directories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WORKSPACE_MARKER = "atomref_proatoms_workspace.json"
WORKSPACE_SCHEMA_VERSION = "atomref.proatoms.generator_workspace.v1"


@dataclass(frozen=True)
class WorkspaceContext:
    """The scientific context pinned to one generator workdir."""

    method: str
    relativity: str
    basis_key: str
    state_policy: str

    def as_dict(self) -> dict[str, str]:
        return {
            "method": self.method,
            "relativity": self.relativity,
            "basis_key": self.basis_key,
            "state_policy": self.state_policy,
        }


@dataclass(frozen=True)
class WorkspaceStatus:
    """Result of opening or checking a workdir."""

    workdir: Path
    marker_path: Path
    status: str
    context: WorkspaceContext
    existing_context: WorkspaceContext | None = None
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "workdir": self.workdir.as_posix(),
            "marker_path": self.marker_path.as_posix(),
            "status": self.status,
            "context": self.context.as_dict(),
            "existing_context": (
                self.existing_context.as_dict() if self.existing_context is not None else None
            ),
            "message": self.message,
        }


def workspace_marker_path(workdir: Path | str) -> Path:
    return Path(workdir).expanduser() / WORKSPACE_MARKER


def _read_marker(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _context_from_mapping(data: dict[str, Any]) -> WorkspaceContext:
    return WorkspaceContext(
        method=str(data["method"]),
        relativity=str(data["relativity"]),
        basis_key=str(data["basis_key"]),
        state_policy=str(data["state_policy"]),
    )


def read_workspace_context(workdir: Path | str) -> WorkspaceContext | None:
    """Return the pinned context if a workdir marker exists."""

    path = workspace_marker_path(workdir)
    if not path.exists():
        return None
    data = _read_marker(path)
    if data.get("schema_version") != WORKSPACE_SCHEMA_VERSION:
        raise ValueError(f"unexpected workspace schema_version in {path}")
    context = data.get("context")
    if not isinstance(context, dict):
        raise ValueError(f"workspace marker is missing context object: {path}")
    return _context_from_mapping(context)


def write_workspace_marker(workdir: Path | str, context: WorkspaceContext) -> Path:
    """Initialize or replace a workspace marker."""

    root = Path(workdir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    path = workspace_marker_path(root)
    data = {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "context": context.as_dict(),
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def check_or_initialize_workspace(
    workdir: Path | str,
    context: WorkspaceContext,
    *,
    initialize: bool = True,
) -> WorkspaceStatus:
    """Check that a workdir context is compatible, initializing when absent."""

    root = Path(workdir).expanduser()
    marker = workspace_marker_path(root)
    existing = read_workspace_context(root)
    if existing is None:
        if initialize:
            marker = write_workspace_marker(root, context)
            return WorkspaceStatus(
                workdir=root,
                marker_path=marker,
                status="initialized",
                context=context,
                message="workspace marker initialized",
            )
        return WorkspaceStatus(
            workdir=root,
            marker_path=marker,
            status="missing",
            context=context,
            message="workspace marker does not exist",
        )
    if existing == context:
        return WorkspaceStatus(
            workdir=root,
            marker_path=marker,
            status="compatible",
            context=context,
            existing_context=existing,
            message="workspace context is compatible",
        )
    message = (
        "workdir context mismatch: existing "
        f"{existing.as_dict()} != requested {context.as_dict()}; use a different --workdir"
    )
    return WorkspaceStatus(
        workdir=root,
        marker_path=marker,
        status="conflict",
        context=context,
        existing_context=existing,
        message=message,
    )


def require_compatible_workspace(workdir: Path | str, context: WorkspaceContext) -> WorkspaceStatus:
    """Check or initialize a workdir and raise on context conflict."""

    status = check_or_initialize_workspace(workdir, context, initialize=True)
    if status.status == "conflict":
        raise ValueError(status.message)
    return status
