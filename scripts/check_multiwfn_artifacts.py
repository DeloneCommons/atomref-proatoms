#!/usr/bin/env python3
"""Check generated Multiwfn interoperability files and manifest consistency."""

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
    MULTIWFN_ARTIFACTS_ROOT,
    PROFILE_DATASETS_FILE,
    STATES_FILE,
    repo_relative_path,
)
from atomref_proatoms.exporters.multiwfn_artifacts import (  # noqa: E402
    MULTIWFN_ARTIFACT_MANIFEST_SCHEMA_VERSION,
    read_multiwfn_manifest,
)
from atomref_proatoms.exporters.multiwfn_rad import (  # noqa: E402
    MULTIWFN_ATMRAD_GRID_BOHR,
    radial_density_integral,
    read_multiwfn_rad_file,
)
from atomref_proatoms.states.state_tables import load_atom_states  # noqa: E402
from atomref_proatoms.validation.wfn_density import parse_wfn_file  # noqa: E402

DEFAULT_ARTIFACT_ROOT = MULTIWFN_ARTIFACTS_ROOT


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
        "--artifact-root",
        "--multiwfn-root",
        dest="artifact_root",
        type=Path,
        default=DEFAULT_ARTIFACT_ROOT,
        help="Generated Multiwfn artifact root; defaults to data/multiwfn_artifacts.",
    )
    parser.add_argument(
        "--require-generated",
        action="store_true",
        help="Fail if the Multiwfn artifact manifest is absent.",
    )
    return parser.parse_args(argv)




def _check_manifest_path_alias(file_record: dict[str, Any]) -> None:
    path_text = str(file_record.get("path", ""))
    if not path_text:
        raise ValueError("manifest file record is missing path")
    file_text = file_record.get("file")
    if file_text is not None and str(file_text) != path_text:
        raise ValueError(
            "manifest file field must match the canonical path field; "
            f"got file={file_text!r}, path={path_text!r}"
        )

def _resolve_manifest_path(path_text: str, artifact_root: Path) -> Path:
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate
    root_candidate = ROOT / candidate
    if root_candidate.exists():
        return root_candidate
    return artifact_root / candidate


def _require_close(observed: float, expected: float, *, label: str, path: Path) -> None:
    if not np.isclose(observed, expected, rtol=1e-10, atol=1e-12):
        raise ValueError(f"{path}: {label} {observed:.12g} != manifest {expected:.12g}")


def _check_rad_file(file_record: dict[str, Any], *, artifact_root: Path) -> None:
    if file_record.get("source") != "scf_density_evaluation":
        raise ValueError(
            "manifest .rad records must be generated from local SCF artifacts; "
            f"got source={file_record.get('source')!r}"
        )
    required_source_fields = (
        "source_scf_checkpoint",
        "source_scf_npz",
        "source_scf_metadata",
        "rad_evaluation",
        "rad_angular_points",
    )
    missing_source_fields = [field for field in required_source_fields if field not in file_record]
    if missing_source_fields:
        raise ValueError(f"manifest .rad record missing fields {missing_source_fields}")
    if file_record.get("rad_evaluation") not in {
        "fixed_axis_spherical_scf",
        "angular_average_scf",
    }:
        raise ValueError(
            "manifest .rad record has unsupported rad_evaluation "
            f"{file_record.get('rad_evaluation')!r}"
        )
    if int(file_record.get("rad_angular_points", 0)) < 1:
        raise ValueError("manifest .rad record has invalid rad_angular_points")
    path = _resolve_manifest_path(str(file_record["path"]), artifact_root)
    parsed = read_multiwfn_rad_file(path)
    if parsed.n_points != len(MULTIWFN_ATMRAD_GRID_BOHR):
        raise ValueError(f"{path}: unexpected .rad point count {parsed.n_points}")
    if not np.allclose(parsed.r_bohr, MULTIWFN_ATMRAD_GRID_BOHR, rtol=0.0, atol=5e-13):
        raise ValueError(f"{path}: radius grid does not match the fixed Multiwfn atmrad grid")
    if "n_points" in file_record and parsed.n_points != int(file_record["n_points"]):
        raise ValueError(f"{path}: point count does not match manifest")
    if "r_min_bohr" in file_record:
        _require_close(
            float(parsed.r_bohr[0]),
            float(file_record["r_min_bohr"]),
            label="r_min",
            path=path,
        )
    if "r_max_bohr" in file_record:
        _require_close(
            float(parsed.r_bohr[-1]),
            float(file_record["r_max_bohr"]),
            label="r_max",
            path=path,
        )
    if "integral_electrons_trapezoid" in file_record:
        observed = radial_density_integral(parsed.r_bohr, parsed.rho_e_bohr3)
        _require_close(
            observed,
            float(file_record["integral_electrons_trapezoid"]),
            label="finite-grid electron integral",
            path=path,
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
    files = manifest.get("files")
    if not isinstance(files, list):
        print("ERROR: manifest files field must be a list", file=sys.stderr)
        return 1
    try:
        for record in files:
            if not isinstance(record, dict):
                raise ValueError(f"manifest file record must be an object, got {record!r}")
            _check_manifest_path_alias(record)
            fmt = record.get("format")
            if fmt == "rad":
                _check_rad_file(record, artifact_root=args.artifact_root)
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
