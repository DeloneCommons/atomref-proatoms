#!/usr/bin/env python3
"""Build generator-ready atom-state records from compact configuration tables.

The script intentionally does not parse NIST pages and does not reconstruct
spectroscopic terms. It combines project-maintained CSV inputs under
``data/states`` and writes a single JSON file for the spherical proatom
generator.

Default inputs:
  data/states/source/atom_configs_nist_source.csv
  data/states/source/atom_configs_formal_anions.csv
  data/states/selection/required_states_v0.csv

Default outputs:
  data/states/curated/atom_states_v0.json
  data/states/curated/atom_states_summary.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

L_BY_LETTER = {"s": 0, "p": 1, "d": 2, "f": 3, "g": 4}
ORBITALS_BY_L = {l_value: 2 * l_value + 1 for l_value in L_BY_LETTER.values()}

# Bracket cores used by NIST GSIE ground-shell notation and by the compact
# formal-anion table. They are expanded explicitly to keep this script
# dependency-free and deterministic.
CORE_CONFIGS = {
    "He": "1s2",
    "Ne": "1s2 2s2 2p6",
    "Ar": "1s2 2s2 2p6 3s2 3p6",
    "Kr": "1s2 2s2 2p6 3s2 3p6 3d10 4s2 4p6",
    "Xe": "1s2 2s2 2p6 3s2 3p6 3d10 4s2 4p6 4d10 5s2 5p6",
    "Rn": "1s2 2s2 2p6 3s2 3p6 3d10 4s2 4p6 4d10 5s2 5p6 4f14 5d10 6s2 6p6",
    "Cd": "1s2 2s2 2p6 3s2 3p6 3d10 4s2 4p6 4d10 5s2",
    "Hg": "1s2 2s2 2p6 3s2 3p6 3d10 4s2 4p6 4d10 5s2 5p6 4f14 5d10 6s2",
}

SUBSHELL_RE = re.compile(r"(?P<n>\d+)(?P<letter>[spdfg])(?P<occ>\d+)")
CORE_RE = re.compile(r"\[(?P<core>[A-Z][a-z]?)\]")
OCCUPATION_POLICY = "free_ion_hund_high_spin_from_configuration_v0"
SPIN_MODEL = "free_ion_hund_high_spin"
SPIN_VARIANT = "hund_high_spin"
STATE_ROLE = "recommended"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def charge_label(charge: int) -> str:
    if charge == 0:
        return "q0"
    if charge > 0:
        return f"qp{charge}"
    return f"qm{abs(charge)}"


def state_id(symbol: str, charge: int, multiplicity: int) -> str:
    return f"{symbol}_{charge_label(charge)}_mult{multiplicity}_hund"


def key(symbol: str, charge: int) -> tuple[str, int]:
    return symbol.strip(), int(charge)


def index_rows(rows: list[dict[str, str]], *, name: str) -> dict[tuple[str, int], dict[str, str]]:
    indexed: dict[tuple[str, int], dict[str, str]] = {}
    duplicates: list[tuple[str, int]] = []
    for row in rows:
        k = key(row["symbol"], int(row["charge"]))
        if k in indexed:
            duplicates.append(k)
        indexed[k] = row
    if duplicates:
        raise ValueError(f"Duplicate keys in {name}: {duplicates[:10]}")
    return indexed


def expand_configuration(configuration: str) -> list[tuple[int, int, int]]:
    """Return explicit ``(n, l, occupancy)`` tuples from a compact configuration."""
    config = configuration.strip()
    parts: list[str] = []

    while True:
        match = CORE_RE.search(config)
        if not match:
            break
        core = match.group("core")
        if core not in CORE_CONFIGS:
            raise ValueError(f"Unknown bracket core [{core}] in configuration {configuration!r}")
        parts.extend(CORE_CONFIGS[core].split())
        config = config[: match.start()] + " " + config[match.end() :]

    parts.extend(config.split())

    subshells: list[tuple[int, int, int]] = []
    for token in parts:
        match = SUBSHELL_RE.fullmatch(token)
        if not match:
            raise ValueError(
                f"Cannot parse subshell token {token!r} "
                f"in configuration {configuration!r}"
            )
        n = int(match.group("n"))
        l_value = L_BY_LETTER[match.group("letter")]
        occ = int(match.group("occ"))
        capacity = 2 * ORBITALS_BY_L[l_value]
        if not (0 <= occ <= capacity):
            raise ValueError(f"Invalid occupancy {token!r} in configuration {configuration!r}")
        subshells.append((n, l_value, occ))
    return subshells


def infer_occupation_counts(configuration: str, electron_count: int) -> dict[str, Any]:
    """Infer alpha/beta l-counts using a free-ion Hund high-spin convention.

    This is a generator convention for spherical proatoms, not a ligand-field
    spin-state model and not a spectroscopic term-symbol reconstruction.
    """
    alpha: Counter[int] = Counter()
    beta: Counter[int] = Counter()
    total_electrons = 0

    for _n, l_value, occ in expand_configuration(configuration):
        orbitals = ORBITALS_BY_L[l_value]
        a = min(occ, orbitals)
        b = max(0, occ - orbitals)
        alpha[l_value] += a
        beta[l_value] += b
        total_electrons += occ

    if total_electrons != int(electron_count):
        raise ValueError(
            f"Configuration electron count mismatch for {configuration!r}: "
            f"configuration has {total_electrons}, row says {electron_count}"
        )

    spin_2s = sum(alpha.values()) - sum(beta.values())
    return {
        "spin_2s": spin_2s,
        "multiplicity": spin_2s + 1,
        "alpha_l_counts": {str(l_value): alpha[l_value] for l_value in sorted(alpha)},
        "beta_l_counts": {str(l_value): beta[l_value] for l_value in sorted(beta)},
    }


def build_states(data_dir: Path, selection_file: Path) -> list[dict[str, Any]]:
    source_dir = data_dir / "source"

    nist_rows = read_csv_rows(source_dir / "atom_configs_nist_source.csv")
    formal_rows = read_csv_rows(source_dir / "atom_configs_formal_anions.csv")
    selected_rows = read_csv_rows(selection_file)

    nist_by_key = index_rows(nist_rows, name="atom_configs_nist_source.csv")
    formal_by_key = index_rows(formal_rows, name="atom_configs_formal_anions.csv")

    states: list[dict[str, Any]] = []
    seen_state_ids: set[str] = set()

    for selected in selected_rows:
        symbol = selected["element"].strip()
        charge = int(selected["charge"])
        k = key(symbol, charge)

        if charge < 0:
            row = formal_by_key.get(k)
            if row is None:
                raise ValueError(f"Required anion/formal anion not found: {symbol} charge {charge}")
            state_category = row["state_category"]
            curation_status = (
                "inferred_formal_ion"
                if state_category == "formal_crystal_ion_reference"
                else "inferred_simple_closed_shell"
            )
        else:
            row = nist_by_key.get(k)
            if row is None:
                raise ValueError(f"Required NIST-derived state not found: {symbol} charge {charge}")
            state_category = "nist_ground_state" if charge == 0 else "curated_common_ion"
            curation_status = "curated"

        z = int(row["z"])
        electron_count = int(row["electron_count"])
        configuration = row["configuration"].strip()
        occupation = infer_occupation_counts(configuration, electron_count)
        sid = state_id(symbol, charge, occupation["multiplicity"])
        if sid in seen_state_ids:
            raise ValueError(f"Duplicate generated state_id: {sid}")
        seen_state_ids.add(sid)

        notes: list[str] = []
        if state_category == "formal_crystal_ion_reference":
            notes.append(
                "Formal crystal-ion reference; not a claim of a stable free isolated atomic anion."
            )

        states.append(
            {
                "schema_version": "atomref.proatoms.state.v0",
                "state_id": sid,
                "symbol": symbol,
                "z": z,
                "charge": charge,
                "electron_count": electron_count,
                "configuration": configuration,
                "spin_2s": occupation["spin_2s"],
                "multiplicity": occupation["multiplicity"],
                "alpha_l_counts": occupation["alpha_l_counts"],
                "beta_l_counts": occupation["beta_l_counts"],
                "spin_model": SPIN_MODEL,
                "spin_variant": SPIN_VARIANT,
                "state_role": STATE_ROLE,
                "occupation_policy": OCCUPATION_POLICY,
                "state_category": state_category,
                "curation_status": curation_status,
                "notes": notes,
            }
        )

    return states


def build_summary(states: list[dict[str, Any]], selection_file: Path) -> dict[str, Any]:
    by_category = Counter(state["state_category"] for state in states)
    by_charge = Counter(str(state["charge"]) for state in states)
    by_curation_status = Counter(state["curation_status"] for state in states)
    by_spin_variant = Counter(state["spin_variant"] for state in states)
    return {
        "schema_version": "atomref.proatoms.state_build_summary.v0",
        "state_count": len(states),
        "selection_file": str(selection_file),
        "output_files": ["atom_states_v0.json"],
        "by_category": dict(sorted(by_category.items())),
        "by_charge": dict(sorted(by_charge.items(), key=lambda item: int(item[0]))),
        "by_curation_status": dict(sorted(by_curation_status.items())),
        "by_spin_variant": dict(sorted(by_spin_variant.items())),
        "spin_model": SPIN_MODEL,
        "occupation_policy": OCCUPATION_POLICY,
    }


def format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def check_curated_states(states_file: Path) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from atomref_proatoms.states import (  # noqa: PLC0415
        load_atom_states,
        selection_count_summary,
        validate_state_collection,
    )

    states = load_atom_states(states_file)
    errors = validate_state_collection(states)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    summary = selection_count_summary(states)
    print(f"OK: checked {summary['state_count']} atom states")
    print(f"categories: {format_counts(summary['by_category'])}")
    print(f"charges: {format_counts(summary['by_charge'])}")
    print(f"spin_variant: {format_counts(summary['by_spin_variant'])}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/states"),
        help="Directory containing source/ and selection/ state CSV files.",
    )
    parser.add_argument(
        "--selection-file",
        type=Path,
        default=None,
        help=(
            "CSV with element,charge columns. "
            "Defaults to <data-dir>/selection/required_states_v0.csv."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to <data-dir>/curated.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the existing curated JSON without rewriting it.",
    )
    args = parser.parse_args()

    data_dir = args.data_dir
    selection_file = args.selection_file or data_dir / "selection" / "required_states_v0.csv"
    out_dir = args.out_dir or data_dir / "curated"

    if args.check:
        return check_curated_states(out_dir / "atom_states_v0.json")

    states = build_states(data_dir, selection_file)
    summary = build_summary(states, selection_file)

    write_json(out_dir / "atom_states_v0.json", states)
    write_json(out_dir / "atom_states_summary.json", summary)

    print(f"Wrote {summary['state_count']} atom states to {out_dir / 'atom_states_v0.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
