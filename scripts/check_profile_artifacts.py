#!/usr/bin/env python3
"""Check generated profile/radii/QA artifacts against the active v2 dataset config."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.dataio.paths import (  # noqa: E402
    PROFILE_DATASETS_FILE,
    PROFILES_ROOT,
    QA_ROOT,
    RADII_ROOT,
    STATES_FILE,
    repo_relative_path,
)
from atomref_proatoms.profiles.artifact_check import check_generated_artifacts  # noqa: E402


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
        "--radii-root",
        type=Path,
        default=RADII_ROOT,
        help="Generated radii artifact root; defaults to data/radii.",
    )
    parser.add_argument(
        "--qa-root",
        type=Path,
        default=QA_ROOT,
        help="Generated QA artifact root; defaults to data/qa.",
    )
    parser.add_argument(
        "--require-generated",
        action="store_true",
        help="Fail when no generated profile/radii/QA dataset artifacts are present.",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help=(
            "Allow a matching subset of configured dataset IDs during incremental local work. "
            "The default release gate requires all configured dataset directories once any "
            "generated dataset exists."
        ),
    )
    parser.add_argument(
        "--allow-qa-failures",
        action="store_true",
        help="Do not fail solely because generated QA rows or summaries contain failures.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = check_generated_artifacts(
        config_path=args.config,
        states_file=args.states_file,
        profiles_root=args.profiles_root,
        radii_root=args.radii_root,
        qa_root=args.qa_root,
        allow_empty=not args.require_generated,
        allow_partial=args.allow_partial,
        require_qa_pass=not args.allow_qa_failures,
    )
    if result.errors:
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if result.checked_dataset_ids:
        print(
            "OK: checked generated profile/radii/QA artifacts for "
            f"{len(result.checked_dataset_ids)} datasets and {result.state_count} state rows"
        )
        print(f"profile_data_version: {result.profile_data_version}")
        for dataset_id in result.checked_dataset_ids:
            print(f"  {dataset_id}")
    else:
        print("OK: no generated profile/radii/QA dataset artifacts found")
        print(f"profile_data_version: {result.profile_data_version}")
        print(f"profiles_root: {repo_relative_path(args.profiles_root)}")
        print(f"radii_root: {repo_relative_path(args.radii_root)}")
        print(f"qa_root: {repo_relative_path(args.qa_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
