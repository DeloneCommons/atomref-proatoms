"""Import checks for the v2 package subpackage layout."""

from __future__ import annotations


def test_v2_subpackage_imports_match_compatibility_shims() -> None:
    from atomref_proatoms.dataio.basis import BasisBundle as NewBasisBundle
    from atomref_proatoms.dataio.datasets import DATASET_IDS as NEW_DATASET_IDS
    from atomref_proatoms.dataio.paths import STATES_FILE as NEW_STATES_FILE
    from atomref_proatoms.engines.pyscf_backend import SCFSettings as NewSCFSettings
    from atomref_proatoms.engines.spherical_uks import (
        validate_angular_block_size as new_validate_angular_block_size,
    )
    from atomref_proatoms.profiles.artifacts import write_json as new_write_json
    from atomref_proatoms.profiles.grids import log_radial_grid as new_log_radial_grid
    from atomref_proatoms.profiles.qa import QAResult as NewQAResult
    from atomref_proatoms.profiles.radial import radius_at_density as new_radius_at_density
    from atomref_proatoms.states.state_tables import AtomState as NewAtomState

    from atomref_proatoms.artifacts import write_json
    from atomref_proatoms.basis import BasisBundle
    from atomref_proatoms.datasets import DATASET_IDS
    from atomref_proatoms.grids import log_radial_grid
    from atomref_proatoms.paths import STATES_FILE
    from atomref_proatoms.profiles import radius_at_density
    from atomref_proatoms.qa import QAResult
    from atomref_proatoms.scf import SCFSettings
    from atomref_proatoms.spherical_uks import validate_angular_block_size
    from atomref_proatoms.states import AtomState

    assert NewBasisBundle is BasisBundle
    assert NEW_DATASET_IDS == DATASET_IDS
    assert NEW_STATES_FILE == STATES_FILE
    assert NewSCFSettings is SCFSettings
    assert new_validate_angular_block_size is validate_angular_block_size
    assert new_write_json is write_json
    assert new_log_radial_grid is log_radial_grid
    assert NewQAResult is QAResult
    assert new_radius_at_density is radius_at_density
    assert NewAtomState is AtomState
