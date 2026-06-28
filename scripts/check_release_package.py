#!/usr/bin/env python3
"""Validate a release-candidate ZIP archive produced by package_dataset_outputs.py."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.release_package import (  # noqa: E402
    check_release_package,
    expected_profile_counts_from_states,
    format_release_package_check,
    selected_release_dataset_ids,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True, help="Release ZIP archive to check.")
    parser.add_argument(
        "--dataset-id",
        action="append",
        default=[],
        help="Expected dataset ID; may be repeated. Use 'all' or 'all_v0' for all v0 datasets.",
    )
    parser.add_argument(
        "--states-file",
        type=Path,
        default=ROOT / "data" / "states" / "curated" / "atom_states_v0.json",
        help="Curated states JSON used for expected build-plan counts.",
    )
    parser.add_argument(
        "--no-hash-check",
        action="store_true",
        help="Only check manifest/file presence, not archived payload hashes.",
    )
    parser.add_argument(
        "--check-dataset-indexes",
        action="store_true",
        help="Validate embedded dataset manifests/index tables and archive file counts.",
    )
    parser.add_argument(
        "--require-expected-counts",
        action="store_true",
        help="Validate embedded profile counts against the curated-state build plan.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print compact per-dataset release summaries.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        expected_dataset_ids = selected_release_dataset_ids(tuple(args.dataset_id), Path("."))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    expected_counts = None
    if args.require_expected_counts:
        dataset_ids_for_counts = expected_dataset_ids or tuple(
            dataset_id
            for dataset_id in selected_release_dataset_ids(("all",), Path("."))
        )
        expected_counts = expected_profile_counts_from_states(
            args.states_file, dataset_ids=dataset_ids_for_counts
        )

    result = check_release_package(
        args.archive,
        expected_dataset_ids=expected_dataset_ids,
        require_hashes=not args.no_hash_check,
        require_dataset_indexes=args.check_dataset_indexes or args.summary,
        expected_profile_counts=expected_counts,
    )
    print(format_release_package_check(result, summary=args.summary))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
