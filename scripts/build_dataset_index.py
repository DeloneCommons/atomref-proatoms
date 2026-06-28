#!/usr/bin/env python3
"""Build dataset-level index files from generated profile artifacts.

This command reads an existing generated dataset directory containing matching
``profiles/<state_id>.csv.zip`` and ``metadata/<state_id>.json`` files, then
writes the release-layout summary files:

``dataset_manifest.json``
``profile_index.csv``
``derived_radii.csv``
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.dataset_index import build_and_write_dataset_indexes  # noqa: E402
from atomref_proatoms.dataset_summary import (  # noqa: E402
    format_dataset_summary,
    summarize_dataset_indexes,
)
from atomref_proatoms.profile_checks import check_profile_dataset  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        required=True,
        help="Generated dataset directory containing profiles/ and metadata/ subdirectories.",
    )
    parser.add_argument(
        "--states-file",
        type=Path,
        default=ROOT / "data" / "states" / "curated" / "atom_states_v0.json",
        help="Curated state JSON used to enrich index rows.",
    )
    parser.add_argument(
        "--basis-root",
        type=Path,
        default=ROOT / "data" / "basis_sets",
        help="Frozen basis bundle root used to validate/enrich index rows.",
    )
    parser.add_argument(
        "--skip-profile-checks",
        action="store_true",
        help="Build indexes without first running check_profiles-style validation.",
    )
    parser.add_argument(
        "--require-profile-qa",
        action="store_true",
        help="Require independent electron-count and angular-sigma QA before writing indexes.",
    )
    parser.add_argument(
        "--angular-sigma-tol",
        type=float,
        default=1e-8,
        help="Tolerance for qa.max_rel_angular_sigma when profile checks are run.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a compact dataset summary after writing indexes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.skip_profile_checks:
        result = check_profile_dataset(
            args.dataset_dir,
            states_file=args.states_file,
            basis_root=args.basis_root,
            require_profile_qa=args.require_profile_qa,
            angular_sigma_tol=args.angular_sigma_tol,
        )
        if result.errors:
            print(f"ERROR: profile checks failed for {result.dataset_dir}", file=sys.stderr)
            for error in result.errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        for warning in result.warnings:
            print(f"Warning: {warning}", file=sys.stderr)

    try:
        tables = build_and_write_dataset_indexes(
            args.dataset_dir,
            states_file=args.states_file,
            basis_root=args.basis_root,
        )
    except Exception as exc:
        print(f"ERROR: failed to build dataset indexes: {exc}", file=sys.stderr)
        return 1
    print(f"OK: wrote dataset indexes for {tables.profile_count} profile(s)")
    print(f"Dataset: {tables.dataset_id}")
    print(f"Manifest: {args.dataset_dir / 'dataset_manifest.json'}")
    print(f"Profile index: {args.dataset_dir / 'profile_index.csv'}")
    print(f"Derived radii: {args.dataset_dir / 'derived_radii.csv'}")
    if args.summary:
        print()
        print(format_dataset_summary(summarize_dataset_indexes(args.dataset_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
