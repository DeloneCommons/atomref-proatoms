#!/usr/bin/env python3
"""Extract released wide radial-profile datasets from saved local SCF artifacts."""

from __future__ import annotations

import argparse
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

from atomref_proatoms.profiles.artifacts import (  # noqa: E402
    profile_density_column,
    qa_overall_pass,
    write_profile_dataset_artifacts,
    write_qa_dataset_artifacts,
    write_qa_overview,
    write_radii_dataset_artifacts,
)
from atomref_proatoms.dataio.basis import list_basis_bundles, sha256_file  # noqa: E402
from atomref_proatoms.profiles.build_plan import (  # noqa: E402
    ALL_PROFILE_DATASETS,
    build_jobs_for_datasets,
    filter_build_jobs,
    format_build_plan,
)
from atomref_proatoms.dataio.datasets import DATASET_IDS, load_profile_dataset_config  # noqa: E402
from atomref_proatoms.profiles.grids import log_radial_grid  # noqa: E402
from atomref_proatoms.dataio.paths import (  # noqa: E402
    BASIS_ROOT,
    PROFILE_DATASETS_FILE,
    STATES_FILE,
    local_scf_root,
    profile_root,
    qa_root,
    radii_root,
    repo_relative_path,
)
from atomref_proatoms.profiles.radial import density_profile_from_mf, derived_radii  # noqa: E402
from atomref_proatoms.profiles.qa import (  # noqa: E402
    electron_count_tolerance,
    linear_dependency_diagnostics_from_log,
    qa_result_from_profile,
)
from atomref_proatoms.engines.pyscf_backend import (  # noqa: E402
    SCF_REUSE_FINGERPRINT_KEYS,
    SCFSettings,
    load_mol_from_chk,
    load_scf_npz,
    read_scf_metadata,
    scf_artifact_paths,
    scf_artifacts_complete,
    scf_state_record_digest,
    stable_json_digest,
)
from atomref_proatoms.states.state_tables import AtomState, load_atom_states  # noqa: E402

PROFILE_DATASET_SCHEMA_VERSION = "atomref.proatoms.profile_dataset.v1"
ANGULAR_SIGMA_REL_TOL = 1.0e-8


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
            "Dataset ID to extract; may be repeated. Use 'all' for all "
            "configured datasets. Defaults to all datasets."
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
    parser.add_argument(
        "--radii-root",
        type=Path,
        default=radii_root(),
        help="Released cutoff-radii output root; defaults to data/radii.",
    )
    parser.add_argument(
        "--qa-root",
        type=Path,
        default=qa_root(),
        help="Released QA output root; defaults to data/qa.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing dataset outputs.")
    parser.add_argument(
        "--list", action="store_true", help="Print the selected extraction plan and exit."
    )
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
    aliases = {"all", ALL_PROFILE_DATASETS}
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


def _print_plan(args: argparse.Namespace, jobs: tuple[Any, ...], config: Any) -> None:
    print(f"Profile data version: {config.profile_data_version}")
    print(f"Dataset config: {repo_relative_path(args.config)}")
    print(f"SCF artifact root: {repo_relative_path(args.scf_root)}")
    print(f"Profile output root: {repo_relative_path(args.output_root)}")
    print(format_build_plan(jobs, show_jobs=args.list or args.dry_run, config=config))


def _check_fingerprint(
    metadata: Mapping[str, Any], *, key: str, expected: str, label: str
) -> None:
    fingerprints = metadata.get("fingerprints", {})
    actual = fingerprints.get(key) if isinstance(fingerprints, Mapping) else None
    if actual != expected:
        raise ValueError(
            f"{label} fingerprint mismatch for {key}: expected {expected}, got {actual}"
        )


def _expected_scf_settings_digest(config: Any) -> str:
    defaults = config.defaults
    relativity = str(defaults.get("relativity", "sf-X2C-1e"))
    settings = SCFSettings(
        xc=str(defaults.get("xc", "PBE0")),
        use_x2c=relativity != "none",
        conv_tol=float(defaults.get("conv_tol", 1e-9)),
        max_cycle=int(defaults.get("max_cycle", 100)),
        grid_level=int(defaults.get("grid_level", 4)),
    )
    return stable_json_digest(settings.to_fingerprint_json())


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
    basis = metadata.get("basis", {})
    if not isinstance(basis, Mapping) or basis.get("basis_sha256") != basis_sha256:
        raise ValueError("SCF metadata basis SHA does not match the current basis bundle")
    _check_fingerprint(
        metadata,
        key="basis_sha256",
        expected=basis_sha256,
        label=state.state_id,
    )
    _check_fingerprint(
        metadata,
        key="state_record_sha256",
        expected=scf_state_record_digest(state.record),
        label=state.state_id,
    )
    _check_fingerprint(
        metadata,
        key="scf_settings_sha256",
        expected=_expected_scf_settings_digest(config),
        label=state.state_id,
    )


def _method_signature(
    metadata: Mapping[str, Any], *, basis_id: str, basis_sha256: str
) -> dict[str, Any]:
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
    scf_artifacts: Mapping[str, Mapping[str, Any]],
    related_artifacts: Mapping[str, str],
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
        "related_artifacts": dict(related_artifacts),
        "scf_artifacts": dict(scf_artifacts),
        "provenance": {
            "profile_datasets_yaml_sha256": config_sha256,
            "scf_source": "local-data/scf/<dataset_id>/<state_id>",
        },
    }


def _scf_artifact_summary(paths: Any, metadata: Mapping[str, Any]) -> dict[str, Any]:
    results = metadata.get("results", {})
    fingerprints = metadata.get("fingerprints", {})
    reusable_fingerprints = (
        {key: fingerprints[key] for key in SCF_REUSE_FINGERPRINT_KEYS if key in fingerprints}
        if isinstance(fingerprints, Mapping)
        else {}
    )
    return {
        "schema_version": metadata.get("schema_version"),
        "scf_chk": repo_relative_path(paths.chk),
        "scf_npz": repo_relative_path(paths.npz),
        "scf_json": repo_relative_path(paths.metadata),
        "scf_log": repo_relative_path(paths.log),
        "results": dict(results) if isinstance(results, Mapping) else {},
        "fingerprints": reusable_fingerprints,
    }



def _dataset_qa_summary(
    dataset_id: str, *, basis_id: str, qa_rows: list[Mapping[str, Any]]
) -> dict[str, Any]:
    electron_errors = [
        abs(float(row["electron_count_error_qa"]))
        for row in qa_rows
        if row.get("electron_count_error_qa") is not None
    ]
    angular_sigmas = [
        abs(float(row["max_rel_angular_sigma"]))
        for row in qa_rows
        if row.get("max_rel_angular_sigma") is not None
    ]
    return {
        "dataset_id": dataset_id,
        "basis_id": basis_id,
        "state_count": len(qa_rows),
        "passed_count": sum(1 for row in qa_rows if qa_overall_pass(row)),
        "failed_count": sum(1 for row in qa_rows if not qa_overall_pass(row)),
        "max_abs_electron_count_error_qa": max(electron_errors) if electron_errors else None,
        "max_rel_angular_sigma": max(angular_sigmas) if angular_sigmas else None,
        "linear_dependency_warning_count": sum(
            int(row.get("linear_dependency_warning_count") or 0) for row in qa_rows
        ),
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
) -> dict[str, Any]:
    output_dir = args.output_root / dataset_id
    radii_dir = args.radii_root / dataset_id
    qa_dir = args.qa_root / dataset_id
    profiles_csv = output_dir / "profiles.csv"
    metadata_json = output_dir / "metadata.json"
    radii_csv = radii_dir / "radii.csv"
    radii_metadata_json = radii_dir / "metadata.json"
    qa_csv = qa_dir / "qa.csv"
    qa_metadata_json = qa_dir / "metadata.json"
    outputs_to_guard = (
        profiles_csv,
        metadata_json,
        radii_csv,
        radii_metadata_json,
        qa_csv,
        qa_metadata_json,
    )
    if any(path.exists() for path in outputs_to_guard) and not args.force:
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
        qa_result["max_rel_angular_sigma_tolerance"] = ANGULAR_SIGMA_REL_TOL
        qa_result["angular_sigma_pass"] = (
            qa_result["max_rel_angular_sigma"] is None
            or abs(float(qa_result["max_rel_angular_sigma"])) <= ANGULAR_SIGMA_REL_TOL
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
    related_artifacts = {
        "profiles_csv": repo_relative_path(profiles_csv),
        "profile_metadata_json": repo_relative_path(metadata_json),
        "radii_csv": repo_relative_path(radii_csv),
        "radii_metadata_json": repo_relative_path(radii_metadata_json),
        "qa_csv": repo_relative_path(qa_csv),
        "qa_metadata_json": repo_relative_path(qa_metadata_json),
    }
    metadata = _profile_dataset_metadata(
        dataset_id=dataset_id,
        basis_id=basis_id,
        basis_sha256=basis_sha256,
        config=config,
        config_sha256=config_sha256,
        method=method,
        columns=columns,
        states=states_metadata,
        scf_artifacts=scf_artifacts,
        related_artifacts=related_artifacts,
    )
    profiles_csv, metadata_json = write_profile_dataset_artifacts(
        output_dir,
        r_bohr=r_grid,
        densities_by_state_id=densities,
        metadata=metadata,
    )
    provenance = {
        "profile_datasets_yaml_sha256": config_sha256,
    }
    radii_csv, radii_metadata_json = write_radii_dataset_artifacts(
        radii_dir,
        dataset_id=dataset_id,
        profile_data_version=config.profile_data_version,
        basis_id=basis_id,
        cutoffs_e_bohr3=config.cutoffs_e_bohr3,
        states=states_metadata,
        derived_radii_by_state_id=derived_by_state,
        source_profiles_csv=repo_relative_path(profiles_csv),
        source_metadata_json=repo_relative_path(metadata_json),
        provenance=provenance,
    )
    qa_csv, qa_metadata_json = write_qa_dataset_artifacts(
        qa_dir,
        dataset_id=dataset_id,
        profile_data_version=config.profile_data_version,
        basis_id=basis_id,
        states=states_metadata,
        qa_by_state_id=qa_by_state,
        source_profiles_csv=repo_relative_path(profiles_csv),
        source_metadata_json=repo_relative_path(metadata_json),
        provenance=provenance,
    )
    qa_rows = []
    for state_id, state_meta in states_metadata.items():
        row = dict(state_meta)
        row.update(qa_by_state[state_id])
        row["overall_pass"] = qa_overall_pass(row)
        qa_rows.append(row)
    qa_summary = _dataset_qa_summary(dataset_id, basis_id=basis_id, qa_rows=qa_rows)
    return {
        "profiles_csv": profiles_csv,
        "profile_metadata_json": metadata_json,
        "radii_csv": radii_csv,
        "radii_metadata_json": radii_metadata_json,
        "qa_csv": qa_csv,
        "qa_metadata_json": qa_metadata_json,
        "qa_summary": qa_summary,
    }


def _check_output(
    dataset_dir: Path,
    *,
    expected_state_ids: list[str],
    radii_dir: Path | None = None,
    qa_dir: Path | None = None,
) -> list[str]:
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
    for label, sibling_dir, expected_file in (
        ("radii", radii_dir, "radii.csv"),
        ("qa", qa_dir, "qa.csv"),
    ):
        if sibling_dir is None:
            continue
        table = sibling_dir / expected_file
        meta = sibling_dir / "metadata.json"
        if not table.exists():
            errors.append(f"missing {label} table {table}")
        if not meta.exists():
            errors.append(f"missing {label} metadata {meta}")
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
                print(f"Output dataset: {repo_relative_path(args.output_root / dataset_id)}")
                for job in dataset_jobs:
                    paths = scf_artifact_paths(args.scf_root, job.dataset_id, job.state_id)
                    print(f"  requires {repo_relative_path(paths.state_dir)}")
            print("Dry run completed before PySCF import/checkpoint reading.")
        return 0

    state_by_id = {state.state_id: state for state in states}
    bundle_by_id = {bundle.basis_id: bundle for bundle in list_basis_bundles(BASIS_ROOT)}
    failures = 0
    qa_summaries: list[Mapping[str, Any]] = []
    for dataset_id, dataset_jobs in jobs_by_dataset.items():
        print(f"Extracting {dataset_id} ({len(dataset_jobs)} states)")
        try:
            outputs = _extract_dataset(
                dataset_id=dataset_id,
                jobs=dataset_jobs,
                state_by_id=state_by_id,
                bundle_by_id=bundle_by_id,
                config=config,
                config_sha256=config_sha256,
                args=args,
            )
            qa_summaries.append(outputs["qa_summary"])
            print(
                f"{dataset_id}: wrote {outputs['profiles_csv']}, "
                f"{outputs['radii_csv']}, and {outputs['qa_csv']}"
            )
            if args.check:
                errors = _check_output(
                    outputs["profiles_csv"].parent,
                    expected_state_ids=[job.state_id for job in dataset_jobs],
                    radii_dir=outputs["radii_csv"].parent,
                    qa_dir=outputs["qa_csv"].parent,
                )
                if errors:
                    raise ValueError("; ".join(errors))
                print(f"{dataset_id}: profile/radii/QA output check OK")
        except Exception as exc:
            failures += 1
            print(f"ERROR: {dataset_id}: {exc}", file=sys.stderr)
            if not args.continue_on_error:
                return 1
    if qa_summaries:
        overview = write_qa_overview(
            args.qa_root,
            profile_data_version=config.profile_data_version,
            dataset_summaries=qa_summaries,
        )
        print(
            "QA overview: wrote "
            f"{repo_relative_path(overview['qa_summary'])} and "
            f"{repo_relative_path(overview['qa_report'])}"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
