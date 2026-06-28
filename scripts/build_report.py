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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles-root", type=Path, default=profile_root())
    parser.add_argument("--report-dir", type=Path, default=report_dir())
    parser.parse_args(argv)
    print(
        "ERROR: report generation will be implemented after the wide profile "
        "CSV/metadata format lands.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
