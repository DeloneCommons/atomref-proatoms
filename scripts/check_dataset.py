#!/usr/bin/env python3
"""Validate a generated profile dataset including dataset-level index files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.dataset_index import check_profile_dataset_with_indexes  # noqa: E402
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
        help="Generated dataset directory containing profiles, metadata, and index files.",
    )
    parser.add_argument(
        "--states-file",
        type=Path,
        default=ROOT / "data" / "states" / "curated" / "atom_states_v0.json",
        help="Curated state JSON used to validate profile metadata.",
    )
    parser.add_argument(
        "--basis-root",
        type=Path,
        default=ROOT / "data" / "basis_sets",
        help="Frozen basis bundle root used to validate profile basis metadata.",
    )
    parser.add_argument(
        "--require-profile-qa",
        action="store_true",
        help="Fail when independent profile QA fields are null/skipped.",
    )
    parser.add_argument(
        "--angular-sigma-tol",
        type=float,
        default=1e-8,
        help="Tolerance for qa.max_rel_angular_sigma when that field is recorded.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a compact dataset summary after successful validation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile_result, index_result = check_profile_dataset_with_indexes(
        args.dataset_dir,
        states_file=args.states_file,
        basis_root=args.basis_root,
        require_profile_qa=args.require_profile_qa,
        angular_sigma_tol=args.angular_sigma_tol,
        require_indexes=True,
    )
    errors = list(profile_result.errors)
    warnings = list(profile_result.warnings)
    if index_result is not None:
        errors.extend(index_result.errors)
        warnings.extend(index_result.warnings)

    if errors:
        print(f"ERROR: dataset checks failed for {args.dataset_dir}", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        if warnings:
            print("Warnings:", file=sys.stderr)
            for warning in warnings:
                print(f"  - {warning}", file=sys.stderr)
        return 1

    print(f"OK: checked dataset under {args.dataset_dir}")
    print(f"Profiles: {profile_result.checked_profiles}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    if args.summary:
        print()
        print(format_dataset_summary(summarize_dataset_indexes(args.dataset_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
