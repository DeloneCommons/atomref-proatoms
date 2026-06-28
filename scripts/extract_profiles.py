#!/usr/bin/env python3
"""Extract wide profile CSV/JSON datasets from saved SCF artifacts.

The v1 profile extractor will read ``local-data/scf`` artifacts and write one
``profiles.csv`` plus one ``metadata.json`` under each ``data/profiles`` dataset
directory.  This placeholder keeps the final script surface in place while the
persistent SCF artifact patch lands first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.paths import local_scf_root, profile_root  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scf-root", type=Path, default=local_scf_root())
    parser.add_argument("--output-root", type=Path, default=profile_root())
    parser.add_argument("--dataset", action="append", default=[])
    parser.parse_args(argv)
    print(
        "ERROR: profile extraction from saved SCF artifacts is not implemented yet. "
        "This command is reserved for the next extraction patch.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
