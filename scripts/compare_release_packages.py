#!/usr/bin/env python3
"""Compare matching-state radii across release-candidate profile archives."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.release_compare import (  # noqa: E402
    DEFAULT_RADIUS_COLUMNS,
    compare_release_datasets,
    format_release_comparison,
    parse_dataset_pair,
    write_comparison_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive",
        type=Path,
        action="append",
        required=True,
        help="Release ZIP archive to compare; repeat for multiple archives.",
    )
    parser.add_argument(
        "--dataset-id",
        action="append",
        default=[],
        help="Limit loaded datasets by ID. May be repeated.",
    )
    parser.add_argument(
        "--pair",
        action="append",
        default=[],
        help="Explicit comparison pair LEFT_DATASET_ID:RIGHT_DATASET_ID. May be repeated.",
    )
    parser.add_argument(
        "--radius-column",
        action="append",
        default=[],
        help=(
            "Radius column to compare. May be repeated. Defaults to the standard "
            f"cutoffs: {', '.join(DEFAULT_RADIUS_COLUMNS)}."
        ),
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Optional long-form CSV path for per-state/per-cutoff radius deltas.",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Do not print per-cutoff summary lines.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        pairs = tuple(parse_dataset_pair(value) for value in args.pair)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    result = compare_release_datasets(
        tuple(args.archive),
        dataset_ids=tuple(args.dataset_id),
        pairs=pairs,
        radius_columns=tuple(args.radius_column) or DEFAULT_RADIUS_COLUMNS,
    )
    print(format_release_comparison(result, summary=not args.no_summary))
    if args.csv and result.ok:
        row_count = write_comparison_csv(result.comparisons, args.csv)
        print(f"CSV rows written: {row_count}")
        print(f"CSV: {args.csv}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
