"""Predefined small pilot profile batches for generator validation."""

from __future__ import annotations

from dataclasses import dataclass

from .datasets import (
    ANION_DYALL_AV4Z,
    ANION_X2C_QZVPALL_S,
    PRIMARY_DYALL_V4Z,
    PRIMARY_X2C_QZVPALL,
)


@dataclass(frozen=True)
class PilotProfile:
    """One state/dataset pair used for a local generator smoke run."""

    state_id: str
    dataset_id: str
    label: str


H_SMOKE = "h_smoke"
NEUTRAL_LIGHT_X2C = "neutral_light_x2c"
ANION_FORMAL_X2C_DIFFUSE = "anion_formal_x2c_diffuse"
ANION_FORMAL_DYALL_AUGMENTED = "anion_formal_dyall_augmented"
HEAVY_DYALL_SMOKE = "heavy_dyall_smoke"
REMAINING_DYALL_PILOTS = "remaining_dyall_pilots"
FULL_PILOT_SUITE = "full_pilot_suite"

_H_SMOKE_PILOTS = (
    PilotProfile(
        "H_q0_mult2_hund",
        PRIMARY_X2C_QZVPALL,
        "Hydrogen neutral x2c-QZVPall smoke profile",
    ),
)

_NEUTRAL_LIGHT_X2C_PILOTS = (
    PilotProfile("H_q0_mult2_hund", PRIMARY_X2C_QZVPALL, "H neutral"),
    PilotProfile("He_q0_mult1_hund", PRIMARY_X2C_QZVPALL, "He neutral"),
    PilotProfile("C_q0_mult3_hund", PRIMARY_X2C_QZVPALL, "C neutral"),
    PilotProfile("N_q0_mult4_hund", PRIMARY_X2C_QZVPALL, "N neutral"),
    PilotProfile("Ne_q0_mult1_hund", PRIMARY_X2C_QZVPALL, "Ne neutral"),
)

_ANION_FORMAL_X2C_DIFFUSE_PILOTS = (
    PilotProfile("I_qm1_mult1_hund", ANION_X2C_QZVPALL_S, "I- x2c-QZVPall-s check"),
    PilotProfile("O_qm2_mult1_hund", ANION_X2C_QZVPALL_S, "O2- x2c-QZVPall-s check"),
    PilotProfile("S_qm2_mult1_hund", ANION_X2C_QZVPALL_S, "S2- x2c-QZVPall-s check"),
)

_ANION_FORMAL_DYALL_AUGMENTED_PILOTS = (
    PilotProfile("I_qm1_mult1_hund", ANION_DYALL_AV4Z, "I- dyall-av4z check"),
    PilotProfile("O_qm2_mult1_hund", ANION_DYALL_AV4Z, "O2- dyall-av4z check"),
    PilotProfile("S_qm2_mult1_hund", ANION_DYALL_AV4Z, "S2- dyall-av4z check"),
)

_HEAVY_DYALL_SMOKE_PILOTS = (
    PilotProfile("Eu_qp3_mult7_hund", PRIMARY_DYALL_V4Z, "Eu3+ Dyall-v4z cation smoke"),
    PilotProfile("U_q0_mult5_hund", PRIMARY_DYALL_V4Z, "U neutral Dyall-v4z smoke"),
)


def combine_pilot_groups(*groups: tuple[PilotProfile, ...]) -> tuple[PilotProfile, ...]:
    """Combine groups, dropping duplicate state/dataset pairs while preserving order."""

    combined: list[PilotProfile] = []
    seen: set[tuple[str, str]] = set()
    for group in groups:
        for pilot in group:
            key = (pilot.state_id, pilot.dataset_id)
            if key in seen:
                continue
            seen.add(key)
            combined.append(pilot)
    return tuple(combined)


PILOT_GROUPS: dict[str, tuple[PilotProfile, ...]] = {
    H_SMOKE: _H_SMOKE_PILOTS,
    NEUTRAL_LIGHT_X2C: _NEUTRAL_LIGHT_X2C_PILOTS,
    ANION_FORMAL_X2C_DIFFUSE: _ANION_FORMAL_X2C_DIFFUSE_PILOTS,
    ANION_FORMAL_DYALL_AUGMENTED: _ANION_FORMAL_DYALL_AUGMENTED_PILOTS,
    HEAVY_DYALL_SMOKE: _HEAVY_DYALL_SMOKE_PILOTS,
    REMAINING_DYALL_PILOTS: combine_pilot_groups(
        _ANION_FORMAL_DYALL_AUGMENTED_PILOTS,
        _HEAVY_DYALL_SMOKE_PILOTS,
    ),
    FULL_PILOT_SUITE: combine_pilot_groups(
        _NEUTRAL_LIGHT_X2C_PILOTS,
        _ANION_FORMAL_X2C_DIFFUSE_PILOTS,
        _ANION_FORMAL_DYALL_AUGMENTED_PILOTS,
        _HEAVY_DYALL_SMOKE_PILOTS,
    ),
}

DEFAULT_PILOT_GROUP = NEUTRAL_LIGHT_X2C


def pilot_group_names() -> tuple[str, ...]:
    """Return pilot group names in the recommended execution order."""

    return tuple(PILOT_GROUPS)


def get_pilot_group(name: str) -> tuple[PilotProfile, ...]:
    """Return one predefined pilot group or raise ``ValueError``."""

    try:
        return PILOT_GROUPS[name]
    except KeyError as exc:
        choices = ", ".join(pilot_group_names())
        raise ValueError(f"Unknown pilot group {name!r}; choices: {choices}") from exc


def filter_pilots(
    pilots: tuple[PilotProfile, ...], *, only_state_ids: set[str] | None = None
) -> tuple[PilotProfile, ...]:
    """Return a pilot subset selected by state ID, preserving original order."""

    if not only_state_ids:
        return pilots
    selected = tuple(pilot for pilot in pilots if pilot.state_id in only_state_ids)
    missing = sorted(only_state_ids - {pilot.state_id for pilot in pilots})
    if missing:
        raise ValueError(f"Requested states are not in the selected pilot group: {missing}")
    return selected
