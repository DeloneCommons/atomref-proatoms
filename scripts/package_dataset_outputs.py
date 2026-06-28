#!/usr/bin/env python3
"""Package generated profile datasets as a release-candidate ZIP archive."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.dataset_index import check_profile_dataset_with_indexes  # noqa: E402
from atomref_proatoms.qa import ELECTRON_COUNT_ABS_TOL, ELECTRON_COUNT_REL_TOL  # noqa: E402
from atomref_proatoms.release_package import (  # noqa: E402
    DEFAULT_ARCHIVE_ROOT,
    check_release_package,
    default_release_archive_path,
    expected_profile_counts_from_states,
    format_release_package_check,
    format_release_package_result,
    package_dataset_outputs,
    selected_release_dataset_ids,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "local-data" / "profile-builds",
        help="Generated profile output root; defaults to local-data/profile-builds.",
    )
    parser.add_argument(
        "--dataset-id",
        action="append",
        default=[],
        help=(
            "Dataset ID to package; may be repeated. Use 'all' or 'all_v0' for all "
            "planned datasets. Defaults to indexed dataset directories discovered under output-dir."
        ),
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=None,
        help="Output release ZIP path; defaults beside output-dir.",
    )
    parser.add_argument(
        "--archive-root",
        default=DEFAULT_ARCHIVE_ROOT,
        help="Path prefix inside the archive; defaults to data/profiles.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Warn and skip missing selected datasets instead of failing.",
    )
    parser.add_argument(
        "--check-datasets",
        action="store_true",
        help="Run dataset checks before packaging.",
    )
    parser.add_argument(
        "--require-profile-qa",
        action="store_true",
        help="Require independent profile QA when --check-datasets is enabled.",
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
        "--check-archive",
        action="store_true",
        help="Validate the produced release ZIP archive before exiting.",
    )
    parser.add_argument(
        "--require-expected-counts",
        action="store_true",
        help=(
            "When --check-archive is enabled, validate embedded profile counts against "
            "the curated-state build plan."
        ),
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print compact per-dataset release summary when checking the archive.",
    )
    return parser.parse_args()


def _check_dataset(output_dir: Path, dataset_id: str, args: argparse.Namespace) -> list[str]:
    profile_result, index_result = check_profile_dataset_with_indexes(
        output_dir / dataset_id,
        states_file=ROOT / "data" / "states" / "curated" / "atom_states_v0.json",
        basis_root=ROOT / "data" / "basis_sets",
        require_profile_qa=args.require_profile_qa,
        electron_count_abs_tol=args.electron_count_abs_tol,
        electron_count_rel_tol=args.electron_count_rel_tol,
        require_indexes=True,
    )
    errors = list(profile_result.errors)
    if index_result is not None:
        errors.extend(index_result.errors)
    return errors


def main() -> int:
    args = parse_args()
    try:
        dataset_ids = selected_release_dataset_ids(tuple(args.dataset_id), args.output_dir)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not dataset_ids:
        raise SystemExit(f"No indexed dataset directories found under {args.output_dir}")
    archive_path = args.archive or default_release_archive_path(args.output_dir, dataset_ids)

    if args.check_datasets:
        errors: list[str] = []
        for dataset_id in dataset_ids:
            dataset_errors = _check_dataset(args.output_dir, dataset_id, args)
            errors.extend(f"{dataset_id}: {error}" for error in dataset_errors)
        if errors:
            print("ERROR: dataset checks failed before packaging", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1

    try:
        result = package_dataset_outputs(
            args.output_dir,
            archive_path,
            dataset_ids=dataset_ids,
            archive_root=args.archive_root,
            allow_missing=args.allow_missing,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(format_release_package_result(result))

    if args.check_archive:
        expected_counts = None
        if args.require_expected_counts:
            expected_counts = expected_profile_counts_from_states(
                ROOT / "data" / "states" / "curated" / "atom_states_v0.json",
                dataset_ids=result.dataset_ids,
            )
        check = check_release_package(
            archive_path,
            expected_dataset_ids=result.dataset_ids,
            require_dataset_indexes=args.summary or args.require_expected_counts,
            expected_profile_counts=expected_counts,
        )
        print()
        print(format_release_package_check(check, summary=args.summary))
        return 0 if check.ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
