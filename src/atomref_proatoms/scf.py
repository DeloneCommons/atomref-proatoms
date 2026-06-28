"""Lazy PySCF access for future generator code."""

from __future__ import annotations

from typing import Any


def import_pyscf() -> Any:
    """Import PySCF lazily and raise a clear message if it is unavailable."""

    try:
        import pyscf  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "PySCF is required only for generator operations. Install with "
            "`python -m pip install -e .[generator]`."
        ) from exc
    return pyscf
