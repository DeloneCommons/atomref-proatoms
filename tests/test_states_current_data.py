from __future__ import annotations

from pathlib import Path

from atomref_proatoms.states import (
    load_atom_states,
    selection_count_summary,
    validate_state_collection,
)

ROOT = Path(__file__).resolve().parents[1]
STATES_FILE = ROOT / "data" / "states" / "curated" / "atom_states_v1.json"


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
