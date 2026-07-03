#!/usr/bin/env python3
"""Build generator-ready atom-state records from compact configuration tables.

The script intentionally does not parse NIST pages and does not reconstruct
spectroscopic terms. It combines project-maintained CSV inputs under
``data/states`` and writes a single JSON file for the spherical proatom
generator.

Default inputs:
  data/states/source/nist_gsie/nist_neutral_cation_states.csv
  data/states/source/ning2022/ning2022_monoanions.csv
  data/states/curated/formal_atoms_ions.csv

Default outputs:
  data/states/selection/required_states_v2.csv
  data/states/curated/atom_states_v2.csv
  data/states/curated/atom_states_v2.json
  data/states/curated/atom_states_summary_v2.json
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

# Relative table paths are stored in generated rows so that source provenance
# remains auditable after the source layer was organized by data source.
NIST_SOURCE_TABLE = Path("source/nist_gsie/nist_neutral_cation_states.csv")
NING2022_SOURCE_TABLE = Path("source/ning2022/ning2022_monoanions.csv")
FORMAL_ANION_TABLE = Path("curated/formal_atoms_ions.csv")
NIST_SOURCE_TABLE_LABEL = NIST_SOURCE_TABLE.as_posix()
NING2022_SOURCE_TABLE_LABEL = NING2022_SOURCE_TABLE.as_posix()
FORMAL_ANION_TABLE_LABEL = FORMAL_ANION_TABLE.as_posix()

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


GROUP_1 = {"H", "Li", "Na", "K", "Rb", "Cs", "Fr"}
GROUP_2 = {"Be", "Mg", "Ca", "Sr", "Ba", "Ra"}
GROUP_18 = {"He", "Ne", "Ar", "Kr", "Xe", "Rn"}
V2_MAX_Z = 103
V2_ANION_MAX_Z = 86
V2_SCHEMA_VERSION = "atomref.proatoms.state.v2"
V2_SUMMARY_SCHEMA_VERSION = "atomref.proatoms.state_build_summary.v2"
V2_SPIN_MODEL = "curated_ground_multiplicity"
V2_SPIN_VARIANT = "curated_multiplicity"
V2_OCCUPATION_POLICY = "spherical_l_counts_from_curated_multiplicity_v2"


def _clean_l_count(value: float) -> int | float:
    if abs(value - round(value)) < 1e-10:
        return int(round(value))
    return round(value, 10)


def infer_occupation_counts_for_multiplicity(
    configuration: str,
    electron_count: int,
    multiplicity: int,
) -> dict[str, Any]:
    """Infer spherical alpha/beta l-counts for a curated multiplicity.

    Earlier state builders used the maximum-spin Hund count implied by the
    configuration. In the active v2 builder, the spin multiplicity comes from
    the curated NIST/Ning/formal source
    table.  When the curated multiplicity is lower than the maximum-spin count
    implied by the configuration, the remaining spin imbalance is distributed
    proportionally over the open angular-momentum channels.  This keeps the
    occupation model spherical and deterministic without inventing an orbital
    term decomposition that is not present in the compact source table.
    """

    high_spin = infer_occupation_counts(configuration, electron_count)
    desired_spin_2s = int(multiplicity) - 1
    if desired_spin_2s < 0:
        raise ValueError(f"Invalid multiplicity {multiplicity} for {configuration!r}")

    max_spin_2s = int(high_spin["spin_2s"])
    if desired_spin_2s > max_spin_2s:
        raise ValueError(
            f"Curated multiplicity {multiplicity} exceeds the maximum-spin "
            f"configuration count {max_spin_2s + 1} for {configuration!r}"
        )

    high_alpha = {int(k): float(v) for k, v in high_spin["alpha_l_counts"].items()}
    high_beta = {int(k): float(v) for k, v in high_spin["beta_l_counts"].items()}
    l_values = sorted(set(high_alpha) | set(high_beta))
    total_by_l = {
        l_value: high_alpha.get(l_value, 0.0) + high_beta.get(l_value, 0.0)
        for l_value in l_values
    }
    max_diff_by_l = {
        l_value: high_alpha.get(l_value, 0.0) - high_beta.get(l_value, 0.0)
        for l_value in l_values
    }

    if desired_spin_2s == max_spin_2s:
        alpha = high_alpha
        beta = high_beta
    else:
        factor = 0.0 if max_spin_2s == 0 else desired_spin_2s / max_spin_2s
        alpha = {}
        beta = {}
        for l_value in l_values:
            diff = max_diff_by_l[l_value] * factor
            total = total_by_l[l_value]
            alpha[l_value] = (total + diff) / 2.0
            beta[l_value] = (total - diff) / 2.0

    spin_2s = sum(alpha.values()) - sum(beta.values())
    if abs(spin_2s - desired_spin_2s) > 1e-8:
        raise ValueError(
            f"Could not assign spin_2s={desired_spin_2s} for {configuration!r}; "
            f"got {spin_2s}"
        )

    return {
        "spin_2s": desired_spin_2s,
        "multiplicity": int(multiplicity),
        "alpha_l_counts": {
            str(l_value): _clean_l_count(alpha[l_value])
            for l_value in l_values
            if abs(alpha[l_value]) > 1e-12
        },
        "beta_l_counts": {
            str(l_value): _clean_l_count(beta[l_value])
            for l_value in l_values
            if abs(beta[l_value]) > 1e-12
        },
    }


def v2_cation_charges(symbol: str) -> list[int]:
    if symbol in GROUP_1:
        return [1]
    if symbol in GROUP_2:
        return [1, 2]
    return [1, 2, 3]


def state_id_v2(symbol: str, charge: int, multiplicity: int, state_source: str) -> str:
    suffix = {
        "nist_gsie": "nist",
        "ning2022": "ning2022",
        "formal_rule": "formal",
        "manual_curated": "formal",
    }.get(state_source, "curated")
    return f"{symbol}_{charge_label(charge)}_mult{multiplicity}_{suffix}"


def v2_notes(row: dict[str, str], *extra: str) -> list[str]:
    notes: list[str] = [note for note in extra if note]
    raw = row.get("notes", "").strip()
    if raw:
        notes.append(raw)
    return notes


def build_v2_selection_rows(data_dir: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    nist_rows = read_csv_rows(data_dir / NIST_SOURCE_TABLE)
    ning_rows = read_csv_rows(data_dir / NING2022_SOURCE_TABLE)
    formal_rows = read_csv_rows(data_dir / FORMAL_ANION_TABLE)

    nist_by_key = index_rows(nist_rows, name=NIST_SOURCE_TABLE_LABEL)
    selection_rows: list[dict[str, str]] = []
    skipped_cations: list[dict[str, str]] = []

    neutral_symbols = [
        row["symbol"]
        for row in nist_rows
        if int(row["charge"]) == 0 and int(row["z"]) <= V2_MAX_Z
    ]

    for symbol in neutral_symbols:
        neutral = nist_by_key[(symbol, 0)]
        selection_rows.append(
            {
                "z": neutral["z"],
                "symbol": symbol,
                "charge": "0",
                "electron_count": neutral["electron_count"],
                "state_source": "nist_gsie",
                "source_table": NIST_SOURCE_TABLE_LABEL,
                "state_role": "reference",
                "physical_status": "experimental_or_evaluated",
                "include_reason": "neutral_reference_policy",
            }
        )

        for charge in v2_cation_charges(symbol):
            row = nist_by_key.get((symbol, charge))
            if row is None:
                skipped_cations.append(
                    {
                        "symbol": symbol,
                        "charge": str(charge),
                        "reason": "missing_nist_electron_bearing_state",
                    }
                )
                continue
            if int(row["electron_count"]) <= 0:
                skipped_cations.append(
                    {
                        "symbol": symbol,
                        "charge": str(charge),
                        "reason": "non_positive_electron_count",
                    }
                )
                continue
            if not row.get("ground_multiplicity", ""):
                skipped_cations.append(
                    {
                        "symbol": symbol,
                        "charge": str(charge),
                        "reason": "missing_ground_multiplicity",
                    }
                )
                continue
            selection_rows.append(
                {
                    "z": row["z"],
                    "symbol": symbol,
                    "charge": str(charge),
                    "electron_count": row["electron_count"],
                    "state_source": "nist_gsie",
                    "source_table": NIST_SOURCE_TABLE_LABEL,
                    "state_role": "reference"
                    if row["nist_ie_provenance"] == "evaluated"
                    else "reference_uncertain",
                    "physical_status": "experimental_or_evaluated",
                    "include_reason": "v2_cation_charge_policy",
                }
            )

    for row in ning_rows:
        symbol = row["symbol"]
        if int(row["z"]) > V2_ANION_MAX_Z:
            continue
        if symbol in GROUP_18:
            continue
        if row["state_role"] not in {"bound_experimental", "bound_provisional"}:
            continue
        selection_rows.append(
            {
                "z": row["z"],
                "symbol": symbol,
                "charge": "-1",
                "electron_count": row["electron_count"],
                "state_source": "ning2022",
                "source_table": NING2022_SOURCE_TABLE_LABEL,
                "state_role": row["state_role"],
                "physical_status": row["physical_status"],
                "include_reason": "accepted_physical_or_provisional_monoanion",
            }
        )

    for row in formal_rows:
        selection_rows.append(
            {
                "z": row["z"],
                "symbol": row["symbol"],
                "charge": row["charge"],
                "electron_count": row["electron_count"],
                "state_source": row["state_source"],
                "source_table": FORMAL_ANION_TABLE_LABEL,
                "state_role": row["state_role"],
                "physical_status": row["physical_status"],
                "include_reason": row["rule_reason"],
            }
        )

    keys = [(row["symbol"], row["charge"]) for row in selection_rows]
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate v2 selected states: {duplicates[:10]}")

    selection_rows.sort(key=lambda row: (int(row["z"]), int(row["charge"])))
    diagnostics = {"skipped_cations": skipped_cations}
    return selection_rows, diagnostics


def build_states_v2(
    data_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    nist_by_key = index_rows(
        read_csv_rows(data_dir / NIST_SOURCE_TABLE),
        name=NIST_SOURCE_TABLE_LABEL,
    )
    ning_by_key = index_rows(
        read_csv_rows(data_dir / NING2022_SOURCE_TABLE),
        name=NING2022_SOURCE_TABLE_LABEL,
    )
    formal_by_key = index_rows(
        read_csv_rows(data_dir / FORMAL_ANION_TABLE),
        name=FORMAL_ANION_TABLE_LABEL,
    )

    selection_rows, diagnostics = build_v2_selection_rows(data_dir)
    states: list[dict[str, Any]] = []
    seen_state_ids: set[str] = set()

    for selected in selection_rows:
        symbol = selected["symbol"]
        charge = int(selected["charge"])
        source_table = selected["source_table"]
        if source_table == NIST_SOURCE_TABLE_LABEL:
            row = nist_by_key[(symbol, charge)]
            multiplicity = int(row["ground_multiplicity"])
            ground_level = row["ground_level"]
            state_category = "nist_reference"
            curation_status = "curated"
            state_source = "nist_gsie"
            nist_ie_provenance = row["nist_ie_provenance"]
            rule_reason = ""
        elif source_table == NING2022_SOURCE_TABLE_LABEL:
            row = ning_by_key[(symbol, charge)]
            multiplicity = int(row["ground_multiplicity"])
            ground_level = row["ground_level"]
            state_category = "ning2022_monoanion_reference"
            curation_status = (
                "curated" if row["state_role"] == "bound_experimental" else "provisional"
            )
            state_source = "ning2022"
            nist_ie_provenance = ""
            rule_reason = ""
        elif source_table == FORMAL_ANION_TABLE_LABEL:
            row = formal_by_key[(symbol, charge)]
            multiplicity = int(row["ground_multiplicity"])
            ground_level = ""
            state_category = "formal_anion_reference"
            curation_status = "formal"
            state_source = row["state_source"]
            nist_ie_provenance = ""
            rule_reason = row["rule_reason"]
        else:
            raise ValueError(f"Unknown v2 source table {source_table!r}")

        z = int(row["z"])
        electron_count = int(row["electron_count"])
        configuration = row["configuration"].strip()
        occupation = infer_occupation_counts_for_multiplicity(
            configuration,
            electron_count,
            multiplicity,
        )
        sid = state_id_v2(symbol, charge, multiplicity, state_source)
        if sid in seen_state_ids:
            raise ValueError(f"Duplicate generated state_id: {sid}")
        seen_state_ids.add(sid)

        notes = v2_notes(row)
        if state_category == "formal_anion_reference" and not any(
            "not a stable" in note for note in notes
        ):
            notes.append(
                "Formal stockholder/Hirshfeld-I reference; not a claim of a stable "
                "isolated atomic anion."
            )

        states.append(
            {
                "schema_version": V2_SCHEMA_VERSION,
                "state_id": sid,
                "symbol": symbol,
                "z": z,
                "charge": charge,
                "electron_count": electron_count,
                "configuration": configuration,
                "ground_level": ground_level,
                "spin_2s": occupation["spin_2s"],
                "multiplicity": occupation["multiplicity"],
                "alpha_l_counts": occupation["alpha_l_counts"],
                "beta_l_counts": occupation["beta_l_counts"],
                "spin_model": V2_SPIN_MODEL,
                "spin_variant": V2_SPIN_VARIANT,
                "state_role": selected["state_role"],
                "occupation_policy": V2_OCCUPATION_POLICY,
                "state_category": state_category,
                "curation_status": curation_status,
                "physical_status": selected["physical_status"],
                "state_source": state_source,
                "source_table": source_table,
                "nist_ie_provenance": nist_ie_provenance,
                "rule_reason": rule_reason,
                "notes": notes,
            }
        )

    return states, selection_rows, diagnostics


def build_summary_v2(
    states: list[dict[str, Any]],
    selection_rows: list[dict[str, str]],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    by_category = Counter(state["state_category"] for state in states)
    by_charge = Counter(str(state["charge"]) for state in states)
    by_source = Counter(state["state_source"] for state in states)
    by_role = Counter(state["state_role"] for state in states)
    by_physical_status = Counter(state["physical_status"] for state in states)
    neutral = sum(1 for state in states if state["charge"] == 0)
    cations = sum(1 for state in states if state["charge"] > 0)
    anions = sum(1 for state in states if state["charge"] < 0)
    return {
        "schema_version": V2_SUMMARY_SCHEMA_VERSION,
        "state_count": len(states),
        "selection_count": len(selection_rows),
        "neutral_count": neutral,
        "cation_count": cations,
        "anion_count": anions,
        "output_files": [
            "selection/required_states_v2.csv",
            "curated/atom_states_v2.csv",
            "curated/atom_states_v2.json",
        ],
        "by_category": dict(sorted(by_category.items())),
        "by_charge": dict(sorted(by_charge.items(), key=lambda item: int(item[0]))),
        "by_source": dict(sorted(by_source.items())),
        "by_role": dict(sorted(by_role.items())),
        "by_physical_status": dict(sorted(by_physical_status.items())),
        "spin_model": V2_SPIN_MODEL,
        "occupation_policy": V2_OCCUPATION_POLICY,
        "policy_notes": [
            "H+ and He2+/He3+ are not included because they are not "
            "electron-bearing NIST source rows.",
            "Purely formal actinide fallback monoanions are out of the initial v2 scope.",
            "Group-18 anions are excluded from the v2 anion policy.",
        ],
        "diagnostics": diagnostics,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def atom_states_v2_csv_rows(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for state in states:
        rows.append(
            {
                "state_id": state["state_id"],
                "z": state["z"],
                "symbol": state["symbol"],
                "charge": state["charge"],
                "electron_count": state["electron_count"],
                "configuration": state["configuration"],
                "ground_level": state["ground_level"],
                "multiplicity": state["multiplicity"],
                "spin_2s": state["spin_2s"],
                "state_category": state["state_category"],
                "state_role": state["state_role"],
                "physical_status": state["physical_status"],
                "state_source": state["state_source"],
                "source_table": state["source_table"],
                "nist_ie_provenance": state["nist_ie_provenance"],
                "rule_reason": state["rule_reason"],
                "notes": " | ".join(state["notes"]),
            }
        )
    return rows


def write_v2_outputs(data_dir: Path) -> dict[str, Any]:
    states, selection_rows, diagnostics = build_states_v2(data_dir)
    summary = build_summary_v2(states, selection_rows, diagnostics)

    write_csv(
        data_dir / "selection" / "required_states_v2.csv",
        selection_rows,
        [
            "z",
            "symbol",
            "charge",
            "electron_count",
            "state_source",
            "source_table",
            "state_role",
            "physical_status",
            "include_reason",
        ],
    )
    write_csv(
        data_dir / "curated" / "atom_states_v2.csv",
        atom_states_v2_csv_rows(states),
        [
            "state_id",
            "z",
            "symbol",
            "charge",
            "electron_count",
            "configuration",
            "ground_level",
            "multiplicity",
            "spin_2s",
            "state_category",
            "state_role",
            "physical_status",
            "state_source",
            "source_table",
            "nist_ie_provenance",
            "rule_reason",
            "notes",
        ],
    )
    write_json(data_dir / "curated" / "atom_states_v2.json", states)
    write_json(data_dir / "curated" / "atom_states_summary_v2.json", summary)
    return summary


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/states"),
        help="Directory containing source/, selection/, and curated/ state data files.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the existing curated v2 JSON without rewriting it.",
    )
    args = parser.parse_args(argv)

    data_dir = args.data_dir
    states_file = data_dir / "curated" / "atom_states_v2.json"

    if args.check:
        return check_curated_states(states_file)

    summary = write_v2_outputs(data_dir)
    print(f"Wrote {summary['state_count']} atom states to {states_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
