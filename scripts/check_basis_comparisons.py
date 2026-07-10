#!/usr/bin/env python3
"""Build primary basis-family comparison QA from generated profile datasets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.dataio.datasets import load_profile_dataset_config  # noqa: E402
from atomref_proatoms.dataio.paths import (  # noqa: E402
    PROFILE_DATASETS_FILE,
    PROFILES_ROOT,
    QA_ROOT,
    STATES_FILE,
    repo_relative_path,
)
from atomref_proatoms.profiles.basis_comparison import (  # noqa: E402
    DEFAULT_MAX_CUMULATIVE_DELTA_OUTLIER_ELECTRONS,
    DEFAULT_MAX_CUMULATIVE_DELTA_WATCH_ELECTRONS,
    DEFAULT_MEAN_RADIAL_SHIFT_OUTLIER_ANGSTROM,
    DEFAULT_MEAN_RADIAL_SHIFT_WATCH_ANGSTROM,
    DEFAULT_PRIMARY_BASIS_COMPARISON_PAIRS,
    DEFAULT_RELATIVE_L1_OUTLIER,
    DEFAULT_RELATIVE_L1_WATCH,
    build_primary_basis_comparisons,
    configured_primary_basis_comparison_pairs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROFILE_DATASETS_FILE,
        help="Active dataset YAML; defaults to data/profile_datasets.yaml.",
    )
    parser.add_argument(
        "--states-file",
        type=Path,
        default=STATES_FILE,
        help="Active curated state JSON; defaults to data/states/curated/atom_states_v2.json.",
    )
    parser.add_argument(
        "--profiles-root",
        type=Path,
        default=PROFILES_ROOT,
        help="Generated profile artifact root; defaults to data/profiles.",
    )
    parser.add_argument(
        "--qa-root",
        type=Path,
        default=QA_ROOT,
        help="Generated QA artifact root; defaults to data/qa.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Allow missing selected profile directories or expected states during debugging.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing primary basis-comparison QA outputs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print configured comparison pairs and exit without writing outputs.",
    )
    parser.add_argument(
        "--watch-relative-l1",
        type=float,
        default=DEFAULT_RELATIVE_L1_WATCH,
        help="Moderate-difference threshold for relative radial-distribution L1 delta.",
    )
    parser.add_argument(
        "--outlier-relative-l1",
        type=float,
        default=DEFAULT_RELATIVE_L1_OUTLIER,
        help="High-difference threshold for relative radial-distribution L1 delta.",
    )
    parser.add_argument(
        "--watch-cumulative-electrons",
        type=float,
        default=DEFAULT_MAX_CUMULATIVE_DELTA_WATCH_ELECTRONS,
        help="Moderate-difference threshold for sup |N_right(<r)-N_left(<r)| in electrons.",
    )
    parser.add_argument(
        "--outlier-cumulative-electrons",
        type=float,
        default=DEFAULT_MAX_CUMULATIVE_DELTA_OUTLIER_ELECTRONS,
        help="High-difference threshold for sup |N_right(<r)-N_left(<r)| in electrons.",
    )
    parser.add_argument(
        "--watch-mean-shift-angstrom",
        type=float,
        default=DEFAULT_MEAN_RADIAL_SHIFT_WATCH_ANGSTROM,
        help="Moderate-difference threshold for cumulative-difference mean radial shift.",
    )
    parser.add_argument(
        "--outlier-mean-shift-angstrom",
        type=float,
        default=DEFAULT_MEAN_RADIAL_SHIFT_OUTLIER_ANGSTROM,
        help="High-difference threshold for cumulative-difference mean radial shift.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_profile_dataset_config(args.config)
    pairs = configured_primary_basis_comparison_pairs(config)
    print(f"Profile data version: {config.profile_data_version}")
    print(f"Dataset config: {repo_relative_path(args.config)}")
    print(f"State table: {repo_relative_path(args.states_file)}")
    print(f"Profile root: {repo_relative_path(args.profiles_root)}")
    print(f"QA output root: {repo_relative_path(args.qa_root)}")
    print("Primary basis-comparison pairs:")
    for left_dataset_id, right_dataset_id in pairs:
        left_present = (args.profiles_root / left_dataset_id).is_dir()
        right_present = (args.profiles_root / right_dataset_id).is_dir()
        print(
            f"  {left_dataset_id} -> {right_dataset_id} "
            f"(left_present={left_present}, right_present={right_present})"
        )
    if args.dry_run:
        return 0

    try:
        result = build_primary_basis_comparisons(
            config_path=args.config,
            states_file=args.states_file,
            profiles_root=args.profiles_root,
            qa_root=args.qa_root,
            pairs=pairs or DEFAULT_PRIMARY_BASIS_COMPARISON_PAIRS,
            require_complete=not args.allow_incomplete,
            force=args.force,
            relative_l1_watch=args.watch_relative_l1,
            relative_l1_outlier=args.outlier_relative_l1,
            max_cumulative_delta_watch_electrons=args.watch_cumulative_electrons,
            max_cumulative_delta_outlier_electrons=args.outlier_cumulative_electrons,
            mean_radial_shift_watch_angstrom=args.watch_mean_shift_angstrom,
            mean_radial_shift_outlier_angstrom=args.outlier_mean_shift_angstrom,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {repo_relative_path(result.metadata_json)}")
    print(
        "Primary basis-comparison rows: "
        f"{result.row_count} ({result.outlier_count} outliers)"
    )
    for comparison_id, outputs in sorted(result.pair_outputs.items()):
        print(
            f"  {comparison_id}: {outputs['rows_csv']} "
            f"({outputs['row_count']} rows, {outputs['outlier_count']} outliers)"
        )
    if result.skipped_pairs:
        print("Skipped comparison pairs:")
        for skipped in result.skipped_pairs:
            print(
                "  {left_dataset_id} -> {right_dataset_id}: {reason}".format(**skipped)
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
