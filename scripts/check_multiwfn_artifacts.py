#!/usr/bin/env python3
"""Check generated Multiwfn interoperability files against profiles and state metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.dataio.datasets import load_profile_dataset_config  # noqa: E402
from atomref_proatoms.dataio.paths import (  # noqa: E402
    PROFILE_DATASETS_FILE,
    PROFILES_ROOT,
    STATES_FILE,
    repo_relative_path,
)
from atomref_proatoms.exporters.multiwfn_artifacts import (  # noqa: E402
    MULTIWFN_ARTIFACT_MANIFEST_SCHEMA_VERSION,
    read_multiwfn_manifest,
)
from atomref_proatoms.exporters.multiwfn_rad import (  # noqa: E402
    interpolate_density_to_rad_grid,
    profile_state_density_from_wide_rows,
    read_multiwfn_rad_file,
    read_wide_profiles_csv,
)
from atomref_proatoms.states.state_tables import load_atom_states  # noqa: E402
from atomref_proatoms.validation.wfn_density import parse_wfn_file  # noqa: E402

DEFAULT_ARTIFACT_ROOT = ROOT / "local-data" / "multiwfn_artifacts"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROFILE_DATASETS_FILE,
        help="Active dataset YAML; defaults to data/profile_datasets.yaml.",
    )
    parser.add_argument(
        "--states-file",
        type=Path,
        default=STATES_FILE,
        help="Active curated state JSON; defaults to data/states/curated/atom_states_v2.json.",
    )
    parser.add_argument(
        "--profiles-root",
        type=Path,
        default=PROFILES_ROOT,
        help="Profile input root; defaults to data/profiles.",
    )
    parser.add_argument(
        "--artifact-root",
        "--multiwfn-root",
        dest="artifact_root",
        type=Path,
        default=DEFAULT_ARTIFACT_ROOT,
        help="Generated Multiwfn artifact root; defaults to local-data/multiwfn_artifacts.",
    )
    parser.add_argument(
        "--require-generated",
        action="store_true",
        help="Fail if the Multiwfn artifact manifest is absent.",
    )
    parser.add_argument(
        "--rad-relative-tol",
        type=float,
        default=1e-9,
        help="Relative tolerance for comparing .rad values with profile interpolation.",
    )
    return parser.parse_args(argv)


def _resolve_manifest_path(path_text: str, artifact_root: Path) -> Path:
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate
    root_candidate = ROOT / candidate
    if root_candidate.exists():
        return root_candidate
    return artifact_root / candidate


def _check_rad_file(
    file_record: dict[str, Any],
    *,
    profiles_root: Path,
    artifact_root: Path,
    rows_cache: dict[str, list[dict[str, str]]],
    relative_tol: float,
) -> None:
    path = _resolve_manifest_path(str(file_record["path"]), artifact_root)
    parsed = read_multiwfn_rad_file(path)
    dataset_id = str(file_record["dataset_id"])
    state_id = str(file_record["state_id"])
    if dataset_id not in rows_cache:
        rows_cache[dataset_id] = read_wide_profiles_csv(profiles_root / dataset_id / "profiles.csv")
    source_r, source_rho = profile_state_density_from_wide_rows(rows_cache[dataset_id], state_id)
    expected = interpolate_density_to_rad_grid(source_r, source_rho, target_r_bohr=parsed.r_bohr)
    abs_error = np.abs(parsed.rho_e_bohr3 - expected)
    scale = max(float(np.max(np.abs(expected))), 1.0)
    if float(np.max(abs_error)) > relative_tol * scale + 1e-14:
        raise ValueError(
            f"{path}: .rad values differ from profile interpolation; "
            f"max_abs={float(np.max(abs_error)):.6g}, scale={scale:.6g}"
        )


def _check_wfn_file(
    file_record: dict[str, Any], *, artifact_root: Path, electron_counts: dict[str, int]
) -> None:
    path = _resolve_manifest_path(str(file_record["path"]), artifact_root)
    parsed = parse_wfn_file(path)
    state_id = str(file_record["state_id"])
    expected = float(electron_counts[state_id])
    if abs(parsed.n_electrons - expected) > 1e-5:
        raise ValueError(f"{path}: WFN electron count {parsed.n_electrons} != {expected}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _ = load_profile_dataset_config(args.config)
    manifest_path = args.artifact_root / "manifest.json"
    if not manifest_path.exists():
        if args.require_generated:
            print(f"ERROR: Multiwfn artifact manifest not found: {manifest_path}", file=sys.stderr)
            return 1
        print("OK: no generated Multiwfn artifact manifest found")
        print(f"artifact_root: {repo_relative_path(args.artifact_root)}")
        return 0

    manifest = read_multiwfn_manifest(manifest_path)
    if manifest.get("schema_version") != MULTIWFN_ARTIFACT_MANIFEST_SCHEMA_VERSION:
        print(
            "ERROR: unexpected Multiwfn artifact manifest schema_version "
            f"{manifest.get('schema_version')!r}",
            file=sys.stderr,
        )
        return 1
    states = load_atom_states(args.states_file)
    electron_counts = {state.state_id: state.electron_count for state in states}
    rows_cache: dict[str, list[dict[str, str]]] = {}
    files = manifest.get("files")
    if not isinstance(files, list):
        print("ERROR: manifest files field must be a list", file=sys.stderr)
        return 1
    try:
        for record in files:
            if not isinstance(record, dict):
                raise ValueError(f"manifest file record must be an object, got {record!r}")
            fmt = record.get("format")
            if fmt == "rad":
                _check_rad_file(
                    record,
                    profiles_root=args.profiles_root,
                    artifact_root=args.artifact_root,
                    rows_cache=rows_cache,
                    relative_tol=args.rad_relative_tol,
                )
            elif fmt == "wfn":
                _check_wfn_file(
                    record,
                    artifact_root=args.artifact_root,
                    electron_counts=electron_counts,
                )
            else:
                raise ValueError(f"unsupported Multiwfn artifact format in manifest: {fmt!r}")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    rad_count = sum(
        1 for record in files if isinstance(record, dict) and record.get("format") == "rad"
    )
    wfn_count = sum(
        1 for record in files if isinstance(record, dict) and record.get("format") == "wfn"
    )
    print(f"OK: checked {len(files)} Multiwfn interoperability files")
    print(f".rad files: {rad_count}")
    print(f".wfn files: {wfn_count}")
    print(f"manifest: {repo_relative_path(manifest_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
