#!/usr/bin/env python3
"""Compute or inspect the configured spherical-atom SCF wavefunction plan.

The current implementation provides the v1 configuration-driven planning surface and
no-PySCF dry-run/list mode.  The next generator patch will attach persistent
``local-data/scf/<dataset_id>/<state_id>/`` checkpoint/NPZ/JSON/log writers to this
entry point.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.build_plan import (  # noqa: E402
    ALL_PROFILE_DATASETS,
    ALL_V1_BUILD_PLAN,
    build_jobs_for_datasets,
    filter_build_jobs,
    format_build_plan,
)
from atomref_proatoms.datasets import DATASET_IDS, load_profile_dataset_config  # noqa: E402
from atomref_proatoms.paths import PROFILE_DATASETS_FILE, SCF_ROOT, STATES_FILE  # noqa: E402
from atomref_proatoms.states import load_atom_states  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROFILE_DATASETS_FILE,
        help="Profile dataset YAML; defaults to data/profile_datasets.yaml.",
    )
    parser.add_argument(
        "--dataset",
        "--dataset-id",
        dest="dataset_ids",
        action="append",
        default=[],
        help=(
            "Dataset ID to compute; may be repeated. Use 'all' or 'all_v1' for all "
            "configured v1 datasets. Defaults to all datasets."
        ),
    )
    parser.add_argument(
        "--state",
        "--state-id",
        dest="state_ids",
        action="append",
        default=[],
        help="Restrict selected datasets to one state_id; may be repeated.",
    )
    parser.add_argument(
        "--scf-root",
        type=Path,
        default=SCF_ROOT,
        help="Local SCF artifact root; defaults to local-data/scf.",
    )
    parser.add_argument("--resume", action="store_true", help="Reuse matching local SCF artifacts.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate SCF artifacts even when matching local artifacts exist.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the selected wavefunction plan and exit before running PySCF.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate/print the plan and exit before importing or running PySCF.",
    )
    parser.add_argument(
        "--show-jobs",
        action="store_true",
        help="Print every selected state/dataset job.",
    )
    return parser.parse_args()


def _selected_dataset_ids(values: list[str], configured_ids: tuple[str, ...]) -> tuple[str, ...]:
    if not values:
        return configured_ids
    expanded: list[str] = []
    aliases = {ALL_PROFILE_DATASETS, ALL_V1_BUILD_PLAN}
    for value in values:
        if value in aliases:
            expanded.extend(configured_ids)
        elif value in configured_ids:
            expanded.append(value)
        else:
            choices = ", ".join((*configured_ids, *sorted(aliases)))
            raise SystemExit(f"Unknown dataset {value!r}; choices: {choices}")
    deduped: list[str] = []
    seen: set[str] = set()
    for dataset_id in expanded:
        if dataset_id in seen:
            continue
        seen.add(dataset_id)
        deduped.append(dataset_id)
    return tuple(deduped)


def main() -> int:
    args = parse_args()
    config = load_profile_dataset_config(args.config)
    dataset_ids = _selected_dataset_ids(args.dataset_ids, config.dataset_ids or DATASET_IDS)
    states = load_atom_states(STATES_FILE)
    jobs = build_jobs_for_datasets(states, dataset_ids=dataset_ids, config=config)
    try:
        jobs = filter_build_jobs(jobs, only_state_ids=set(args.state_ids) or None)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not jobs:
        raise SystemExit("Selected wavefunction plan is empty")

    print(f"Profile data version: {config.profile_data_version}")
    print(f"Dataset config: {args.config}")
    print(f"SCF artifact root: {args.scf_root}")
    print(
        format_build_plan(
            jobs, show_jobs=args.show_jobs or args.list or args.dry_run, config=config
        )
    )

    if args.list or args.dry_run:
        print("Dry run completed before PySCF import/SCF execution.")
        return 0

    raise SystemExit(
        "Persistent SCF artifact generation is not implemented in this patch yet. "
        "Use --dry-run/--list for plan validation."
    )


if __name__ == "__main__":
    raise SystemExit(main())
