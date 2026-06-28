"""Small artifact writers for future generated profile datasets."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_profile_csv_gz(path: Path, rows: list[tuple[float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        handle.write("r_bohr,rho_e_bohr3\n")
        for r_bohr, rho in rows:
            handle.write(f"{r_bohr:.17g},{rho:.17g}\n")
