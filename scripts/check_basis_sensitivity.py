#!/usr/bin/env python3
"""Build optional diffuse-basis sensitivity QA from generated profile datasets."""

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
    repo_relative_path,
)
from atomref_proatoms.profiles.basis_sensitivity import (  # noqa: E402
    DEFAULT_WARN_DELTA_RADIUS_ANGSTROM,
    DEFAULT_WARN_RELATIVE_L1,
    build_basis_sensitivity_qa,
    configured_basis_sensitivity_pairs,
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
        "--force",
        action="store_true",
        help="Overwrite existing basis-sensitivity QA outputs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print configured comparison pairs and exit without writing outputs.",
    )
    parser.add_argument(
        "--warn-relative-l1",
        type=float,
        default=DEFAULT_WARN_RELATIVE_L1,
        help="Warning threshold for integrated relative L1 density delta.",
    )
    parser.add_argument(
        "--warn-delta-radius-angstrom",
        type=float,
        default=DEFAULT_WARN_DELTA_RADIUS_ANGSTROM,
        help="Warning threshold for absolute radius shifts in Angstrom.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_profile_dataset_config(args.config)
    pairs = configured_basis_sensitivity_pairs(config)
    print(f"Profile data version: {config.profile_data_version}")
    print(f"Dataset config: {repo_relative_path(args.config)}")
    print(f"Profile root: {repo_relative_path(args.profiles_root)}")
    print(f"QA output root: {repo_relative_path(args.qa_root)}")
    print("Basis-sensitivity pairs:")
    for base_dataset_id, diffuse_dataset_id in pairs:
        base_present = (args.profiles_root / base_dataset_id).is_dir()
        diffuse_present = (args.profiles_root / diffuse_dataset_id).is_dir()
        print(
            f"  {base_dataset_id} -> {diffuse_dataset_id} "
            f"(base_present={base_present}, diffuse_present={diffuse_present})"
        )
    if args.dry_run:
        return 0

    try:
        result = build_basis_sensitivity_qa(
            config_path=args.config,
            profiles_root=args.profiles_root,
            qa_root=args.qa_root,
            pairs=pairs,
            force=args.force,
            warn_relative_l1=args.warn_relative_l1,
            warn_delta_radius_angstrom=args.warn_delta_radius_angstrom,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {repo_relative_path(result.rows_csv)} ({result.row_count} rows)")
    print(f"Wrote {repo_relative_path(result.summary_csv)} ({result.summary_count} rows)")
    print(f"Wrote {repo_relative_path(result.outliers_csv)} ({result.outlier_count} rows)")
    print(f"Wrote {repo_relative_path(result.metadata_json)}")
    if result.skipped_pairs:
        print("Skipped comparison pairs:")
        for skipped in result.skipped_pairs:
            print(
                "  {base_dataset_id} -> {diffuse_dataset_id}: {reason}".format(**skipped)
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
