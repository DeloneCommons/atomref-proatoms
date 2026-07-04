"""Curated atomic-state loading and validation utilities."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..dataio.basis import ELEMENTS
from ..dataio.schemas import (
    ALLOWED_ATOM_STATE_SCHEMA_VERSIONS,
    ALLOWED_OCCUPATION_POLICIES,
    ALLOWED_SPIN_MODELS,
    ALLOWED_SPIN_VARIANTS,
    ATOM_STATE_SCHEMA_VERSION,
    FORBIDDEN_STATE_FIELDS,
    REQUIRED_STATE_FIELDS,
)

ALLOWED_STATE_CATEGORIES = {
    "nist_reference",
    "ning2022_monoanion_reference",
    "formal_anion_reference",
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
    def alpha_l_counts(self) -> dict[int, float]:
        return {int(key): float(value) for key, value in self.record["alpha_l_counts"].items()}

    @property
    def beta_l_counts(self) -> dict[int, float]:
        return {int(key): float(value) for key, value in self.record["beta_l_counts"].items()}

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


def _l_count_sum(counts: dict[str, Any]) -> float:
    return sum(float(value) for value in counts.values())


def _nearly_equal(left: float, right: float, *, tol: float = 1e-9) -> bool:
    return abs(left - right) <= tol


def expected_alpha_beta_counts(record: dict[str, Any]) -> tuple[float, float, float]:
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
    schema_version = record["schema_version"]
    if schema_version not in ALLOWED_ATOM_STATE_SCHEMA_VERSIONS:
        errors.append(f"{state_id}: unexpected schema_version {schema_version!r}")
    if record["electron_count"] != z_value - int(record["charge"]):
        errors.append(f"{state_id}: electron_count != z - charge")
    if record["multiplicity"] != int(record["spin_2s"]) + 1:
        errors.append(f"{state_id}: multiplicity != spin_2s + 1")
    if record["spin_model"] not in ALLOWED_SPIN_MODELS:
        errors.append(f"{state_id}: unexpected spin_model {record['spin_model']!r}")
    if record["spin_variant"] not in ALLOWED_SPIN_VARIANTS:
        errors.append(f"{state_id}: unexpected spin_variant {record['spin_variant']!r}")
    if record["occupation_policy"] not in ALLOWED_OCCUPATION_POLICIES:
        errors.append(f"{state_id}: unexpected occupation_policy")
    if record["state_category"] not in ALLOWED_STATE_CATEGORIES:
        errors.append(f"{state_id}: unexpected state_category {record['state_category']!r}")
    if not isinstance(record["notes"], list):
        errors.append(f"{state_id}: notes must be a list")

    alpha, beta, total = expected_alpha_beta_counts(record)
    if not _nearly_equal(total, float(record["electron_count"])):
        errors.append(f"{state_id}: alpha/beta l-counts do not sum to electron_count")
    if not _nearly_equal(alpha - beta, float(record["spin_2s"])):
        errors.append(f"{state_id}: alpha/beta l-counts do not match spin_2s")
    expected_prefix = (
        f"{symbol}_{charge_label(int(record['charge']))}_"
        f"mult{record['multiplicity']}_"
    )
    if not state_id.startswith(expected_prefix):
        errors.append(f"{state_id}: expected state_id prefix {expected_prefix}")
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
    schema_versions = {str(state.record["schema_version"]) for state in states}
    if schema_versions != {ATOM_STATE_SCHEMA_VERSION}:
        errors.append(f"State collection has mixed or unsupported schema versions: {schema_versions}")
        return errors

    expected_summary = {
        "state_count": 495,
        "neutral_count": 103,
        "cation_count": 286,
        "anion_count": 106,
        "by_category": {
            "formal_anion_reference": 40,
            "ning2022_monoanion_reference": 66,
            "nist_reference": 389,
        },
        "by_charge": {
            "-3": 6,
            "-2": 20,
            "-1": 80,
            "0": 103,
            "1": 102,
            "2": 95,
            "3": 89,
        },
        "by_spin_variant": {"curated_multiplicity": 495},
    }

    for key, expected in expected_summary.items():
        if summary[key] != expected:
            errors.append(f"State collection {key}={summary[key]!r} != {expected!r}")

    for state in states:
        if state.state_category == "formal_anion_reference":
            notes = " ".join(str(note) for note in state.record.get("notes", []))
            if (
                "not a claim of a stable" not in notes
                and "not a stable isolated atomic anion" not in notes
            ):
                errors.append(f"{state.state_id}: formal anion note is missing/unclear")
    return errors
