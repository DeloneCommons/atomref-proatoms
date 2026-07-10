from __future__ import annotations

import pytest

from atomref_proatoms.generator.state_selection import (
    load_packaged_atom_states,
    parse_charges,
    parse_element_range,
    parse_elements,
    select_curated_states,
)


def test_parse_elements_and_ranges() -> None:
    assert parse_elements("c,N,O") == ("C", "N", "O")
    assert parse_element_range("H-Li") == ("H", "He", "Li")
    assert parse_charges("-1,0,+1") == (-1, 0, 1)


def test_select_neutral_packaged_states() -> None:
    states = load_packaged_atom_states()
    selection = select_curated_states(states, elements=("C", "O"), policy="neutral")
    assert {state.symbol for state in selection.states} == {"C", "O"}
    assert all(state.charge == 0 for state in selection.states)
    assert len(selection.states) == 2


def test_select_stockholder_charge_filter() -> None:
    states = load_packaged_atom_states()
    selection = select_curated_states(
        states,
        elements=("C", "O"),
        policy="stockholder",
        charges=(-1, 0),
    )
    assert selection.charges == (-1, 0)
    assert {state.charge for state in selection.states} <= {-1, 0}
    assert any(state.charge == -1 for state in selection.states)


def test_invalid_state_policy_rejected() -> None:
    states = load_packaged_atom_states()
    with pytest.raises(ValueError, match="state policy"):
        select_curated_states(states, elements=("C",), policy="custom")
