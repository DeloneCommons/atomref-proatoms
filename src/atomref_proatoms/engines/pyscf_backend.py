"""PySCF-facing SCF helpers for spherical proatom generation.

All functions in this module keep PySCF imports lazy so that the package remains
usable for data checks and metadata handling without generator dependencies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..dataio.basis import BasisBundle, load_basis_nw_text, sha256_file
from ..dataio.datasets import ProfileDatasetConfig, assert_dataset_basis_match
from ..dataio.paths import repo_relative_path
from ..states.state_tables import AtomState, state_digest
from .spherical_uks import (
    apply_x2c_if_requested,
    configure_dft_grid,
    make_spherical_uks,
    validate_spherical_ao_layout,
)

DEFAULT_XC = "PBE0"
DEFAULT_USE_X2C = True
DEFAULT_CONV_TOL = 1e-9
DEFAULT_MAX_CYCLE = 100
DEFAULT_GRID_LEVEL = 4
DEFAULT_GRID_PRUNE = None
SCF_ARTIFACT_SCHEMA_VERSION = "atomref.proatoms.scf_artifact.v1"
SCF_REUSE_FINGERPRINT_KEYS = (
    "basis_sha256",
    "state_record_sha256",
    "scf_settings_sha256",
    "engine_version",
    "density_model",
    "scf_type",
)


@dataclass(frozen=True)
class SCFSettings:
    """Small configuration object for spherical UKS runs."""

    xc: str = DEFAULT_XC
    use_x2c: bool = DEFAULT_USE_X2C
    conv_tol: float = DEFAULT_CONV_TOL
    max_cycle: int = DEFAULT_MAX_CYCLE
    grid_level: int = DEFAULT_GRID_LEVEL
    grid_prune: Any = DEFAULT_GRID_PRUNE
    verbose: int = 3
    stdout: Any | None = None
    chkfile: Path | None = None

    def to_fingerprint_json(self) -> dict[str, Any]:
        """Return settings that affect numerical SCF results."""

        return {
            "xc": self.xc,
            "use_x2c": self.use_x2c,
            "conv_tol": self.conv_tol,
            "max_cycle": self.max_cycle,
            "grid_level": self.grid_level,
            "grid_prune": self.grid_prune,
        }


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
            "basis_path": repo_relative_path(self.basis_path),
            "source_api_url": self.source_api_url,
        }


@dataclass(frozen=True)
class SCFRun:
    """Return object for a completed PySCF SCF run."""

    mf: Any
    basis: BasisUse
    settings: SCFSettings


@dataclass(frozen=True)
class SCFArtifactPaths:
    """File paths for one saved state/dataset SCF artifact."""

    root: Path
    dataset_id: str
    state_id: str

    @property
    def state_dir(self) -> Path:
        return self.root / self.dataset_id / self.state_id

    @property
    def chk(self) -> Path:
        return self.state_dir / "scf.chk"

    @property
    def npz(self) -> Path:
        return self.state_dir / "scf.npz"

    @property
    def metadata(self) -> Path:
        return self.state_dir / "scf.json"

    @property
    def log(self) -> Path:
        return self.state_dir / "scf.log"

    def required_files(self) -> tuple[Path, Path, Path, Path]:
        return (self.chk, self.npz, self.metadata, self.log)


def scf_artifact_paths(root: Path, dataset_id: str, state_id: str) -> SCFArtifactPaths:
    return SCFArtifactPaths(root=Path(root), dataset_id=dataset_id, state_id=state_id)


def stable_json_digest(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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


def build_atom_mol(
    state: AtomState,
    bundle: BasisBundle,
    *,
    verbose: int = 3,
    stdout: Any | None = None,
):
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
    if stdout is not None:
        mol.stdout = stdout
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
    mol, basis_use = build_atom_mol(
        state,
        bundle,
        verbose=run_settings.verbose,
        stdout=run_settings.stdout,
    )
    mf = make_spherical_uks(
        mol,
        xc=run_settings.xc,
        alpha_l_counts=state.alpha_l_counts,
        beta_l_counts=state.beta_l_counts,
    )
    if run_settings.stdout is not None:
        mf.stdout = run_settings.stdout
    if run_settings.chkfile is not None:
        mf.chkfile = str(run_settings.chkfile)
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


def _spin_pair(value: Any, *, label: str) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    if isinstance(value, list | tuple) and len(value) == 2:
        return np.asarray(value[0], dtype=float), np.asarray(value[1], dtype=float)
    arr = np.asarray(value, dtype=float)
    if arr.ndim >= 1 and arr.shape[0] == 2:
        return np.asarray(arr[0], dtype=float), np.asarray(arr[1], dtype=float)
    raise ValueError(f"Expected alpha/beta pair for {label}, got shape {arr.shape}")


def scf_arrays_from_mf(mf: Any) -> dict[str, NDArray[np.float64]]:
    """Extract project-native reusable SCF arrays from a completed UKS object."""

    dm_alpha, dm_beta = _spin_pair(mf.make_rdm1(), label="density matrix")
    mo_coeff_alpha, mo_coeff_beta = _spin_pair(mf.mo_coeff, label="mo_coeff")
    mo_occ_alpha, mo_occ_beta = _spin_pair(mf.mo_occ, label="mo_occ")
    mo_energy_alpha, mo_energy_beta = _spin_pair(mf.mo_energy, label="mo_energy")
    return {
        "dm_alpha": dm_alpha,
        "dm_beta": dm_beta,
        "mo_coeff_alpha": mo_coeff_alpha,
        "mo_coeff_beta": mo_coeff_beta,
        "mo_occ_alpha": mo_occ_alpha,
        "mo_occ_beta": mo_occ_beta,
        "mo_energy_alpha": mo_energy_alpha,
        "mo_energy_beta": mo_energy_beta,
    }


def write_scf_npz(path: Path, mf: Any) -> None:
    """Write the project-native reusable SCF array artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **scf_arrays_from_mf(mf))


def load_scf_npz(path: Path) -> dict[str, NDArray[np.float64]]:
    """Load a project-native SCF array artifact as plain numpy arrays."""

    required = {
        "dm_alpha",
        "dm_beta",
        "mo_coeff_alpha",
        "mo_coeff_beta",
        "mo_occ_alpha",
        "mo_occ_beta",
        "mo_energy_alpha",
        "mo_energy_beta",
    }
    with np.load(path) as data:
        arrays = {name: np.asarray(data[name], dtype=float) for name in data.files}
    missing = sorted(required - set(arrays))
    if missing:
        raise ValueError(f"SCF npz artifact {path} is missing arrays {missing}")
    if arrays["dm_alpha"].shape != arrays["dm_beta"].shape:
        raise ValueError(f"SCF npz artifact {path} has mismatched alpha/beta density shapes")
    return arrays


def load_mol_from_chk(chk_path: Path) -> Any:
    """Load a PySCF molecule from a saved checkpoint file."""

    try:
        from pyscf.scf import chkfile  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "PySCF is required to read SCF checkpoint files. Install with "
            "`python -m pip install -e .[generator]`."
        ) from exc
    return chkfile.load_mol(str(chk_path))


def scf_artifacts_complete(paths: SCFArtifactPaths) -> bool:
    """Return true when all required files for one SCF artifact are present and non-empty."""

    return all(
        path.exists() and path.is_file() and path.stat().st_size > 0
        for path in paths.required_files()
    )


def scf_state_record_digest(record: dict[str, Any]) -> str:
    """Return the active state-record fingerprint used for SCF artifact reuse."""

    return state_digest(record)


def scf_fingerprints(
    *,
    config_path: Path,
    config: ProfileDatasetConfig,
    state: AtomState,
    bundle: BasisBundle,
    settings: SCFSettings,
    pyscf_version: str | None = None,
) -> dict[str, str]:
    """Return fingerprints that define reusable local SCF artifacts.

    The profile-data release version and the full dataset YAML hash are deliberately
    excluded.  They describe publication scope/provenance, not the numerical SCF
    arrays stored in ``local-data/scf``.  This keeps expensive SCF artifacts reusable
    across release-version bumps and scope-only YAML edits.
    """

    _ = config_path
    defaults = getattr(config, "defaults", {})
    expected_engine_version = ""
    if isinstance(defaults, dict):
        expected_engine_version = str(defaults.get("expected_engine_version", ""))
    engine_version = str(pyscf_version if pyscf_version is not None else expected_engine_version)
    density_model = ""
    scf_type = ""
    if isinstance(defaults, dict):
        density_model = str(defaults.get("density_model", ""))
        scf_type = str(defaults.get("scf_type", ""))
    return {
        "basis_sha256": bundle.basis_sha256,
        "basis_manifest_sha256": sha256_file(bundle.path / "manifest.json"),
        "state_record_sha256": scf_state_record_digest(state.record),
        "scf_settings_sha256": stable_json_digest(settings.to_fingerprint_json()),
        "engine_version": engine_version,
        "density_model": density_model,
        "scf_type": scf_type,
    }


def scf_metadata(
    *,
    dataset_id: str,
    state: AtomState,
    bundle: BasisBundle,
    config: ProfileDatasetConfig,
    config_path: Path,
    settings: SCFSettings,
    pyscf_version: str,
    mf: Any,
    log_text: str,
) -> dict[str, Any]:
    """Build structured JSON metadata for one local SCF artifact."""

    fingerprints = scf_fingerprints(
        config_path=config_path,
        config=config,
        state=state,
        bundle=bundle,
        settings=settings,
        pyscf_version=pyscf_version,
    )
    return {
        "schema_version": SCF_ARTIFACT_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "state_id": state.state_id,
        "basis_id": bundle.basis_id,
        "density_model": config.defaults["density_model"],
        "method": {
            "engine": "pyscf",
            "engine_version": pyscf_version,
            "scf_type": config.defaults["scf_type"],
            "xc": settings.xc,
            "relativity": "sf-X2C-1e" if settings.use_x2c else "none",
            "spherical_basis": True,
        },
        "settings": settings.to_fingerprint_json(),
        "state": {
            "symbol": state.symbol,
            "z": state.z,
            "charge": state.charge,
            "electron_count": state.electron_count,
            "spin_2s": state.spin_2s,
            "multiplicity": state.multiplicity,
            "configuration": state.record["configuration"],
            "state_role": state.record["state_role"],
            "state_category": state.record["state_category"],
            "occupation_policy": state.record["occupation_policy"],
        },
        "basis": {
            "basis_id": bundle.basis_id,
            "basis_sha256": bundle.basis_sha256,
            "basis_manifest_sha256": fingerprints["basis_manifest_sha256"],
            "source_api_url": bundle.manifest["source"]["source_api_url"],
        },
        "results": {
            "converged": bool(mf.converged),
            "total_energy_hartree": None if mf.e_tot is None else float(mf.e_tot),
            "nelectron": int(mf.mol.nelectron),
            "n_ao": int(mf.mol.nao_nr()),
        },
        "fingerprints": fingerprints,
        "log": {
            "captured": True,
            "line_count": len(log_text.splitlines()),
        },
    }


def read_scf_metadata(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def scf_artifact_is_reusable(
    paths: SCFArtifactPaths, expected_fingerprints: dict[str, str]
) -> bool:
    """Return true if a local SCF artifact matches the current SCF-defining inputs.

    Dataset YAML hashes are intentionally not part of this reuse gate.  Scope-only
    changes such as dropping ion datasets should not invalidate neutral SCF arrays when
    the basis, state record, and numerical SCF settings are unchanged.
    """

    if not scf_artifacts_complete(paths):
        return False
    try:
        metadata = read_scf_metadata(paths.metadata)
    except Exception:
        return False
    if metadata.get("schema_version") != SCF_ARTIFACT_SCHEMA_VERSION:
        return False
    if (
        metadata.get("dataset_id") != paths.dataset_id
        or metadata.get("state_id") != paths.state_id
    ):
        return False
    results = metadata.get("results", {})
    if not isinstance(results, dict) or results.get("converged") is not True:
        return False
    actual = metadata.get("fingerprints")
    if not isinstance(actual, dict):
        return False
    return all(
        actual.get(key) == expected_fingerprints.get(key)
        for key in SCF_REUSE_FINGERPRINT_KEYS
    )
