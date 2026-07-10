"""Public scripting API for atomref-proatoms.

The package intentionally keeps heavy quantum-chemistry dependencies optional.
Importing :mod:`atomref_proatoms` does not require PySCF; functions that run SCF
or evaluate PySCF objects require the ``generator`` extra only when called.
"""

from __future__ import annotations

__version__ = "2.0.0"

from .engines.pyscf_backend import write_scf_npz
from .engines.spherical_scf import (
    apply_x2c_if_requested,
    configure_dft_grid,
    make_spherical_uhf,
    make_spherical_uks,
    validate_spherical_ao_layout,
)
from .exporters.multiwfn_rad import (
    evaluate_scf_radial_density,
    multiwfn_rad_filename,
    write_multiwfn_rad_file,
)
from .exporters.proaim_wfn import atom_wfn_filename, write_atomref_spherical_wfn
from .generator.basis_resolver import (
    BasisCheckResult,
    BasisSpec,
    check_basis_source,
    parse_basis_spec,
)
from .generator.methods import (
    MethodCheck,
    MethodSpec,
    RelativitySpec,
    check_method_with_pyscf,
    parse_method,
    parse_relativity,
)
from .generator.state_selection import StateSelection, select_packaged_states
from .profiles.artifacts import write_wide_profiles_csv
from .profiles.grids import log_radial_grid
from .profiles.interpolation import interpolate_density, load_profile_csv
from .profiles.radial import density_profile_from_mf, derived_radii, radius_at_density
from .states.state_tables import AtomState, validate_atom_state

__all__ = [
    "AtomState",
    "BasisCheckResult",
    "BasisSpec",
    "MethodCheck",
    "MethodSpec",
    "RelativitySpec",
    "StateSelection",
    "__version__",
    "apply_x2c_if_requested",
    "atom_wfn_filename",
    "check_basis_source",
    "check_method_with_pyscf",
    "configure_dft_grid",
    "density_profile_from_mf",
    "derived_radii",
    "evaluate_scf_radial_density",
    "interpolate_density",
    "load_profile_csv",
    "log_radial_grid",
    "make_spherical_uhf",
    "make_spherical_uks",
    "multiwfn_rad_filename",
    "parse_basis_spec",
    "parse_method",
    "parse_relativity",
    "radius_at_density",
    "select_packaged_states",
    "validate_atom_state",
    "validate_spherical_ao_layout",
    "write_atomref_spherical_wfn",
    "write_multiwfn_rad_file",
    "write_scf_npz",
    "write_wide_profiles_csv",
]
