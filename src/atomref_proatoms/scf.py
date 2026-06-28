"""PySCF-facing SCF helpers for spherical proatom generation.

All functions in this module keep PySCF imports lazy so that the package remains
usable for data checks and metadata handling without generator dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .basis import BasisBundle, load_basis_nw_text
from .datasets import assert_dataset_basis_match
from .spherical_uks import (
    apply_x2c_if_requested,
    configure_dft_grid,
    make_spherical_uks,
    validate_spherical_ao_layout,
)
from .states import AtomState

DEFAULT_XC = "PBE0"
DEFAULT_USE_X2C = True
DEFAULT_CONV_TOL = 1e-9
DEFAULT_MAX_CYCLE = 100
DEFAULT_GRID_LEVEL = 4
DEFAULT_GRID_PRUNE = None


@dataclass(frozen=True)
class SCFSettings:
    """Small configuration object for pilot spherical UKS runs."""

    xc: str = DEFAULT_XC
    use_x2c: bool = DEFAULT_USE_X2C
    conv_tol: float = DEFAULT_CONV_TOL
    max_cycle: int = DEFAULT_MAX_CYCLE
    grid_level: int = DEFAULT_GRID_LEVEL
    grid_prune: Any = DEFAULT_GRID_PRUNE
    verbose: int = 3


@dataclass(frozen=True)
class BasisUse:
    """Basis metadata attached to a generated PySCF molecule."""

    basis_id: str
    basis_sha256: str
    basis_path: Path
    source_api_url: str

    def to_json(self) -> dict[str, str]:
        return {
            "basis_id": self.basis_id,
            "basis_sha256": self.basis_sha256,
            "basis_path": str(self.basis_path),
            "source_api_url": self.source_api_url,
        }


@dataclass(frozen=True)
class SCFRun:
    """Return object for a completed PySCF SCF run."""

    mf: Any
    basis: BasisUse
    settings: SCFSettings


def import_pyscf_modules() -> tuple[Any, Any, Any, str]:
    """Import PySCF modules lazily and return ``gto``, ``dft``, ``basis``, version."""

    try:
        import pyscf  # type: ignore[import-not-found]
        from pyscf import dft, gto  # type: ignore[import-not-found]
        from pyscf.gto import basis as pyscf_basis  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "PySCF is required only for generator operations. Install with "
            "`python -m pip install -e .[generator]`."
        ) from exc
    return gto, dft, pyscf_basis, getattr(pyscf, "__version__", "unknown")


def basis_use_from_bundle(bundle: BasisBundle) -> BasisUse:
    source = bundle.manifest["source"]
    return BasisUse(
        basis_id=bundle.basis_id,
        basis_sha256=bundle.basis_sha256,
        basis_path=bundle.basis_path,
        source_api_url=str(source["source_api_url"]),
    )


def build_atom_mol(state: AtomState, bundle: BasisBundle, *, verbose: int = 3):
    """Build a one-center PySCF molecule from a curated state and frozen basis bundle."""

    gto, _dft, pyscf_basis, _version = import_pyscf_modules()
    basis_text = load_basis_nw_text(bundle)
    parsed_basis = pyscf_basis.parse(basis_text, symb=state.symbol)

    mol = gto.Mole()
    mol.atom = f"{state.symbol} 0 0 0"
    mol.basis = {state.symbol: parsed_basis}
    mol.charge = state.charge
    mol.spin = state.spin_2s
    mol.unit = "Bohr"
    mol.cart = False
    mol.symmetry = False
    mol.verbose = verbose
    mol.build()

    validate_spherical_ao_layout(mol)
    return mol, basis_use_from_bundle(bundle)


def run_spherical_uks(
    state: AtomState,
    bundle: BasisBundle,
    *,
    settings: SCFSettings | None = None,
) -> SCFRun:
    """Run the production spherical fractional-occupation UKS model for one state."""

    run_settings = settings or SCFSettings()
    mol, basis_use = build_atom_mol(state, bundle, verbose=run_settings.verbose)
    mf = make_spherical_uks(
        mol,
        xc=run_settings.xc,
        alpha_l_counts=state.alpha_l_counts,
        beta_l_counts=state.beta_l_counts,
    )
    mf.conv_tol = run_settings.conv_tol
    mf.max_cycle = run_settings.max_cycle
    configure_dft_grid(mf, level=run_settings.grid_level, prune=run_settings.grid_prune)
    mf = apply_x2c_if_requested(mf, use_x2c=run_settings.use_x2c)
    mf.kernel()
    return SCFRun(mf=mf, basis=basis_use, settings=run_settings)


def run_dataset_state(
    state: AtomState,
    bundle: BasisBundle,
    *,
    dataset_id: str,
    settings: SCFSettings | None = None,
) -> SCFRun:
    """Run a state after enforcing the dataset/basis no-fallback rule."""

    assert_dataset_basis_match(dataset_id, bundle.basis_id)
    return run_spherical_uks(state, bundle, settings=settings)
