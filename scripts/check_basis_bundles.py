#!/usr/bin/env python3
"""Check frozen basis-set bundles for atomref-proatoms.

The checker validates file presence, SHA256 hashes, NWChem/SPHERICAL headers,
BSE header metadata, element coverage, and the mandatory stored BSE source URL
metadata. If PySCF is installed, the same run also performs small basis-parse
smoke checks through ``pyscf.gto.basis.parse``. If PySCF is not installed, the
structural checks still run and the PySCF smoke step is reported as skipped.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.exists():
    sys.path.insert(0, str(_SRC))

from atomref_proatoms.dataio.basis import (  # noqa: E402
    get_pyscf_basis_parser,
    list_basis_bundles,
    load_basis_nw_text,
    parse_covered_z,
    parse_pyscf_basis_smoke,
    validate_all_basis_bundles,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basis-root", default=Path("data/basis_sets"), type=Path)
    args = parser.parse_args(argv)

    root = args.basis_root
    errors = validate_all_basis_bundles(root, run_pyscf_smoke=False)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    bundles = list_basis_bundles(root)
    pyscf_basis, pyscf_version, pyscf_error = get_pyscf_basis_parser()
    smoke_cases: list[str] = []
    if pyscf_basis is not None:
        for bundle in bundles:
            text = load_basis_nw_text(bundle)
            z_values = parse_covered_z(text)
            try:
                smoke_cases.extend(parse_pyscf_basis_smoke(bundle, text, z_values))
            except Exception as exc:  # pragma: no cover - optional local dependency
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1

    print(f"OK: checked {len(bundles)} basis bundles under {root}")
    if pyscf_basis is None:
        print(f"PySCF smoke checks: skipped (PySCF is not installed: {pyscf_error})")
    else:
        print(
            "PySCF smoke checks: passed "
            f"(PySCF {pyscf_version}; parsed {len(smoke_cases)} element/basis cases)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
