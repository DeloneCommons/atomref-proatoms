"""Curated atomic-state loading and validation utilities."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .basis import ELEMENTS
from .schemas import (
    ATOM_STATE_SCHEMA_VERSION,
    DEFAULT_OCCUPATION_POLICY,
    DEFAULT_SPIN_MODEL,
    DEFAULT_SPIN_VARIANT,
    FORBIDDEN_STATE_FIELDS,
    REQUIRED_STATE_FIELDS,
)

ACTINIDE_Z_RANGE = range(89, 104)
ALLOWED_STATE_CATEGORIES = {
    "nist_ground_state",
    "curated_common_ion",
    "formal_crystal_ion_reference",
    "diagnostic_only",
}


@dataclass(frozen=True)
class AtomState:
    """A generator-ready curated atomic state."""

    record: dict[str, Any]

    @property
    def state_id(self) -> str:
        return str(self.record["state_id"])

    @property
    def symbol(self) -> str:
        return str(self.record["symbol"])

    @property
    def z(self) -> int:
        return int(self.record["z"])

    @property
    def charge(self) -> int:
        return int(self.record["charge"])

    @property
    def electron_count(self) -> int:
        return int(self.record["electron_count"])

    @property
    def spin_2s(self) -> int:
        return int(self.record["spin_2s"])

    @property
    def multiplicity(self) -> int:
        return int(self.record["multiplicity"])

    @property
    def state_category(self) -> str:
        return str(self.record["state_category"])


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json_digest(data: Any) -> str:
    import hashlib

    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def state_digest(record: dict[str, Any]) -> str:
    return canonical_json_digest(record)


def charge_label(charge: int) -> str:
    if charge == 0:
        return "q0"
    if charge > 0:
        return f"qp{charge}"
    return f"qm{abs(charge)}"


def _l_count_sum(counts: dict[str, Any]) -> int:
    return sum(int(value) for value in counts.values())


def expected_alpha_beta_counts(record: dict[str, Any]) -> tuple[int, int, int]:
    alpha = _l_count_sum(record["alpha_l_counts"])
    beta = _l_count_sum(record["beta_l_counts"])
    return alpha, beta, alpha + beta


def validate_atom_state(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_STATE_FIELDS - set(record))
    if missing:
        errors.append(f"{record.get('state_id', '<unknown>')}: missing fields {missing}")
    forbidden = sorted(FORBIDDEN_STATE_FIELDS & set(record))
    if forbidden:
        errors.append(
            f"{record.get('state_id', '<unknown>')}: forbidden per-record source fields {forbidden}"
        )
    if errors:
        return errors

    state_id = record["state_id"]
    symbol = record["symbol"]
    if symbol not in ELEMENTS:
        errors.append(f"{state_id}: unknown element symbol {symbol!r}")
    z_value = int(record["z"])
    if 1 <= z_value <= len(ELEMENTS) and ELEMENTS[z_value - 1] != symbol:
        errors.append(f"{state_id}: z={z_value} does not match symbol {symbol}")
    if record["schema_version"] != ATOM_STATE_SCHEMA_VERSION:
        errors.append(f"{state_id}: unexpected schema_version {record['schema_version']!r}")
    if record["electron_count"] != z_value - int(record["charge"]):
        errors.append(f"{state_id}: electron_count != z - charge")
    if record["multiplicity"] != int(record["spin_2s"]) + 1:
        errors.append(f"{state_id}: multiplicity != spin_2s + 1")
    if record["spin_model"] != DEFAULT_SPIN_MODEL:
        errors.append(f"{state_id}: unexpected spin_model {record['spin_model']!r}")
    if record["spin_variant"] != DEFAULT_SPIN_VARIANT:
        errors.append(f"{state_id}: unexpected spin_variant {record['spin_variant']!r}")
    if record["occupation_policy"] != DEFAULT_OCCUPATION_POLICY:
        errors.append(f"{state_id}: unexpected occupation_policy")
    if record["state_category"] not in ALLOWED_STATE_CATEGORIES:
        errors.append(f"{state_id}: unexpected state_category {record['state_category']!r}")
    if not isinstance(record["notes"], list):
        errors.append(f"{state_id}: notes must be a list")

    alpha, beta, total = expected_alpha_beta_counts(record)
    if total != int(record["electron_count"]):
        errors.append(f"{state_id}: alpha/beta l-counts do not sum to electron_count")
    if alpha - beta != int(record["spin_2s"]):
        errors.append(f"{state_id}: alpha/beta l-counts do not match spin_2s")
    expected_id = (
        f"{symbol}_{charge_label(int(record['charge']))}_"
        f"mult{record['multiplicity']}_hund"
    )
    if state_id != expected_id:
        errors.append(f"{state_id}: expected state_id {expected_id}")
    if z_value in ACTINIDE_Z_RANGE and int(record["charge"]) > 0:
        errors.append(f"{state_id}: actinide cations are not part of v0 production")
    return errors


def load_atom_states(path: Path) -> list[AtomState]:
    records = read_json(path)
    if not isinstance(records, list):
        raise ValueError(f"Expected list of state records in {path}")
    states: list[AtomState] = []
    errors: list[str] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            errors.append("State record is not a JSON object")
            continue
        sid = str(record.get("state_id", "<missing>"))
        if sid in seen:
            errors.append(f"Duplicate state_id: {sid}")
        seen.add(sid)
        errors.extend(validate_atom_state(record))
        states.append(AtomState(record))
    if errors:
        raise ValueError("Invalid atom states:\n" + "\n".join(errors))
    return states


def selection_count_summary(states: list[AtomState]) -> dict[str, Any]:
    by_category = Counter(state.state_category for state in states)
    by_charge = Counter(str(state.charge) for state in states)
    by_spin_variant = Counter(str(state.record["spin_variant"]) for state in states)
    neutral = sum(1 for state in states if state.charge == 0)
    cations = sum(1 for state in states if state.charge > 0)
    anions = sum(1 for state in states if state.charge < 0)
    return {
        "state_count": len(states),
        "neutral_count": neutral,
        "cation_count": cations,
        "anion_count": anions,
        "by_category": dict(sorted(by_category.items())),
        "by_charge": dict(sorted(by_charge.items(), key=lambda item: int(item[0]))),
        "by_spin_variant": dict(sorted(by_spin_variant.items())),
    }


def validate_state_collection(states: list[AtomState]) -> list[str]:
    errors: list[str] = []
    summary = selection_count_summary(states)
    expected_summary = {
        "state_count": 173,
        "neutral_count": 103,
        "cation_count": 57,
        "anion_count": 13,
        "by_category": {
            "curated_common_ion": 61,
            "formal_crystal_ion_reference": 9,
            "nist_ground_state": 103,
        },
        "by_charge": {
            "-3": 5,
            "-2": 4,
            "-1": 4,
            "0": 103,
            "1": 9,
            "2": 22,
            "3": 23,
            "4": 3,
        },
        "by_spin_variant": {"hund_high_spin": 173},
    }
    for key, expected in expected_summary.items():
        if summary[key] != expected:
            errors.append(f"State collection {key}={summary[key]!r} != {expected!r}")
    for state in states:
        if state.state_category == "formal_crystal_ion_reference":
            notes = " ".join(str(note) for note in state.record.get("notes", []))
            if "not a claim of a stable free isolated atomic anion" not in notes:
                errors.append(f"{state.state_id}: formal anion note is missing/unclear")
        if (
            state.symbol in {"F", "Cl", "Br", "I"}
            and state.charge == -1
            and state.state_category != "curated_common_ion"
        ):
            errors.append(f"{state.state_id}: halide must be curated_common_ion")
    return errors
