"""Predefined small pilot profile batches for generator validation."""

from __future__ import annotations

from dataclasses import dataclass

from .datasets import ANION_X2C_QZVPALL_S, PRIMARY_DYALL_V4Z, PRIMARY_X2C_QZVPALL


@dataclass(frozen=True)
class PilotProfile:
    """One state/dataset pair used for a local generator smoke run."""

    state_id: str
    dataset_id: str
    label: str


H_SMOKE = "h_smoke"
NEUTRAL_LIGHT_X2C = "neutral_light_x2c"
ANION_FORMAL_X2C_DIFFUSE = "anion_formal_x2c_diffuse"
HEAVY_DYALL_SMOKE = "heavy_dyall_smoke"

PILOT_GROUPS: dict[str, tuple[PilotProfile, ...]] = {
    H_SMOKE: (
        PilotProfile(
            "H_q0_mult2_hund",
            PRIMARY_X2C_QZVPALL,
            "Hydrogen neutral x2c-QZVPall smoke profile",
        ),
    ),
    NEUTRAL_LIGHT_X2C: (
        PilotProfile("H_q0_mult2_hund", PRIMARY_X2C_QZVPALL, "H neutral"),
        PilotProfile("He_q0_mult1_hund", PRIMARY_X2C_QZVPALL, "He neutral"),
        PilotProfile("C_q0_mult3_hund", PRIMARY_X2C_QZVPALL, "C neutral"),
        PilotProfile("N_q0_mult4_hund", PRIMARY_X2C_QZVPALL, "N neutral"),
        PilotProfile("Ne_q0_mult1_hund", PRIMARY_X2C_QZVPALL, "Ne neutral"),
    ),
    ANION_FORMAL_X2C_DIFFUSE: (
        PilotProfile("I_qm1_mult1_hund", ANION_X2C_QZVPALL_S, "I- diffuse-basis check"),
        PilotProfile("O_qm2_mult1_hund", ANION_X2C_QZVPALL_S, "O2- formal-anion check"),
        PilotProfile("S_qm2_mult1_hund", ANION_X2C_QZVPALL_S, "S2- formal-anion check"),
    ),
    HEAVY_DYALL_SMOKE: (
        PilotProfile("Eu_qp3_mult7_hund", PRIMARY_DYALL_V4Z, "Eu3+ Dyall-v4z cation smoke"),
        PilotProfile("U_q0_mult5_hund", PRIMARY_DYALL_V4Z, "U neutral Dyall-v4z smoke"),
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
