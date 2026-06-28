#!/usr/bin/env python3
"""Package selected local pilot-output datasets into a ZIP archive."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.pilot_package import (  # noqa: E402
    default_pilot_archive_path,
    format_pilot_output_package,
    package_pilot_outputs,
)
from atomref_proatoms.pilots import FULL_PILOT_SUITE, pilot_group_names  # noqa: E402


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
            f"Pilot group to package; may be repeated. Defaults to {FULL_PILOT_SUITE}."
        ),
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=None,
        help="Output ZIP path; defaults to local-data/pilot-profiles-<groups>.zip.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Warn instead of failing when an expected selected dataset directory is missing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    groups = tuple(args.group) or (FULL_PILOT_SUITE,)
    archive_path = args.archive or default_pilot_archive_path(args.output_dir, groups)
    try:
        result = package_pilot_outputs(
            args.output_dir,
            archive_path,
            group_names=groups,
            allow_missing=args.allow_missing,
        )
    except Exception as exc:
        raise SystemExit(str(exc)) from exc
    print(format_pilot_output_package(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
