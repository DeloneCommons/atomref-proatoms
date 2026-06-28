from __future__ import annotations

from atomref_proatoms.profiles import validate_profile_metadata
from atomref_proatoms.qa import radii_are_monotonic
from atomref_proatoms.schemas import DENSITY_MODEL, PROFILE_METADATA_SCHEMA_VERSION


def valid_metadata() -> dict[str, object]:
    return {
        "schema_version": PROFILE_METADATA_SCHEMA_VERSION,
        "dataset_id": "pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0",
        "state_id": "C_q0_mult3_hund",
        "density_model": DENSITY_MODEL,
        "method": {
            "engine": "pyscf",
            "engine_version": "placeholder",
            "scf_type": "UKS",
            "xc": "PBE0",
            "relativity": "sf-X2C-1e",
            "basis_id": "x2c-QZVPall",
            "basis_sha256": "0" * 64,
        },
        "state": {
            "symbol": "C",
            "charge": 0,
            "spin_2s": 2,
            "multiplicity": 3,
            "configuration": "1s2 2s2 2p2",
            "spin_model": "free_ion_hund_high_spin",
        },
        "units": {"r": "bohr", "rho": "electron/bohr^3"},
        "derived": {
            "r_iso_0.003_e_bohr3_bohr": 1.0,
            "r_iso_0.001_e_bohr3_bohr": 2.0,
            "r_iso_0.0001_e_bohr3_bohr": 3.0,
        },
        "qa": {
            "scf_converged": True,
            "electron_count_error_qa": 0.0,
            "max_rel_angular_sigma": 0.0,
            "tail_reaches_min_cutoff": True,
            "radii_monotonic": True,
        },
    }


def test_valid_profile_metadata_passes() -> None:
    metadata = valid_metadata()
    assert validate_profile_metadata(metadata) == []
    assert radii_are_monotonic(metadata["derived"])  # type: ignore[arg-type]


def test_profile_metadata_requires_basis_id_and_basis_sha() -> None:
    metadata = valid_metadata()
    method = metadata["method"]
    assert isinstance(method, dict)
    del method["basis_id"]
    errors = validate_profile_metadata(metadata)
    assert any("basis_id" in error for error in errors)
