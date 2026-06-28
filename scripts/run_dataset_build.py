#!/usr/bin/env python3
"""Run planned profile datasets from the curated v0 state selection.

This is the full-dataset orchestration layer.  It still delegates one-state SCF
work to ``scripts/run_dataset.py`` so the single-profile path remains testable
and reusable.  By default it skips already generated state artifacts, which makes
long local builds resumable after interruptions.
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

from atomref_proatoms.build_plan import (  # noqa: E402
    ALL_V0_BUILD_PLAN,
    build_jobs_for_datasets,
    filter_build_jobs,
    format_build_plan,
)
from atomref_proatoms.datasets import DATASET_IDS  # noqa: E402
from atomref_proatoms.qa import ELECTRON_COUNT_ABS_TOL, ELECTRON_COUNT_REL_TOL  # noqa: E402
from atomref_proatoms.states import load_atom_states  # noqa: E402

RUN_DATASET = ROOT / "scripts" / "run_dataset.py"
CHECK_PROFILES = ROOT / "scripts" / "check_profiles.py"
BUILD_DATASET_INDEX = ROOT / "scripts" / "build_dataset_index.py"
PACKAGE_DATASET_OUTPUTS = ROOT / "scripts" / "package_dataset_outputs.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-id",
        action="append",
        default=[],
        help=(
            "Dataset ID to build; may be repeated. Use 'all' or 'all_v0' for all "
            "planned v0 datasets. Defaults to all_v0."
        ),
    )
    parser.add_argument(
        "--only-state-id",
        action="append",
        default=[],
        help="Restrict selected datasets to one state_id; may be repeated.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "local-data" / "profile-builds",
        help="Output root for generated profile datasets; defaults to local-data/profile-builds.",
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
        help="Ignore profile-grid angular sigma points with rho at or below this value",
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
        help="Print/validate the build plan without importing or running PySCF",
    )
    parser.add_argument(
        "--show-jobs",
        action="store_true",
        help="With --dry-run or --list, print every planned state/dataset job.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the selected build plan and exit before running anything.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run at most this many selected jobs; useful for manual chunking.",
    )
    parser.add_argument(
        "--start-after-state-id",
        default=None,
        help=(
            "Skip selected jobs through the first matching state_id, then run following jobs. "
            "If the state appears in multiple datasets, only the first selected occurrence is used."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate profiles even when profile archive and metadata already exist.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue the build if a state fails.",
    )
    parser.add_argument(
        "--check-profiles",
        action="store_true",
        help="Run scripts/check_profiles.py for affected dataset directories after generation.",
    )
    parser.add_argument(
        "--require-profile-qa",
        action="store_true",
        help="When checking/building indexes, require electron-count and angular-sigma QA.",
    )
    parser.add_argument(
        "--build-indexes",
        action="store_true",
        help=(
            "Build dataset_manifest.json, profile_index.csv, and derived_radii.csv "
            "after generation."
        ),
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print compact dataset summaries after indexes are available.",
    )
    parser.add_argument(
        "--package-release",
        action="store_true",
        help="Package affected dataset directories as a release-candidate ZIP after indexes build.",
    )
    parser.add_argument(
        "--release-archive",
        type=Path,
        default=None,
        help="Output path for --package-release; defaults beside output-dir.",
    )
    parser.add_argument(
        "--release-archive-root",
        default="data/profiles",
        help="Path prefix inside --package-release archives; defaults to data/profiles.",
    )
    parser.add_argument(
        "--check-release-package",
        action="store_true",
        help="Validate the produced release-candidate ZIP archive after packaging.",
    )
    return parser.parse_args()


def _selected_dataset_ids(values: list[str]) -> tuple[str, ...]:
    if not values:
        return DATASET_IDS
    expanded: list[str] = []
    for value in values:
        if value in {"all", ALL_V0_BUILD_PLAN}:
            expanded.extend(DATASET_IDS)
        elif value in DATASET_IDS:
            expanded.append(value)
        else:
            choices = ", ".join((*DATASET_IDS, "all", ALL_V0_BUILD_PLAN))
            raise SystemExit(f"Unknown dataset-id {value!r}; choices: {choices}")
    deduped: list[str] = []
    seen: set[str] = set()
    for dataset_id in expanded:
        if dataset_id in seen:
            continue
        seen.add(dataset_id)
        deduped.append(dataset_id)
    return tuple(deduped)


def _apply_position_filters(
    jobs: tuple[object, ...], *, start_after_state_id: str | None, limit: int | None
) -> tuple[object, ...]:
    selected = jobs
    if start_after_state_id:
        for index, job in enumerate(selected):
            if getattr(job, "state_id") == start_after_state_id:
                selected = selected[index + 1 :]
                break
        else:
            raise SystemExit(f"--start-after-state-id {start_after_state_id!r} not found")
    if limit is not None:
        if limit < 1:
            raise SystemExit("--limit must be positive")
        selected = selected[:limit]
    return selected


def _bool_flag(command: list[str], flag: str, enabled: bool) -> None:
    if enabled:
        command.append(flag)


def _artifacts_exist(output_dir: Path, dataset_id: str, state_id: str) -> bool:
    dataset_dir = output_dir / dataset_id
    metadata_path = dataset_dir / "metadata" / f"{state_id}.json"
    profile_zip = dataset_dir / "profiles" / f"{state_id}.csv.zip"
    profile_gz = dataset_dir / "profiles" / f"{state_id}.csv.gz"
    return metadata_path.exists() and (profile_zip.exists() or profile_gz.exists())


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
            "--electron-count-abs-tol",
            str(args.electron_count_abs_tol),
            "--electron-count-rel-tol",
            str(args.electron_count_rel_tol),
        ]
        _bool_flag(command, "--require-profile-qa", args.require_profile_qa)
        _bool_flag(command, "--summary", args.summary)
        print("\nBuilding dataset indexes:", " ".join(command))
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            failures += 1
            if not args.continue_on_error:
                break
    return failures


def package_release_candidate(args: argparse.Namespace, dataset_ids: set[str]) -> int:
    if not dataset_ids:
        print("No dataset directories available to package.")
        return 0
    command = [
        sys.executable,
        str(PACKAGE_DATASET_OUTPUTS),
        "--output-dir",
        str(args.output_dir),
        "--archive-root",
        args.release_archive_root,
        "--check-datasets",
        "--electron-count-abs-tol",
        str(args.electron_count_abs_tol),
        "--electron-count-rel-tol",
        str(args.electron_count_rel_tol),
    ]
    for dataset_id in sorted(dataset_ids):
        command.extend(["--dataset-id", dataset_id])
    if args.release_archive is not None:
        command.extend(["--archive", str(args.release_archive)])
    _bool_flag(command, "--require-profile-qa", args.require_profile_qa)
    _bool_flag(command, "--check-archive", args.check_release_package)
    print("\nPackaging release candidate:", " ".join(command))
    result = subprocess.run(command, cwd=ROOT, check=False)
    return result.returncode


def main() -> int:
    args = parse_args()
    if args.summary:
        args.build_indexes = True
    if args.package_release:
        args.build_indexes = True
        args.check_profiles = True
    if args.require_profile_qa and not (
        args.check_profiles or args.build_indexes or args.package_release
    ):
        raise SystemExit("--require-profile-qa requires --check-profiles or --build-indexes")
    if args.require_profile_qa and args.no_profile_qa:
        raise SystemExit("--require-profile-qa conflicts with --no-profile-qa")

    dataset_ids = _selected_dataset_ids(args.dataset_id)
    states = load_atom_states(ROOT / "data" / "states" / "curated" / "atom_states_v0.json")
    jobs = build_jobs_for_datasets(states, dataset_ids=dataset_ids)
    try:
        jobs = filter_build_jobs(jobs, only_state_ids=set(args.only_state_id) or None)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    jobs = _apply_position_filters(
        jobs, start_after_state_id=args.start_after_state_id, limit=args.limit
    )
    if not jobs:
        raise SystemExit("Selected build plan is empty")

    print(format_build_plan(jobs, show_jobs=args.show_jobs or args.list or args.dry_run))
    if args.list:
        return 0

    failures = 0
    completed_or_present_dataset_ids: set[str] = set()
    skipped = 0
    ran = 0
    for index, job in enumerate(jobs, start=1):
        prefix = f"[{index}/{len(jobs)}] {job.dataset_id} :: {job.state_id}"
        if not args.force and _artifacts_exist(args.output_dir, job.dataset_id, job.state_id):
            print(f"\n{prefix}: SKIP existing artifacts")
            skipped += 1
            completed_or_present_dataset_ids.add(job.dataset_id)
            continue
        print(f"\n{prefix}: RUN")
        command = build_run_dataset_command(args, job.state_id, job.dataset_id)
        print("Command:", " ".join(command))
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            failures += 1
            print(f"FAILED: {job.state_id} exited with status {result.returncode}")
            if not args.continue_on_error:
                return result.returncode
        else:
            ran += 1
            completed_or_present_dataset_ids.add(job.dataset_id)

    if args.check_profiles and completed_or_present_dataset_ids and not args.dry_run:
        failures += check_dataset_dirs(args, completed_or_present_dataset_ids)
    if (
        args.build_indexes
        and completed_or_present_dataset_ids
        and not args.dry_run
        and (not failures or args.continue_on_error)
    ):
        failures += build_dataset_indexes(args, completed_or_present_dataset_ids)

    print(f"\nBuild summary: ran={ran}, skipped_existing={skipped}, failures={failures}")
    if (
        args.package_release
        and completed_or_present_dataset_ids
        and not args.dry_run
        and not failures
    ):
        failures += package_release_candidate(args, completed_or_present_dataset_ids)

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
