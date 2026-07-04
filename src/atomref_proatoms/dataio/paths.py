"""Central path helpers for the source-tree workflow."""

from __future__ import annotations

import os
from pathlib import Path

_ENV_ROOT = "ATOMREF_PROATOMS_ROOT"


def repo_root() -> Path:
    """Return the repository root used by scripts and tests.

    The path module lives under ``atomref_proatoms.dataio`` in the v2 package
    layout, but this helper should stay robust if it is moved again during
    packaging work.  Prefer an explicit environment override, then search
    upward for the source-tree markers used by this repository.
    """

    override = os.environ.get(_ENV_ROOT)
    if override:
        return Path(override).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "data").is_dir():
            return parent
    return here.parents[3]


ROOT = repo_root()
DATA_DIR = ROOT / "data"
LOCAL_DATA_DIR = ROOT / "local-data"
PROFILE_DATASETS_FILE = DATA_DIR / "profile_datasets.yaml"
STATES_FILE = DATA_DIR / "states" / "curated" / "atom_states_v2.json"
BASIS_ROOT = DATA_DIR / "basis_sets"
PROFILES_ROOT = DATA_DIR / "profiles"
RADII_ROOT = DATA_DIR / "radii"
QA_ROOT = DATA_DIR / "qa"
SCF_ROOT = LOCAL_DATA_DIR / "scf"
DIAGNOSTICS_ROOT = LOCAL_DATA_DIR / "diagnostics"
SCRATCH_ROOT = LOCAL_DATA_DIR / "scratch"


def repo_relative_path(path: Path | str) -> str:
    """Return a stable POSIX path relative to the repo root when possible."""

    candidate = Path(path)
    try:
        resolved = candidate.expanduser().resolve(strict=False)
        rel = resolved.relative_to(ROOT.resolve(strict=False))
    except Exception:
        return candidate.as_posix()
    return rel.as_posix()


def data_dir() -> Path:
    return DATA_DIR


def local_data_dir() -> Path:
    return LOCAL_DATA_DIR


def profile_datasets_file() -> Path:
    return PROFILE_DATASETS_FILE


def states_file() -> Path:
    """Return the active v2 curated state table."""

    return STATES_FILE


def basis_root() -> Path:
    return BASIS_ROOT


def profile_root() -> Path:
    return PROFILES_ROOT


def radii_root() -> Path:
    return RADII_ROOT


def qa_root() -> Path:
    return QA_ROOT


def local_scf_root() -> Path:
    return SCF_ROOT
