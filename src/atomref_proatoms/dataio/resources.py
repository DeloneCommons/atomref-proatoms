"""Installed-package service resource helpers for the generator tool.

These helpers intentionally cover only small runtime resources bundled under
``atomref_proatoms.resources``.  They are independent of the repository-root
``data/`` layout used by maintainer scripts.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources as importlib_resources
from pathlib import Path

_RESOURCE_PACKAGE = "atomref_proatoms.resources"
_ENV_RESOURCE_ROOT = "ATOMREF_PROATOMS_RESOURCE_ROOT"


def default_resource_root() -> None:
    """Return the default filesystem resource root.

    Installed-package resources are resolved via ``importlib.resources`` and do not
    necessarily have a persistent filesystem root, so the default is represented by
    ``None``.  Pass a ``Path`` explicitly, or set ``ATOMREF_PROATOMS_RESOURCE_ROOT``,
    to override resources with a development filesystem directory.
    """

    return None


def _clean_relpath(relpath: str | Path) -> str:
    value = Path(relpath).as_posix()
    if not value or value == ".":
        raise ValueError("resource relpath must be non-empty")
    if value.startswith("/") or ".." in Path(value).parts:
        raise ValueError(f"resource relpath must be relative and stay within resources: {value!r}")
    return value


def _override_root(resource_root: Path | str | None = None) -> Path | None:
    if resource_root is not None:
        return Path(resource_root).expanduser().resolve(strict=False)
    value = os.environ.get(_ENV_RESOURCE_ROOT)
    if value:
        return Path(value).expanduser().resolve(strict=False)
    return None


def _filesystem_resource(relpath: str, *, resource_root: Path | str | None = None) -> Path | None:
    root = _override_root(resource_root)
    if root is None:
        return None
    path = root / relpath
    if not path.is_file():
        raise FileNotFoundError(f"resource not found under {root}: {relpath}")
    return path


def resource_bytes(relpath: str | Path, *, resource_root: Path | str | None = None) -> bytes:
    """Read a bundled service resource as bytes."""

    cleaned = _clean_relpath(relpath)
    filesystem_path = _filesystem_resource(cleaned, resource_root=resource_root)
    if filesystem_path is not None:
        return filesystem_path.read_bytes()
    traversable = importlib_resources.files(_RESOURCE_PACKAGE).joinpath(cleaned)
    if not traversable.is_file():
        raise FileNotFoundError(f"package resource not found: {cleaned}")
    return traversable.read_bytes()


def resource_text(
    relpath: str | Path,
    *,
    resource_root: Path | str | None = None,
    encoding: str = "utf-8",
) -> str:
    """Read a bundled service resource as text."""

    return resource_bytes(relpath, resource_root=resource_root).decode(encoding)


@contextmanager
def resource_path(
    relpath: str | Path,
    *,
    resource_root: Path | str | None = None,
) -> Iterator[Path]:
    """Yield a filesystem path for a bundled service resource.

    When resources are served from a filesystem override, the original path is
    yielded directly.  Otherwise ``importlib.resources.as_file`` is used, which is
    safe for both normal wheels and zip-style importers.
    """

    cleaned = _clean_relpath(relpath)
    filesystem_path = _filesystem_resource(cleaned, resource_root=resource_root)
    if filesystem_path is not None:
        yield filesystem_path
        return
    traversable = importlib_resources.files(_RESOURCE_PACKAGE).joinpath(cleaned)
    if not traversable.is_file():
        raise FileNotFoundError(f"package resource not found: {cleaned}")
    with importlib_resources.as_file(traversable) as path:
        yield path


def resource_origin(*, resource_root: Path | str | None = None) -> dict[str, str | None]:
    """Return a JSON-friendly description of the active resource origin."""

    root = _override_root(resource_root)
    if root is None:
        return {"kind": "package", "package": _RESOURCE_PACKAGE, "root": None}
    return {"kind": "filesystem", "package": None, "root": root.as_posix()}
