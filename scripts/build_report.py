#!/usr/bin/env python3
"""Build the current atomref-proatoms scientific report from profile datasets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.paths import profile_root, report_dir  # noqa: E402
from atomref_proatoms.report import build_report, discover_profile_datasets  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles-root", type=Path, default=profile_root())
    parser.add_argument("--report-dir", type=Path, default=report_dir())
    parser.add_argument(
        "--dataset",
        "--dataset-id",
        dest="dataset_ids",
        action="append",
        default=[],
        help="Restrict report to one dataset_id; may be repeated. Defaults to all generated datasets.",
    )
    parser.add_argument("--list", action="store_true", help="List detected profile datasets and exit.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_ids = tuple(args.dataset_ids) or None
    if args.list:
        datasets = discover_profile_datasets(args.profiles_root, dataset_ids=dataset_ids)
        for dataset in datasets:
            print(f"{dataset.dataset_id}: {len(dataset.state_ids)} states, {dataset.row_count} grid rows")
        if not datasets:
            print(f"No generated profile datasets found under {args.profiles_root}")
            return 1
        return 0
    try:
        outputs = build_report(
            profiles_root=args.profiles_root,
            report_dir=args.report_dir,
            dataset_ids=dataset_ids,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Report written: {outputs['report']}")
    print(f"Report manifest: {outputs['manifest']}")
    print(f"Tables: {outputs['dataset_summary'].parent}")
    print(f"Figures: {outputs['electron_error_svg'].parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
