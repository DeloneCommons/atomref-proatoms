#!/usr/bin/env python3
"""Validate the curated atom-state table against the v0 schema and policy."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.exists():
    sys.path.insert(0, str(_SRC))

from atomref_proatoms.states import (  # noqa: E402
    load_atom_states,
    selection_count_summary,
    validate_state_collection,
)


def format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--states-file",
        default=Path("data/states/curated/atom_states_v0.json"),
        type=Path,
    )
    args = parser.parse_args(argv)

    try:
        states = load_atom_states(args.states_file)
        errors = validate_state_collection(states)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    summary = selection_count_summary(states)
    print(f"OK: checked {summary['state_count']} atom states")
    print(f"categories: {format_counts(summary['by_category'])}")
    print(f"charges: {format_counts(summary['by_charge'])}")
    print(f"spin_variant: {format_counts(summary['by_spin_variant'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
