"""Dataset identifiers and scope rules for planned proatom profile outputs."""

from __future__ import annotations

from dataclasses import dataclass

PRIMARY_X2C_QZVPALL = "pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0"
PRIMARY_DYALL_V4Z = "pbe0_sfx2c_dyallv4z_h-lr_spherical_v0"
ANION_X2C_QZVPALL_S = "pbe0_sfx2c_x2cqzvpall-s_h-rn_anioncheck_v0"
ANION_DYALL_AV4Z = "pbe0_sfx2c_dyallav4z_h-ba_hf-ra_selected_anions_v0"

DATASET_IDS = (
    PRIMARY_X2C_QZVPALL,
    PRIMARY_DYALL_V4Z,
    ANION_X2C_QZVPALL_S,
    ANION_DYALL_AV4Z,
)

BASIS_TO_DATASETS = {
    "x2c-QZVPall": (PRIMARY_X2C_QZVPALL,),
    "dyall-v4z": (PRIMARY_DYALL_V4Z,),
    "x2c-QZVPall-s": (ANION_X2C_QZVPALL_S,),
    "dyall-av4z": (ANION_DYALL_AV4Z,),
}

DATASET_TO_BASIS = {
    dataset_id: basis_id
    for basis_id, ids in BASIS_TO_DATASETS.items()
    for dataset_id in ids
}


@dataclass(frozen=True)
class DatasetScope:
    dataset_id: str
    basis_id: str
    role: str
    coverage_label: str
    allow_neutral: bool
    allow_cation: bool
    allow_anion: bool
    z_intervals: tuple[tuple[int, int], ...]

    def covers_z(self, z_value: int) -> bool:
        return any(start <= z_value <= end for start, end in self.z_intervals)

    def allows_charge(self, charge: int) -> bool:
        if charge == 0:
            return self.allow_neutral
        if charge > 0:
            return self.allow_cation
        return self.allow_anion


DATASET_SCOPES = {
    PRIMARY_X2C_QZVPALL: DatasetScope(
        PRIMARY_X2C_QZVPALL,
        "x2c-QZVPall",
        "primary_non_diffuse",
        "H-Rn",
        True,
        True,
        True,
        ((1, 86),),
    ),
    PRIMARY_DYALL_V4Z: DatasetScope(
        PRIMARY_DYALL_V4Z,
        "dyall-v4z",
        "primary_non_diffuse_actinide_capable",
        "H-Lr selected states",
        True,
        True,
        True,
        ((1, 103),),
    ),
    ANION_X2C_QZVPALL_S: DatasetScope(
        ANION_X2C_QZVPALL_S,
        "x2c-QZVPall-s",
        "anion_formal_anion_sensitivity",
        "H-Rn anions/formal anions",
        False,
        False,
        True,
        ((1, 86),),
    ),
    ANION_DYALL_AV4Z: DatasetScope(
        ANION_DYALL_AV4Z,
        "dyall-av4z",
        "selected_anion_sensitivity",
        "H-Ba, Hf-Ra, Rf-Og selected anions",
        False,
        False,
        True,
        ((1, 56), (72, 88), (104, 118)),
    ),
}


def dataset_scope(dataset_id: str) -> DatasetScope:
    try:
        return DATASET_SCOPES[dataset_id]
    except KeyError as exc:
        raise ValueError(f"Unknown dataset_id: {dataset_id}") from exc


def expected_basis_for_dataset(dataset_id: str) -> str:
    return dataset_scope(dataset_id).basis_id


def assert_dataset_basis_match(dataset_id: str, basis_id: str) -> None:
    expected = expected_basis_for_dataset(dataset_id)
    if basis_id != expected:
        raise ValueError(
            f"No silent basis fallback allowed: dataset {dataset_id} "
            f"requires {expected}, got {basis_id}"
        )


def state_allowed_in_dataset(dataset_id: str, *, z: int, charge: int) -> bool:
    scope = dataset_scope(dataset_id)
    return scope.covers_z(z) and scope.allows_charge(charge)
