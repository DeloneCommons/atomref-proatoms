#!/usr/bin/env python3
"""Validate generated atomref-proatoms profile artifacts.

This command checks one generated dataset directory containing matching
``profiles/<state_id>.csv.zip`` (or legacy ``.csv.gz``) and
``metadata/<state_id>.json`` files.  It is intended for local pilot outputs and
future release checks; it does not run PySCF.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
        if result.warnings:
            print("Warnings:", file=sys.stderr)
            for warning in result.warnings:
                print(f"  - {warning}", file=sys.stderr)
        return 1

    print(f"OK: checked {result.checked_profiles} profile artifacts under {result.dataset_dir}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
