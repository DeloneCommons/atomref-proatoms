#!/usr/bin/env python3
"""Validate the active v2 atomic-state table.

This is the user-facing state-layer check.  It validates the existing curated
v2 JSON without rebuilding any generated state files.  Use
``scripts/build_atom_states.py`` when the compact source tables have changed and
the curated outputs need to be regenerated.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Sequence


def _load_state_builder() -> ModuleType:
    """Load the sibling build script as a module without requiring scripts/ as a package."""

    builder_path = Path(__file__).with_name("build_atom_states.py")
    spec = importlib.util.spec_from_file_location("_atomref_build_atom_states", builder_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load state builder from {builder_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/states"),
        help="Directory containing source/, selection/, and curated/ state data files.",
    )
    args = parser.parse_args(argv)

    states_file = args.data_dir / "curated" / "atom_states_v2.json"
    builder = _load_state_builder()
    return int(builder.check_curated_states(states_file))


if __name__ == "__main__":
    raise SystemExit(main())
