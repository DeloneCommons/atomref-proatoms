#!/usr/bin/env python3
"""Extract released wide radial-profile datasets from saved local SCF artifacts."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.artifacts import (  # noqa: E402
    profile_density_column,
    write_profile_dataset_artifacts,
)
from atomref_proatoms.basis import list_basis_bundles, sha256_file  # noqa: E402
from atomref_proatoms.build_plan import (  # noqa: E402
    ALL_PROFILE_DATASETS,
    ALL_V1_BUILD_PLAN,
    build_jobs_for_datasets,
    filter_build_jobs,
    format_build_plan,
)
from atomref_proatoms.datasets import DATASET_IDS, load_profile_dataset_config  # noqa: E402
from atomref_proatoms.grids import log_radial_grid  # noqa: E402
from atomref_proatoms.paths import (  # noqa: E402
    BASIS_ROOT,
    PROFILE_DATASETS_FILE,
    STATES_FILE,
    local_scf_root,
    profile_root,
)
from atomref_proatoms.profiles import density_profile_from_mf, derived_radii  # noqa: E402
from atomref_proatoms.qa import (  # noqa: E402
    electron_count_tolerance,
    linear_dependency_diagnostics_from_log,
    qa_result_from_profile,
)
from atomref_proatoms.scf import (  # noqa: E402
    load_mol_from_chk,
    load_scf_npz,
    read_scf_metadata,
    scf_artifact_paths,
    scf_artifacts_complete,
)
from atomref_proatoms.states import AtomState, load_atom_states, state_digest  # noqa: E402


PROFILE_DATASET_SCHEMA_VERSION = "atomref.proatoms.profile_dataset.v1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROFILE_DATASETS_FILE,
        help="Active dataset YAML; defaults to data/profile_datasets.yaml.",
    )
    parser.add_argument(
        "--dataset",
        "--dataset-id",
        dest="dataset_ids",
        action="append",
        default=[],
        help=(
            "Dataset ID to extract; may be repeated. Use 'all' or 'all_v1' for all "
            "configured v1 datasets. Defaults to all datasets."
        ),
    )
    parser.add_argument(
        "--state",
        "--state-id",
        dest="state_ids",
        action="append",
        default=[],
        help="Restrict selected datasets to one state_id; may be repeated.",
    )
    parser.add_argument(
        "--scf-root",
        type=Path,
        default=local_scf_root(),
        help="Local SCF artifact root; defaults to local-data/scf.",
    )
    parser.add_argument(
        "--output-root",
        "--profiles-root",
        dest="output_root",
        type=Path,
        default=profile_root(),
        help="Released profile output root; defaults to data/profiles.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing dataset outputs.")
    parser.add_argument("--list", action="store_true", help="Print the selected extraction plan and exit.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate/print required SCF artifacts and exit before importing PySCF.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check written/existing profile datasets after extraction.",
    )
    parser.add_argument(
        "--no-profile-qa",
        action="store_true",
        help="Skip independent electron-count QA during extraction.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue remaining datasets after one extraction failure.",
    )
    parser.add_argument(
        "--angular-points",
        type=int,
        default=None,
        help="Override angular grid size for stored-profile density evaluation.",
    )
    return parser.parse_args(argv)


def _selected_dataset_ids(values: list[str], configured_ids: tuple[str, ...]) -> tuple[str, ...]:
    if not values:
        return configured_ids
    aliases = {"all", ALL_PROFILE_DATASETS, ALL_V1_BUILD_PLAN}
    expanded: list[str] = []
    for value in values:
        if value in aliases:
            expanded.extend(configured_ids)
        elif value in configured_ids:
            expanded.append(value)
        else:
            choices = ", ".join((*configured_ids, *sorted(aliases)))
            raise SystemExit(f"Unknown dataset {value!r}; choices: {choices}")
    deduped: list[str] = []
    seen: set[str] = set()
    for dataset_id in expanded:
        if dataset_id in seen:
            continue
        seen.add(dataset_id)
        deduped.append(dataset_id)
    return tuple(deduped)


def _profile_grid_from_config(config: Any) -> np.ndarray:
    grid = config.profile_grid
    if grid.get("type") != "log":
        raise SystemExit(f"Unsupported profile grid type {grid.get('type')!r}")
    return log_radial_grid(
        float(grid["r_min_bohr"]),
        float(grid["r_max_bohr"]),
        int(grid["n"]),
    )


def _qa_grid_kwargs(config: Any) -> dict[str, Any]:
    grid = config.qa_grid
    if grid.get("type") != "gauss_legendre_log_r":
        raise SystemExit(f"Unsupported QA grid type {grid.get('type')!r}")
    return {
        "qa_r_min": float(grid["r_min_bohr"]),
        "qa_r_max": float(grid["r_max_bohr"]),
        "qa_n_r": int(grid["n"]),
        "qa_n_ang": int(grid.get("angular_points", 110)),
    }


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    commit = result.stdout.strip()
    return commit or None


def _print_plan(args: argparse.Namespace, jobs: tuple[Any, ...], config: Any) -> None:
    print(f"Profile data version: {config.profile_data_version}")
    print(f"Dataset config: {args.config}")
    print(f"SCF artifact root: {args.scf_root}")
    print(f"Profile output root: {args.output_root}")
    print(format_build_plan(jobs, show_jobs=args.list or args.dry_run, config=config))


def _check_fingerprint(
    metadata: Mapping[str, Any], *, key: str, expected: str, label: str
) -> None:
    fingerprints = metadata.get("fingerprints", {})
    actual = fingerprints.get(key) if isinstance(fingerprints, Mapping) else None
    if actual != expected:
        raise ValueError(f"{label} fingerprint mismatch for {key}: expected {expected}, got {actual}")


def _validate_scf_metadata(
    *,
    metadata: Mapping[str, Any],
    dataset_id: str,
    state: AtomState,
    basis_id: str,
    basis_sha256: str,
    config: Any,
    config_sha256: str,
) -> None:
    if metadata.get("dataset_id") != dataset_id:
        raise ValueError(f"SCF metadata dataset_id mismatch: {metadata.get('dataset_id')!r}")
    if metadata.get("state_id") != state.state_id:
        raise ValueError(f"SCF metadata state_id mismatch: {metadata.get('state_id')!r}")
    if metadata.get("basis_id") != basis_id:
        raise ValueError(f"SCF metadata basis_id mismatch: {metadata.get('basis_id')!r}")
    if metadata.get("profile_data_version") != config.profile_data_version:
        raise ValueError(
            "SCF metadata profile_data_version mismatch: "
            f"{metadata.get('profile_data_version')!r}"
        )
    basis = metadata.get("basis", {})
    if not isinstance(basis, Mapping) or basis.get("basis_sha256") != basis_sha256:
        raise ValueError("SCF metadata basis SHA does not match the current basis bundle")
    _check_fingerprint(
        metadata,
        key="profile_datasets_yaml_sha256",
        expected=config_sha256,
        label=state.state_id,
    )
    _check_fingerprint(
        metadata,
        key="basis_sha256",
        expected=basis_sha256,
        label=state.state_id,
    )
    _check_fingerprint(
        metadata,
        key="state_record_sha256",
        expected=state_digest(state.record),
        label=state.state_id,
    )


def _method_signature(metadata: Mapping[str, Any], *, basis_id: str, basis_sha256: str) -> dict[str, Any]:
    method = dict(metadata.get("method", {}))
    method["basis_id"] = basis_id
    method["basis_sha256"] = basis_sha256
    return method


def _state_metadata(state: AtomState, scf_metadata: Mapping[str, Any]) -> dict[str, Any]:
    scf_state = dict(scf_metadata.get("state", {}))
    return {
        "symbol": state.symbol,
        "z": state.z,
        "charge": state.charge,
        "electron_count": state.electron_count,
        "spin_2s": state.spin_2s,
        "multiplicity": state.multiplicity,
        "configuration": state.record["configuration"],
        "spin_model": state.record["spin_model"],
        "spin_variant": state.record["spin_variant"],
        "occupation_policy": state.record["occupation_policy"],
        "state_category": state.record["state_category"],
        "state_role": state.record["state_role"],
        "curation_status": state.record["curation_status"],
        "scf_state_metadata": scf_state,
    }


def _profile_dataset_metadata(
    *,
    dataset_id: str,
    basis_id: str,
    basis_sha256: str,
    config: Any,
    config_sha256: str,
    method: Mapping[str, Any],
    columns: Mapping[str, Mapping[str, Any]],
    states: Mapping[str, Mapping[str, Any]],
    derived: Mapping[str, Mapping[str, float]],
    qa: Mapping[str, Mapping[str, Any]],
    scf_artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": PROFILE_DATASET_SCHEMA_VERSION,
        "profile_data_version": config.profile_data_version,
        "dataset_id": dataset_id,
        "basis_id": basis_id,
        "basis_sha256": basis_sha256,
        "density_model": config.defaults["density_model"],
        "method": dict(method),
        "units": {"r": "bohr", "rho": "electron/bohr^3"},
        "profile_grid": dict(config.profile_grid),
        "qa_grid": dict(config.qa_grid),
        "cutoffs_e_bohr3": list(config.cutoffs_e_bohr3),
        "columns": dict(columns),
        "states": dict(states),
        "derived_radii": dict(derived),
        "qa": dict(qa),
        "scf_artifacts": dict(scf_artifacts),
        "provenance": {
            "profile_datasets_yaml_sha256": config_sha256,
            "generator_git_commit": _git_commit(),
            "scf_source": "local-data/scf/<dataset_id>/<state_id>",
        },
    }


def _scf_artifact_summary(paths: Any, metadata: Mapping[str, Any]) -> dict[str, Any]:
    results = metadata.get("results", {})
    fingerprints = metadata.get("fingerprints", {})
    return {
        "schema_version": metadata.get("schema_version"),
        "scf_chk": str(paths.chk),
        "scf_npz": str(paths.npz),
        "scf_json": str(paths.metadata),
        "scf_log": str(paths.log),
        "results": dict(results) if isinstance(results, Mapping) else {},
        "fingerprints": dict(fingerprints) if isinstance(fingerprints, Mapping) else {},
    }


def _extract_dataset(
    *,
    dataset_id: str,
    jobs: list[Any],
    state_by_id: Mapping[str, AtomState],
    bundle_by_id: Mapping[str, Any],
    config: Any,
    config_sha256: str,
    args: argparse.Namespace,
) -> tuple[Path, Path]:
    output_dir = args.output_root / dataset_id
    profiles_csv = output_dir / "profiles.csv"
    metadata_json = output_dir / "metadata.json"
    if (profiles_csv.exists() or metadata_json.exists()) and not args.force:
        raise FileExistsError(f"{dataset_id}: output exists; use --force to overwrite")

    r_grid = _profile_grid_from_config(config)
    qa_kwargs = _qa_grid_kwargs(config)
    profile_n_ang = int(args.angular_points or config.profile_grid.get("angular_points", 110))

    densities: dict[str, Any] = {}
    columns: dict[str, dict[str, Any]] = {}
    states_metadata: dict[str, dict[str, Any]] = {}
    derived_by_state: dict[str, dict[str, float]] = {}
    qa_by_state: dict[str, dict[str, Any]] = {}
    scf_artifacts: dict[str, dict[str, Any]] = {}
    method: dict[str, Any] | None = None

    basis_id = jobs[0].basis_id
    basis_sha256 = bundle_by_id[basis_id].basis_sha256

    for index, job in enumerate(jobs, start=1):
        state = state_by_id[job.state_id]
        paths = scf_artifact_paths(args.scf_root, job.dataset_id, job.state_id)
        print(f"  [{index}/{len(jobs)}] {job.state_id}")
        if not scf_artifacts_complete(paths):
            raise FileNotFoundError(f"Missing complete SCF artifacts: {paths.state_dir}")

        scf_metadata = read_scf_metadata(paths.metadata)
        _validate_scf_metadata(
            metadata=scf_metadata,
            dataset_id=job.dataset_id,
            state=state,
            basis_id=basis_id,
            basis_sha256=basis_sha256,
            config=config,
            config_sha256=config_sha256,
        )
        job_method = _method_signature(scf_metadata, basis_id=basis_id, basis_sha256=basis_sha256)
        if method is None:
            method = job_method
        elif job_method != method:
            raise ValueError(f"Dataset {dataset_id} mixes SCF method/settings metadata")

        arrays = load_scf_npz(paths.npz)
        dm_total = np.asarray(arrays["dm_alpha"], dtype=float) + np.asarray(
            arrays["dm_beta"], dtype=float
        )
        mol = load_mol_from_chk(paths.chk)
        mf_proxy = SimpleNamespace(mol=mol)
        profile = density_profile_from_mf(
            mf_proxy,
            r_grid=r_grid,
            n_ang=profile_n_ang,
            dm_total=dm_total,
            compute_qa=not args.no_profile_qa,
            **qa_kwargs,
        )
        state_derived = derived_radii(
            profile["r_bohr"], profile["rho_e_bohr3"], config.cutoffs_e_bohr3
        )
        linear_dependency = linear_dependency_diagnostics_from_log(
            paths.log.read_text(encoding="utf-8")
        )
        qa_result = qa_result_from_profile(
            scf_converged=bool(scf_metadata.get("results", {}).get("converged")),
            electron_count_exact=state.electron_count,
            derived=state_derived,
            profile=profile,
            linear_dependency_vectors_removed=linear_dependency.vectors_removed,
        ).to_json()
        qa_result["linear_dependency_warning_count"] = linear_dependency.warning_count
        qa_result["electron_count_tolerance"] = electron_count_tolerance(state.electron_count)
        qa_result["electron_count_pass"] = (
            qa_result["electron_count_error_qa"] is None
            or abs(float(qa_result["electron_count_error_qa"]))
            <= float(qa_result["electron_count_tolerance"])
        )

        densities[state.state_id] = profile["rho_e_bohr3"]
        column_name = profile_density_column(state.state_id)
        columns[column_name] = {
            "state_id": state.state_id,
            "symbol": state.symbol,
            "z": state.z,
            "charge": state.charge,
            "electron_count": state.electron_count,
            "multiplicity": state.multiplicity,
        }
        states_metadata[state.state_id] = _state_metadata(state, scf_metadata)
        derived_by_state[state.state_id] = state_derived
        qa_by_state[state.state_id] = qa_result
        scf_artifacts[state.state_id] = _scf_artifact_summary(paths, scf_metadata)

    if method is None:
        raise ValueError(f"Dataset {dataset_id} has no jobs")
    metadata = _profile_dataset_metadata(
        dataset_id=dataset_id,
        basis_id=basis_id,
        basis_sha256=basis_sha256,
        config=config,
        config_sha256=config_sha256,
        method=method,
        columns=columns,
        states=states_metadata,
        derived=derived_by_state,
        qa=qa_by_state,
        scf_artifacts=scf_artifacts,
    )
    return write_profile_dataset_artifacts(
        output_dir,
        r_bohr=r_grid,
        densities_by_state_id=densities,
        metadata=metadata,
    )


def _check_output(dataset_dir: Path, *, expected_state_ids: list[str]) -> list[str]:
    errors: list[str] = []
    profiles_csv = dataset_dir / "profiles.csv"
    metadata_json = dataset_dir / "metadata.json"
    if not profiles_csv.exists():
        errors.append(f"missing {profiles_csv}")
    if not metadata_json.exists():
        errors.append(f"missing {metadata_json}")
    if errors:
        return errors
    import csv
    import json

    with profiles_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            return [f"empty {profiles_csv}"]
        row_count = sum(1 for _row in reader)
    if not header or header[0] != "r_bohr":
        errors.append(f"{profiles_csv}: first column must be r_bohr")
    expected_columns = [profile_density_column(state_id) for state_id in expected_state_ids]
    missing_columns = sorted(set(expected_columns) - set(header))
    if missing_columns:
        errors.append(f"{profiles_csv}: missing density columns {missing_columns}")
    if row_count < 2:
        errors.append(f"{profiles_csv}: expected at least two profile rows")
    metadata = json.loads(metadata_json.read_text(encoding="utf-8"))
    if metadata.get("schema_version") != PROFILE_DATASET_SCHEMA_VERSION:
        errors.append(f"{metadata_json}: unexpected schema_version")
    if set(metadata.get("states", {})) != set(expected_state_ids):
        errors.append(f"{metadata_json}: states do not match selected jobs")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_profile_dataset_config(args.config)
    config_sha256 = sha256_file(args.config)
    dataset_ids = _selected_dataset_ids(args.dataset_ids, config.dataset_ids or DATASET_IDS)
    states = load_atom_states(STATES_FILE)
    jobs = build_jobs_for_datasets(states, dataset_ids=dataset_ids, config=config)
    try:
        jobs = filter_build_jobs(jobs, only_state_ids=set(args.state_ids) or None)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not jobs:
        raise SystemExit("Selected profile extraction plan is empty")

    _print_plan(args, jobs, config)

    jobs_by_dataset: dict[str, list[Any]] = {}
    for job in jobs:
        jobs_by_dataset.setdefault(job.dataset_id, []).append(job)

    if args.dry_run or args.list:
        if args.dry_run:
            for dataset_id, dataset_jobs in jobs_by_dataset.items():
                print(f"Output dataset: {args.output_root / dataset_id}")
                for job in dataset_jobs:
                    paths = scf_artifact_paths(args.scf_root, job.dataset_id, job.state_id)
                    print(f"  requires {paths.state_dir}")
            print("Dry run completed before PySCF import/checkpoint reading.")
        return 0

    state_by_id = {state.state_id: state for state in states}
    bundle_by_id = {bundle.basis_id: bundle for bundle in list_basis_bundles(BASIS_ROOT)}
    failures = 0
    for dataset_id, dataset_jobs in jobs_by_dataset.items():
        print(f"Extracting {dataset_id} ({len(dataset_jobs)} states)")
        try:
            profiles_csv, metadata_json = _extract_dataset(
                dataset_id=dataset_id,
                jobs=dataset_jobs,
                state_by_id=state_by_id,
                bundle_by_id=bundle_by_id,
                config=config,
                config_sha256=config_sha256,
                args=args,
            )
            print(f"{dataset_id}: wrote {profiles_csv} and {metadata_json}")
            if args.check:
                errors = _check_output(
                    profiles_csv.parent,
                    expected_state_ids=[job.state_id for job in dataset_jobs],
                )
                if errors:
                    raise ValueError("; ".join(errors))
                print(f"{dataset_id}: profile output check OK")
        except Exception as exc:
            failures += 1
            print(f"ERROR: {dataset_id}: {exc}", file=sys.stderr)
            if not args.continue_on_error:
                return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
