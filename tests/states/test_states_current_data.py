from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from atomref_proatoms.dataio.paths import STATES_FILE
from atomref_proatoms.states import (
    load_atom_states,
    selection_count_summary,
    validate_state_collection,
)

ROOT = Path(__file__).resolve().parents[2]
NIST_SOURCE_FILE = (
    ROOT / "data" / "states" / "source" / "nist_gsie" / "nist_neutral_cation_states.csv"
)

def test_current_state_table_loads_and_matches_expected_counts() -> None:
    states = load_atom_states(STATES_FILE)
    summary = selection_count_summary(states)
    assert summary["state_count"] == 501
    assert summary["neutral_count"] == 103
    assert summary["cation_count"] == 286
    assert summary["anion_count"] == 112
    assert summary["by_category"] == {
        "formal_anion_reference": 40,
        "ning2022_monoanion_reference": 72,
        "nist_reference": 389,
    }
    assert summary["by_charge"] == {
        "-3": 6,
        "-2": 20,
        "-1": 86,
        "0": 103,
        "1": 102,
        "2": 95,
        "3": 89,
    }
    assert summary["by_spin_variant"] == {"curated_multiplicity": 501}
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
        alpha = sum(float(value) for value in state.record["alpha_l_counts"].values())
        beta = sum(float(value) for value in state.record["beta_l_counts"].values())
        assert abs((alpha + beta) - state.electron_count) < 1e-9
        assert abs((alpha - beta) - state.spin_2s) < 1e-9
        assert state.record["spin_model"] == "curated_ground_multiplicity"


def test_actinide_cations_are_in_active_v2_state_table() -> None:
    states = load_atom_states(STATES_FILE)
    assert any(89 <= state.z <= 103 and state.charge > 0 for state in states)


def test_formal_anions_and_halides_are_labeled_as_expected() -> None:
    for state in load_atom_states(STATES_FILE):
        if state.charge < -1:
            assert state.state_category == "formal_anion_reference"
        if state.symbol in {"F", "Cl", "Br", "I"} and state.charge == -1:
            assert state.state_category == "ning2022_monoanion_reference"


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

NING2022_SOURCE_FILE = ROOT / "data" / "states" / "source" / "ning2022" / "ning2022_monoanions.csv"


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

    assert len(rows) == 40
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
        "formal_monoanion": 14,
        "formal_multianion": 26,
    }
    assert Counter(row["state_source"] for row in rows) == {
        "formal_rule": 34,
        "manual_curated": 6,
    }
    assert Counter(row["rule_reason"] for row in rows) == {
        "review_unbound_but_required_by_policy": 8,
        "review_theory_only_but_required_by_policy": 6,
        "p_block_formal_dianion_policy": 20,
        "carbon_pnictogen_formal_trianion_policy": 6,
    }

    group18 = {"He", "Ne", "Ar", "Kr", "Xe", "Rn"}
    assert not any(row["symbol"] in group18 for row in rows)

    p_block = {
        "B",
        "C",
        "N",
        "O",
        "Al",
        "Si",
        "P",
        "S",
        "Ga",
        "Ge",
        "As",
        "Se",
        "In",
        "Sn",
        "Sb",
        "Te",
        "Tl",
        "Pb",
        "Bi",
        "Po",
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
    assert ("F", "-2") not in by_key
    assert ("Cl", "-2") not in by_key
    assert ("Br", "-2") not in by_key
    assert ("I", "-2") not in by_key
    assert ("At", "-2") not in by_key
    assert ("Fr", "-1") not in by_key
    assert by_key[("Bi", "-3")]["configuration"] == "[Hg] 6p6"

V2_SELECTION_FILE = ROOT / "data" / "states" / "selection" / "required_states_v2.csv"
V2_STATES_CSV_FILE = ROOT / "data" / "states" / "curated" / "atom_states_v2.csv"
V2_STATES_JSON_FILE = ROOT / "data" / "states" / "curated" / "atom_states_v2.json"
V2_STATES_SUMMARY_FILE = ROOT / "data" / "states" / "curated" / "atom_states_summary_v2.json"


def test_v2_required_states_table_matches_charge_policy() -> None:
    with V2_SELECTION_FILE.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 501
    assert rows[0].keys() == {
        "z",
        "symbol",
        "charge",
        "electron_count",
        "state_source",
        "source_table",
        "state_role",
        "physical_status",
        "include_reason",
    }

    keys = [(row["symbol"], row["charge"]) for row in rows]
    assert len(keys) == len(set(keys))
    assert all(int(row["electron_count"]) > 0 for row in rows)
    assert all(int(row["charge"]) <= 3 for row in rows)
    assert Counter(row["charge"] for row in rows) == {
        "-3": 6,
        "-2": 20,
        "-1": 86,
        "0": 103,
        "1": 102,
        "2": 95,
        "3": 89,
    }
    assert {row["source_table"] for row in rows} == {
        "source/nist_gsie/nist_neutral_cation_states.csv",
        "source/ning2022/ning2022_monoanions.csv",
        "curated/formal_atoms_ions.csv",
    }

    group18 = {"He", "Ne", "Ar", "Kr", "Xe", "Rn"}
    assert not any(row["symbol"] in group18 and int(row["charge"]) < 0 for row in rows)
    assert ("H", "1") not in keys
    assert ("He", "2") not in keys
    assert ("He", "3") not in keys
    assert ("Fr", "-1") in keys
    assert ("Ra", "-1") in keys
    assert ("Ac", "-1") in keys
    assert ("Th", "-1") in keys
    assert ("Pa", "-1") in keys
    assert ("U", "-1") in keys
    assert ("Np", "-1") not in keys
    assert ("Lr", "-1") not in keys
    assert ("F", "-2") not in keys
    assert ("Cl", "-2") not in keys
    assert ("Br", "-2") not in keys
    assert ("I", "-2") not in keys
    assert ("At", "-2") not in keys


def test_v2_curated_json_loads_with_curated_multiplicities() -> None:
    states = load_atom_states(V2_STATES_JSON_FILE)
    summary = selection_count_summary(states)

    assert summary["state_count"] == 501
    assert summary["neutral_count"] == 103
    assert summary["cation_count"] == 286
    assert summary["anion_count"] == 112
    assert summary["by_category"] == {
        "formal_anion_reference": 40,
        "ning2022_monoanion_reference": 72,
        "nist_reference": 389,
    }
    assert summary["by_spin_variant"] == {"curated_multiplicity": 501}

    by_key = {(state.symbol, state.charge): state for state in states}
    ce = by_key[("Ce", 0)]
    assert ce.multiplicity == 1
    assert ce.record["state_id"] == "Ce_q0_mult1_nist"
    assert ce.record["alpha_l_counts"]["2"] == 10.5
    assert ce.record["beta_l_counts"]["3"] == 0.5

    carbon_anion = by_key[("C", -1)]
    assert carbon_anion.record["state_source"] == "ning2022"
    assert carbon_anion.record["state_role"] == "bound_experimental"

    nitrogen_anion = by_key[("N", -1)]
    assert nitrogen_anion.record["state_category"] == "formal_anion_reference"
    assert nitrogen_anion.record["physical_status"] == "not_claimed"


def test_v2_summary_records_policy_exclusions() -> None:
    import json

    summary = json.loads(V2_STATES_SUMMARY_FILE.read_text(encoding="utf-8"))
    assert summary["schema_version"] == "atomref.proatoms.state_build_summary.v2"
    assert summary["state_count"] == 501
    assert summary["by_source"] == {
        "formal_rule": 34,
        "manual_curated": 6,
        "ning2022": 72,
        "nist_gsie": 389,
    }
    assert summary["diagnostics"] == {
        "skipped_cations": [
            {
                "symbol": "H",
                "charge": "1",
                "reason": "missing_nist_electron_bearing_state",
            },
            {
                "symbol": "He",
                "charge": "2",
                "reason": "missing_nist_electron_bearing_state",
            },
            {
                "symbol": "He",
                "charge": "3",
                "reason": "missing_nist_electron_bearing_state",
            },
        ]
    }


def test_v2_review_csv_is_json_subset_without_l_counts() -> None:
    with V2_STATES_CSV_FILE.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 501
    assert rows[0].keys() == {
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
    }
    assert "alpha_l_counts" not in rows[0]
    assert "beta_l_counts" not in rows[0]
