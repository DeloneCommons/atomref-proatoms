"""Curated-state selection helpers for the MVP generator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..dataio.basis import ELEMENTS, Z_BY_SYMBOL
from ..dataio.resources import resource_path
from ..states.state_tables import AtomState, load_atom_states, selection_count_summary

StatePolicy = Literal["neutral", "stockholder"]


@dataclass(frozen=True)
class StateSelection:
    """Result of selecting curated atomref-proatoms states."""

    policy: StatePolicy
    elements: tuple[str, ...]
    charges: tuple[int, ...] | None
    states: tuple[AtomState, ...]
    warnings: tuple[str, ...] = ()

    @property
    def state_ids(self) -> tuple[str, ...]:
        return tuple(state.state_id for state in self.states)

    def summary(self) -> dict[str, object]:
        data = selection_count_summary(list(self.states))
        data.update(
            {
                "policy": self.policy,
                "elements": list(self.elements),
                "charges": list(self.charges) if self.charges is not None else None,
                "state_ids": list(self.state_ids),
                "warnings": list(self.warnings),
            }
        )
        return data


def normalize_element_symbol(symbol: str) -> str:
    """Normalize one element symbol and reject unknown elements."""

    value = str(symbol).strip()
    if not value:
        raise ValueError("empty element symbol")
    normalized = value[0].upper() + value[1:].lower()
    if normalized not in Z_BY_SYMBOL:
        raise ValueError(f"unknown element symbol: {symbol!r}")
    return normalized


def parse_elements(elements: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Parse comma-separated or list-like element requests."""

    raw_items = elements.split(",") if isinstance(elements, str) else list(elements)
    result: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        normalized = normalize_element_symbol(str(item))
        if normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    if not result:
        raise ValueError("at least one element is required")
    return tuple(result)


def parse_element_range(value: str) -> tuple[str, ...]:
    """Parse a closed element range like ``H-Ar``."""

    parts = [part.strip() for part in str(value).split("-", 1)]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("element range must look like H-Ar")
    start = normalize_element_symbol(parts[0])
    end = normalize_element_symbol(parts[1])
    start_z = Z_BY_SYMBOL[start]
    end_z = Z_BY_SYMBOL[end]
    if start_z > end_z:
        raise ValueError(f"element range start {start} is after end {end}")
    return tuple(ELEMENTS[start_z - 1 : end_z])


def parse_charges(value: str | list[int] | tuple[int, ...] | None) -> tuple[int, ...] | None:
    """Parse an optional comma-separated charge filter."""

    if value is None:
        return None
    raw_items = value.split(",") if isinstance(value, str) else list(value)
    result: list[int] = []
    seen: set[int] = set()
    for item in raw_items:
        text = str(item).strip()
        if text.startswith("+"):
            text = text[1:]
        if not text:
            raise ValueError("empty charge value")
        charge = int(text)
        if charge not in seen:
            result.append(charge)
            seen.add(charge)
    return tuple(result)


def parse_state_policy(policy: str) -> StatePolicy:
    value = str(policy).strip().lower()
    if value not in {"neutral", "stockholder"}:
        raise ValueError("state policy must be one of: neutral, stockholder")
    return value  # type: ignore[return-value]


def load_packaged_atom_states(*, resource_root: Path | str | None = None) -> list[AtomState]:
    """Load the packaged curated atom state table."""

    with resource_path("states/atom_states_v2.json", resource_root=resource_root) as path:
        return load_atom_states(path)


def select_curated_states(
    states: list[AtomState],
    *,
    elements: tuple[str, ...] | list[str],
    policy: str,
    charges: tuple[int, ...] | list[int] | None = None,
) -> StateSelection:
    """Select only curated MVP states: neutral or stockholder."""

    normalized_elements = tuple(parse_elements(tuple(elements)))
    selected_policy = parse_state_policy(policy)
    selected_charges = tuple(int(charge) for charge in charges) if charges is not None else None
    warnings: list[str] = []
    allowed_elements = set(normalized_elements)
    result: list[AtomState] = []
    for state in states:
        if state.symbol not in allowed_elements:
            continue
        if selected_policy == "neutral" and state.charge != 0:
            continue
        if selected_charges is not None and state.charge not in selected_charges:
            continue
        result.append(state)
    if selected_policy == "neutral" and selected_charges is not None:
        nonzero = [charge for charge in selected_charges if charge != 0]
        if nonzero:
            warnings.append("neutral state policy ignores nonzero charge filters")
    if not result:
        raise ValueError(
            "state selection produced no states for "
            f"elements={list(normalized_elements)!r}, policy={selected_policy!r}, "
            f"charges={list(selected_charges) if selected_charges is not None else None!r}"
        )
    return StateSelection(
        policy=selected_policy,
        elements=normalized_elements,
        charges=selected_charges,
        states=tuple(result),
        warnings=tuple(warnings),
    )


def select_packaged_states(
    *,
    elements: tuple[str, ...] | list[str],
    policy: str = "neutral",
    charges: tuple[int, ...] | list[int] | None = None,
    resource_root: Path | str | None = None,
) -> StateSelection:
    """Load packaged states and apply the MVP selection policy."""

    return select_curated_states(
        load_packaged_atom_states(resource_root=resource_root),
        elements=elements,
        policy=policy,
        charges=charges,
    )
