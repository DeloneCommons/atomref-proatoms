#!/usr/bin/env python3
"""Validate generated local pilot-output roots across one or more pilot groups."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.pilot_outputs import (  # noqa: E402
    check_pilot_output_root,
    format_pilot_output_check,
)
from atomref_proatoms.pilots import DEFAULT_PILOT_GROUP, pilot_group_names  # noqa: E402
from atomref_proatoms.qa import ELECTRON_COUNT_ABS_TOL, ELECTRON_COUNT_REL_TOL  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "local-data" / "pilot-profiles",
        help="Pilot output root; defaults to local-data/pilot-profiles.",
    )
    parser.add_argument(
        "--group",
        action="append",
        choices=pilot_group_names(),
        default=[],
        help=(
            f"Pilot group to validate; may be repeated. Defaults to {DEFAULT_PILOT_GROUP}."
        ),
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
        "--electron-count-abs-tol",
        type=float,
        default=ELECTRON_COUNT_ABS_TOL,
        help="Absolute floor for independent electron-count QA tolerance.",
    )
    parser.add_argument(
        "--electron-count-rel-tol",
        type=float,
        default=ELECTRON_COUNT_REL_TOL,
        help="Per-electron relative term for independent electron-count QA tolerance.",
    )
    parser.add_argument(
        "--no-require-indexes",
        action="store_true",
        help="Do not require dataset_manifest/profile_index/derived_radii files.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Warn instead of failing when an expected dataset directory is missing.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print compact dataset summaries for checked datasets.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    groups = tuple(args.group) or (DEFAULT_PILOT_GROUP,)
    result = check_pilot_output_root(
        args.output_dir,
        group_names=groups,
        states_file=args.states_file,
        basis_root=args.basis_root,
        require_profile_qa=args.require_profile_qa,
        angular_sigma_tol=args.angular_sigma_tol,
        electron_count_abs_tol=args.electron_count_abs_tol,
        electron_count_rel_tol=args.electron_count_rel_tol,
        require_indexes=not args.no_require_indexes,
        allow_missing=args.allow_missing,
        include_summaries=args.summary,
    )
    print(format_pilot_output_check(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
