"""Central path helpers for the source-tree workflow."""

from __future__ import annotations

import os
from pathlib import Path

_ENV_ROOT = "ATOMREF_PROATOMS_ROOT"


def repo_root() -> Path:
    """Return the repository root used by scripts and tests."""

    override = os.environ.get(_ENV_ROOT)
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


ROOT = repo_root()
DATA_DIR = ROOT / "data"
LOCAL_DATA_DIR = ROOT / "local-data"
REPORT_DIR = ROOT / "report"
PROFILE_DATASETS_FILE = DATA_DIR / "profile_datasets.yaml"
STATES_FILE = DATA_DIR / "states" / "curated" / "atom_states_v0.json"
BASIS_ROOT = DATA_DIR / "basis_sets"
PROFILES_ROOT = DATA_DIR / "profiles"
SCF_ROOT = LOCAL_DATA_DIR / "scf"
DIAGNOSTICS_ROOT = LOCAL_DATA_DIR / "diagnostics"
SCRATCH_ROOT = LOCAL_DATA_DIR / "scratch"


def data_dir() -> Path:
    return DATA_DIR


def local_data_dir() -> Path:
    return LOCAL_DATA_DIR


def report_dir() -> Path:
    return REPORT_DIR


def profile_datasets_file() -> Path:
    return PROFILE_DATASETS_FILE


def states_file() -> Path:
    return STATES_FILE


def basis_root() -> Path:
    return BASIS_ROOT


def profile_root() -> Path:
    return PROFILES_ROOT


def local_scf_root() -> Path:
    return SCF_ROOT
