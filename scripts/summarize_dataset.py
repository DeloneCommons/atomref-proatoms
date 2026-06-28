#!/usr/bin/env python3
"""Print a compact summary of a generated profile dataset.

The dataset must already contain ``dataset_manifest.json``, ``profile_index.csv``,
and ``derived_radii.csv``.  Build those files first with
``scripts/build_dataset_index.py`` or ``scripts/run_pilots.py --build-indexes``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.dataset_summary import (  # noqa: E402
    format_dataset_summary,
    summarize_dataset_indexes,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        required=True,
        help="Generated dataset directory containing dataset-level index files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = summarize_dataset_indexes(args.dataset_dir)
    except Exception as exc:
        print(f"ERROR: failed to summarize dataset: {exc}", file=sys.stderr)
        return 1
    print(format_dataset_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
