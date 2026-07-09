"""Import checks for the v2 package subpackage layout."""

from __future__ import annotations

import importlib.util

REMOVED_MODULES = (
    "atomref_proatoms.artifacts",
    "atomref_proatoms.basis",
    "atomref_proatoms.build_plan",
    "atomref_proatoms.datasets",
    "atomref_proatoms.grids",
    "atomref_proatoms.paths",
    "atomref_proatoms.qa",
    "atomref_proatoms.scf",
    "atomref_proatoms.schemas",
    "atomref_proatoms.spherical_uks",
    "atomref_proatoms.engines.spherical_uks",
)


def test_v2_subpackage_imports_are_canonical() -> None:
    from atomref_proatoms.dataio.basis import BasisBundle
    from atomref_proatoms.dataio.datasets import DATASET_IDS
    from atomref_proatoms.dataio.paths import STATES_FILE
    from atomref_proatoms.engines.pyscf_backend import SCFSettings
    from atomref_proatoms.engines.spherical_scf import validate_angular_block_size
    from atomref_proatoms.exporters.multiwfn_rad import write_multiwfn_rad_file
    from atomref_proatoms.exporters.proaim_wfn import write_proaim_wfn
    from atomref_proatoms.profiles import radius_at_density
    from atomref_proatoms.profiles.artifacts import write_json
    from atomref_proatoms.profiles.grids import log_radial_grid
    from atomref_proatoms.profiles.qa import QAResult
    from atomref_proatoms.profiles.radial import radius_at_density as radial_radius_at_density
    from atomref_proatoms.states import AtomState
    from atomref_proatoms.states.state_tables import AtomState as StateTableAtomState
    from atomref_proatoms.validation.wfn_density import parse_wfn_file

    assert BasisBundle.__name__ == "BasisBundle"
    assert DATASET_IDS
    assert STATES_FILE.name == "atom_states_v2.json"
    assert SCFSettings.__name__ == "SCFSettings"
    assert callable(validate_angular_block_size)
    assert callable(write_json)
    assert callable(log_radial_grid)
    assert QAResult.__name__ == "QAResult"
    assert callable(write_multiwfn_rad_file)
    assert callable(write_proaim_wfn)
    assert radius_at_density is radial_radius_at_density
    assert AtomState is StateTableAtomState
    assert callable(parse_wfn_file)


def test_old_compatibility_modules_are_removed() -> None:
    for module_name in REMOVED_MODULES:
        assert importlib.util.find_spec(module_name) is None
