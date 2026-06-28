#!/usr/bin/env python3
"""Run a small predefined batch of local pilot proatom profiles.

This is still pilot orchestration, not a full dataset builder.  It calls
``scripts/run_dataset.py`` for curated state/dataset pairs so Stage-5 validation
can cover the light neutral, anion/formal-anion, and heavy-element smoke systems
without copying long command lines.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.pilots import (  # noqa: E402
    DEFAULT_PILOT_GROUP,
    filter_pilots,
    get_pilot_group,
    pilot_group_names,
)
from atomref_proatoms.qa import ELECTRON_COUNT_ABS_TOL, ELECTRON_COUNT_REL_TOL  # noqa: E402

RUN_DATASET = ROOT / "scripts" / "run_dataset.py"
CHECK_PROFILES = ROOT / "scripts" / "check_profiles.py"
BUILD_DATASET_INDEX = ROOT / "scripts" / "build_dataset_index.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group",
        choices=pilot_group_names(),
        default=DEFAULT_PILOT_GROUP,
        help=f"Pilot group to run; default: {DEFAULT_PILOT_GROUP}",
    )
    parser.add_argument(
        "--only-state-id",
        action="append",
        default=[],
        help="Restrict the selected group to one state_id; may be repeated",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "local-data" / "pilot-profiles",
        help="Output root for local pilot artifacts; defaults to local-data/pilot-profiles",
    )
    parser.add_argument("--no-x2c", action="store_true", help="Disable sf-X2C for debugging only")
    parser.add_argument("--xc", default="PBE0", help="XC functional, default PBE0")
    parser.add_argument("--conv-tol", type=float, default=1e-9, help="SCF convergence tolerance")
    parser.add_argument("--max-cycle", type=int, default=100, help="Maximum SCF cycles")
    parser.add_argument("--grid-level", type=int, default=4, help="PySCF DFT grid level")
    parser.add_argument(
        "--profile-n-ang", type=int, default=110, help="Angular grid size for profiles"
    )
    parser.add_argument(
        "--no-profile-qa",
        action="store_true",
        help="Skip independent electron-count QA integration",
    )
    parser.add_argument(
        "--qa-n-r",
        type=int,
        default=400,
        help="Number of log-r radial nodes for independent electron-count QA",
    )
    parser.add_argument(
        "--qa-n-ang",
        type=int,
        default=110,
        help="Angular grid size for independent electron-count QA",
    )
    parser.add_argument(
        "--qa-r-min",
        type=float,
        default=1.0e-7,
        help="Minimum radius for independent electron-count QA",
    )
    parser.add_argument(
        "--qa-r-max",
        type=float,
        default=120.0,
        help="Maximum radius for independent electron-count QA",
    )
    parser.add_argument(
        "--angular-sigma-rho-floor",
        type=float,
        default=1.0e-8,
        help="Ignore angular sigma points with rho at or below this value",
    )
    parser.add_argument(
        "--electron-count-abs-tol",
        type=float,
        default=ELECTRON_COUNT_ABS_TOL,
        help="Absolute floor for independent electron-count QA checks after generation.",
    )
    parser.add_argument(
        "--electron-count-rel-tol",
        type=float,
        default=ELECTRON_COUNT_REL_TOL,
        help="Per-electron relative term for independent electron-count QA checks.",
    )
    parser.add_argument(
        "--profile-archive-format",
        choices=("zip", "csv.gz"),
        default="zip",
        help="Profile archive format; defaults to per-state .csv.zip archives",
    )
    parser.add_argument("--verbose", type=int, default=3, help="PySCF verbosity")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate state/dataset/basis selections without importing or running PySCF",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue the batch if a pilot state fails",
    )
    parser.add_argument(
        "--check-profiles",
        action="store_true",
        help="Run scripts/check_profiles.py for affected dataset directories after the batch",
    )
    parser.add_argument(
        "--require-profile-qa",
        action="store_true",
        help=(
            "When --check-profiles or --build-indexes is used, require electron-count "
            "and angular-sigma QA"
        ),
    )
    parser.add_argument(
        "--build-indexes",
        action="store_true",
        help=(
            "Build dataset_manifest.json, profile_index.csv, and derived_radii.csv "
            "after the batch"
        ),
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print compact dataset summaries after indexes are available.",
    )
    parser.add_argument("--list", action="store_true", help="List available pilot groups and exit")
    return parser.parse_args()


def _bool_flag(command: list[str], flag: str, enabled: bool) -> None:
    if enabled:
        command.append(flag)


def build_run_dataset_command(
    args: argparse.Namespace, state_id: str, dataset_id: str
) -> list[str]:
    command = [
        sys.executable,
        str(RUN_DATASET),
        "--state-id",
        state_id,
        "--dataset-id",
        dataset_id,
        "--output-dir",
        str(args.output_dir),
        "--xc",
        args.xc,
        "--conv-tol",
        str(args.conv_tol),
        "--max-cycle",
        str(args.max_cycle),
        "--grid-level",
        str(args.grid_level),
        "--profile-n-ang",
        str(args.profile_n_ang),
        "--qa-n-r",
        str(args.qa_n_r),
        "--qa-n-ang",
        str(args.qa_n_ang),
        "--qa-r-min",
        str(args.qa_r_min),
        "--qa-r-max",
        str(args.qa_r_max),
        "--angular-sigma-rho-floor",
        str(args.angular_sigma_rho_floor),
        "--profile-archive-format",
        args.profile_archive_format,
        "--verbose",
        str(args.verbose),
    ]
    _bool_flag(command, "--no-x2c", args.no_x2c)
    _bool_flag(command, "--no-profile-qa", args.no_profile_qa)
    _bool_flag(command, "--dry-run", args.dry_run)
    return command


def check_dataset_dirs(args: argparse.Namespace, dataset_ids: set[str]) -> int:
    failures = 0
    for dataset_id in sorted(dataset_ids):
        dataset_dir = args.output_dir / dataset_id
        command = [
            sys.executable,
            str(CHECK_PROFILES),
            "--dataset-dir",
            str(dataset_dir),
            "--electron-count-abs-tol",
            str(args.electron_count_abs_tol),
            "--electron-count-rel-tol",
            str(args.electron_count_rel_tol),
        ]
        _bool_flag(command, "--require-profile-qa", args.require_profile_qa)
        print("\nChecking generated profiles:", " ".join(command))
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            failures += 1
            if not args.continue_on_error:
                break
    return failures


def build_dataset_indexes(args: argparse.Namespace, dataset_ids: set[str]) -> int:
    failures = 0
    for dataset_id in sorted(dataset_ids):
        dataset_dir = args.output_dir / dataset_id
        command = [
            sys.executable,
            str(BUILD_DATASET_INDEX),
            "--dataset-dir",
            str(dataset_dir),
        ]
        command.extend(
            [
                "--electron-count-abs-tol",
                str(args.electron_count_abs_tol),
                "--electron-count-rel-tol",
                str(args.electron_count_rel_tol),
            ]
        )
        _bool_flag(command, "--require-profile-qa", args.require_profile_qa)
        _bool_flag(command, "--summary", args.summary)
        print("\nBuilding dataset indexes:", " ".join(command))
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            failures += 1
            if not args.continue_on_error:
                break
    return failures


def list_groups() -> None:
    for group_name in pilot_group_names():
        print(f"{group_name}:")
        for pilot in get_pilot_group(group_name):
            print(f"  {pilot.state_id} -> {pilot.dataset_id}  # {pilot.label}")


def main() -> int:
    args = parse_args()
    if args.summary:
        args.build_indexes = True
    if args.require_profile_qa and not (args.check_profiles or args.build_indexes):
        raise SystemExit("--require-profile-qa requires --check-profiles or --build-indexes")
    if args.require_profile_qa and args.no_profile_qa:
        raise SystemExit("--require-profile-qa conflicts with --no-profile-qa")
    if args.list:
        list_groups()
        return 0

    try:
        pilots = filter_pilots(
            get_pilot_group(args.group), only_state_ids=set(args.only_state_id) or None
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not pilots:
        raise SystemExit(f"Pilot group {args.group!r} is empty")

    print(f"Running pilot group {args.group!r} with {len(pilots)} state(s).")
    failures = 0
    completed_dataset_ids: set[str] = set()
    for index, pilot in enumerate(pilots, start=1):
        print(f"\n[{index}/{len(pilots)}] {pilot.state_id}: {pilot.label}")
        command = build_run_dataset_command(args, pilot.state_id, pilot.dataset_id)
        print("Command:", " ".join(command))
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            failures += 1
            print(f"FAILED: {pilot.state_id} exited with status {result.returncode}")
            if not args.continue_on_error:
                return result.returncode
        else:
            completed_dataset_ids.add(pilot.dataset_id)

    if args.check_profiles and completed_dataset_ids and not args.dry_run:
        failures += check_dataset_dirs(args, completed_dataset_ids)
    if args.build_indexes and completed_dataset_ids and not args.dry_run and not failures:
        failures += build_dataset_indexes(args, completed_dataset_ids)
    if failures:
        print(f"Pilot batch completed with {failures} failure(s).")
        return 1
    print("Pilot batch completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
