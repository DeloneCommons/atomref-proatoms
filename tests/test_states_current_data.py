from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from atomref_proatoms.states import (
    load_atom_states,
    selection_count_summary,
    validate_state_collection,
)

ROOT = Path(__file__).resolve().parents[1]
STATES_FILE = ROOT / "data" / "states" / "curated" / "atom_states_v1.json"
NIST_SOURCE_FILE = ROOT / "data" / "states" / "source" / "atom_configs_nist_source.csv"

def test_current_state_table_loads_and_matches_expected_counts() -> None:
    states = load_atom_states(STATES_FILE)
    summary = selection_count_summary(states)
    assert summary["state_count"] == 173
    assert summary["neutral_count"] == 103
    assert summary["cation_count"] == 57
    assert summary["anion_count"] == 13
    assert summary["by_category"] == {
        "curated_common_ion": 61,
        "formal_crystal_ion_reference": 9,
        "nist_ground_state": 103,
    }
    assert summary["by_charge"] == {
        "-3": 5,
        "-2": 4,
        "-1": 4,
        "0": 103,
        "1": 9,
        "2": 22,
        "3": 23,
        "4": 3,
    }
    assert summary["by_spin_variant"] == {"hund_high_spin": 173}
    assert validate_state_collection(states) == []


def test_state_ids_are_unique_and_schema_has_no_per_record_sources() -> None:
    states = load_atom_states(STATES_FILE)
    ids = [state.state_id for state in states]
    assert len(ids) == len(set(ids))
    for state in states:
        assert "source" not in state.record
        assert "sources" not in state.record


def test_state_charge_spin_and_l_counts_are_consistent() -> None:
    for state in load_atom_states(STATES_FILE):
        assert state.electron_count == state.z - state.charge
        assert state.multiplicity == state.spin_2s + 1
        alpha = sum(int(value) for value in state.record["alpha_l_counts"].values())
        beta = sum(int(value) for value in state.record["beta_l_counts"].values())
        assert alpha + beta == state.electron_count
        assert alpha - beta == state.spin_2s
        assert state.record["spin_model"] == "free_ion_hund_high_spin"


def test_no_actinide_cations_in_curated_production_states() -> None:
    for state in load_atom_states(STATES_FILE):
        assert not (89 <= state.z <= 103 and state.charge > 0)


def test_formal_anions_and_halides_are_labeled_as_expected() -> None:
    for state in load_atom_states(STATES_FILE):
        if state.charge < -1:
            assert state.state_category == "formal_crystal_ion_reference"
        if state.symbol in {"F", "Cl", "Br", "I"} and state.charge == -1:
            assert state.state_category == "curated_common_ion"


def test_nist_source_table_keeps_compact_v2_state_metadata() -> None:
    with NIST_SOURCE_FILE.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 5352
    assert rows[0].keys() == {
        "z",
        "symbol",
        "charge",
        "electron_count",
        "configuration",
        "ground_level",
        "ground_multiplicity",
        "nist_ie_provenance",
    }

    keys = [(row["symbol"], row["charge"]) for row in rows]
    assert len(keys) == len(set(keys))

    provenance = Counter(row["nist_ie_provenance"] for row in rows)
    assert set(provenance) <= {"evaluated", "semiempirical", "theoretical", "missing"}
    assert provenance == {
        "evaluated": 311,
        "semiempirical": 898,
        "theoretical": 4143,
    }
    assert sum(1 for row in rows if not row["ground_level"]) == 138

    multiplicity = Counter(row["ground_multiplicity"] or "<blank>" for row in rows)
    assert multiplicity == {
        "<blank>": 460,
        "1": 919,
        "2": 1586,
        "3": 1028,
        "4": 587,
        "5": 401,
        "6": 207,
        "7": 105,
        "8": 53,
        "9": 5,
        "10": 1,
    }

    by_key = {(row["symbol"], row["charge"]): row for row in rows}
    assert by_key[("Fe", "1")]["ground_level"] == "6D9/2"
    assert by_key[("Fe", "1")]["ground_multiplicity"] == "6"
    assert by_key[("P", "0")]["ground_level"] == "4S°3/2"
    assert by_key[("P", "0")]["ground_multiplicity"] == "4"
    assert by_key[("Pb", "0")]["ground_level"] == "(1/2,1/2)0"
    assert by_key[("Pb", "0")]["ground_multiplicity"] == "3"
    assert by_key[("Pr", "1")]["ground_level"] == "(9/2,1/2)°4"
    assert by_key[("Pr", "1")]["ground_multiplicity"] == "5"
    assert by_key[("Tb", "1")]["ground_multiplicity"] == "7"
    assert by_key[("Dy", "1")]["ground_multiplicity"] == "6"
    assert by_key[("Ho", "1")]["ground_multiplicity"] == "5"
    assert by_key[("Er", "1")]["ground_multiplicity"] == "4"
    assert by_key[("Tm", "1")]["ground_multiplicity"] == "3"
    assert by_key[("Mg", "3")]["nist_ie_provenance"] == "semiempirical"
    assert by_key[("H", "0")]["nist_ie_provenance"] == "theoretical"

NING2022_SOURCE_FILE = ROOT / "data" / "states" / "source" / "ning2022_monoanions.csv"


def test_ning2022_monoanion_source_table_is_compact_and_status_only() -> None:
    with NING2022_SOURCE_FILE.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 92
    assert rows[0].keys() == {
        "z",
        "symbol",
        "charge",
        "electron_count",
        "configuration",
        "ground_level",
        "ground_multiplicity",
        "state_role",
        "physical_status",
        "notes",
    }
    assert "electron_affinity_eV" not in rows[0]
    assert "electron_affinity_uncertainty_eV" not in rows[0]

    keys = [(row["symbol"], row["charge"]) for row in rows]
    assert len(keys) == len(set(keys))
    assert {row["charge"] for row in rows} == {"-1"}
    assert all(int(row["electron_count"]) == int(row["z"]) + 1 for row in rows)

    assert Counter(row["state_role"] for row in rows) == {
        "bound_experimental": 65,
        "bound_provisional": 4,
        "diagnostic_theory": 9,
        "excluded": 14,
    }
    assert Counter(row["physical_status"] for row in rows) == {
        "experimental_or_evaluated": 65,
        "provisional_experimental": 4,
        "theoretical_only": 9,
        "unbound_or_metastable": 14,
    }

    for row in rows:
        if row["state_role"] in {"bound_experimental", "bound_provisional", "diagnostic_theory"}:
            assert row["configuration"]
            assert row["ground_level"]
            assert row["ground_multiplicity"]
        if row["state_role"] == "excluded":
            assert row["physical_status"] == "unbound_or_metastable"

    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["C"]["configuration"] == "[He] 2s2 2p3"
    assert by_symbol["C"]["ground_level"] == "4S3/2"
    assert by_symbol["C"]["ground_multiplicity"] == "4"
    assert by_symbol["Ba"]["configuration"] == "[Xe] 6s2 6p1"
    assert by_symbol["Ba"]["ground_level"] == "2P1/2"
    assert by_symbol["La"]["state_role"] == "bound_experimental"
    assert by_symbol["La"]["ground_level"] == "3F2"
    assert by_symbol["Gd"]["state_role"] == "bound_provisional"
    assert by_symbol["Ho"]["state_role"] == "diagnostic_theory"
    assert by_symbol["Tc"]["physical_status"] == "theoretical_only"
    assert by_symbol["Yb"]["state_role"] == "excluded"
    assert by_symbol["Yb"]["configuration"] == ""
    assert by_symbol["Rn"]["state_role"] == "excluded"

FORMAL_V2_FILE = ROOT / "data" / "states" / "curated" / "formal_atoms_ions.csv"


def test_v2_formal_anion_table_is_explicitly_not_claimed() -> None:
    with FORMAL_V2_FILE.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 46
    assert rows[0].keys() == {
        "z",
        "symbol",
        "charge",
        "electron_count",
        "configuration",
        "ground_multiplicity",
        "state_role",
        "physical_status",
        "state_source",
        "rule_reason",
        "notes",
    }

    keys = [(row["symbol"], row["charge"]) for row in rows]
    assert len(keys) == len(set(keys))
    assert all(int(row["electron_count"]) == int(row["z"]) - int(row["charge"]) for row in rows)
    assert all(row["configuration"] for row in rows)
    assert all(row["ground_multiplicity"] for row in rows)
    assert {row["physical_status"] for row in rows} == {"not_claimed"}

    assert Counter(row["state_role"] for row in rows) == {
        "formal_monoanion": 15,
        "formal_multianion": 31,
    }
    assert Counter(row["state_source"] for row in rows) == {
        "formal_rule": 39,
        "manual_curated": 7,
    }
    assert Counter(row["rule_reason"] for row in rows) == {
        "review_unbound_but_required_by_policy": 8,
        "review_theory_only_but_required_by_policy": 7,
        "p_block_formal_dianion_policy": 25,
        "carbon_pnictogen_formal_trianion_policy": 6,
    }

    group18 = {"He", "Ne", "Ar", "Kr", "Xe", "Rn"}
    assert not any(row["symbol"] in group18 for row in rows)

    p_block = {
        "B",
        "C",
        "N",
        "O",
        "F",
        "Al",
        "Si",
        "P",
        "S",
        "Cl",
        "Ga",
        "Ge",
        "As",
        "Se",
        "Br",
        "In",
        "Sn",
        "Sb",
        "Te",
        "I",
        "Tl",
        "Pb",
        "Bi",
        "Po",
        "At",
    }
    carbon_pnictogens = {"C", "N", "P", "As", "Sb", "Bi"}

    assert {row["symbol"] for row in rows if row["charge"] == "-2"} == p_block
    assert {row["symbol"] for row in rows if row["charge"] == "-3"} == carbon_pnictogens
    assert all(
        row["symbol"] in p_block or row["charge"] == "-1"
        for row in rows
        if int(row["charge"]) < -1
    )

    by_key = {(row["symbol"], row["charge"]): row for row in rows}
    assert by_key[("Be", "-1")]["state_role"] == "formal_monoanion"
    assert by_key[("Be", "-1")]["rule_reason"] == "review_unbound_but_required_by_policy"
    assert by_key[("Tc", "-1")]["state_source"] == "manual_curated"
    assert by_key[("Tc", "-1")]["rule_reason"] == "review_theory_only_but_required_by_policy"
    assert by_key[("Yb", "-1")]["rule_reason"] == "review_unbound_but_required_by_policy"
    assert not any(89 <= int(row["z"]) <= 103 for row in rows)
    assert ("Ac", "-1") not in by_key
    assert ("Pa", "-1") not in by_key
    assert ("Lr", "-1") not in by_key
    assert by_key[("F", "-2")]["configuration"] == "[Ne] 3s1"
    assert by_key[("Bi", "-3")]["configuration"] == "[Hg] 6p6"
