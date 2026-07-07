#!/usr/bin/env python3
"""Export configured Multiwfn .rad/.wfn interoperability files."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.dataio.datasets import load_profile_dataset_config  # noqa: E402
from atomref_proatoms.dataio.paths import (  # noqa: E402
    PROFILE_DATASETS_FILE,
    PROFILES_ROOT,
    SCF_ROOT,
    STATES_FILE,
    repo_relative_path,
)
from atomref_proatoms.engines.pyscf_backend import (  # noqa: E402
    load_mol_from_chk,
    load_scf_npz,
    read_scf_metadata,
    scf_artifact_paths,
)
from atomref_proatoms.exporters.multiwfn_artifacts import (  # noqa: E402
    ALL_MULTIWFN_ARTIFACT_DATASETS,
    MultiwfnArtifactJob,
    build_multiwfn_artifact_jobs,
    filter_multiwfn_artifact_jobs,
    format_multiwfn_artifact_plan,
    write_multiwfn_manifest,
)
from atomref_proatoms.exporters.multiwfn_rad import (  # noqa: E402
    profile_state_density_from_wide_rows,
    read_wide_profiles_csv,
    write_profile_state_rad,
)
from atomref_proatoms.exporters.proaim_wfn import write_atomref_scf_arrays_wfn  # noqa: E402
from atomref_proatoms.states.state_tables import AtomState, load_atom_states  # noqa: E402

DEFAULT_OUTPUT_ROOT = ROOT / "local-data" / "multiwfn_artifacts"


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
        "--dataset",
        "--dataset-id",
        dest="dataset_ids",
        action="append",
        default=[],
        help=(
            "Dataset ID to export; may be repeated. Use 'all' for all configured "
            "datasets. Defaults to all datasets with requested Multiwfn outputs."
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
        "--format",
        choices=("all", "rad", "wfn"),
        default="all",
        help="Export both configured formats, only .rad, or only .wfn.",
    )
    parser.add_argument(
        "--profiles-root",
        type=Path,
        default=PROFILES_ROOT,
        help="Profile input root; defaults to data/profiles.",
    )
    parser.add_argument(
        "--scf-root",
        type=Path,
        default=SCF_ROOT,
        help="Local SCF artifact root for .wfn export; defaults to local-data/scf.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Output root; defaults to local-data/multiwfn_artifacts.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="After writing, re-read .rad/.wfn files using package parsers where possible.",
    )
    parser.add_argument("--list", action="store_true", help="Print the export plan and exit.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the export plan and required inputs, then exit before writing files.",
    )
    parser.add_argument(
        "--show-jobs",
        action="store_true",
        help="With --list or --dry-run, print every selected export job.",
    )
    return parser.parse_args(argv)


def _selected_dataset_ids(values: list[str], configured_ids: tuple[str, ...]) -> tuple[str, ...]:
    if not values:
        return configured_ids
    aliases = {ALL_MULTIWFN_ARTIFACT_DATASETS, "all"}
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


def _state_map(states: list[AtomState]) -> dict[str, AtomState]:
    return {state.state_id: state for state in states}


def _print_plan(
    args: argparse.Namespace, jobs: tuple[MultiwfnArtifactJob, ...], config: Any
) -> None:
    print(f"Profile data version: {config.profile_data_version}")
    print(f"Dataset config: {repo_relative_path(args.config)}")
    print(f"Profile input root: {repo_relative_path(args.profiles_root)}")
    print(f"SCF artifact root: {repo_relative_path(args.scf_root)}")
    print(f"Output root: {repo_relative_path(args.output_root)}")
    print(format_multiwfn_artifact_plan(jobs, show_jobs=args.show_jobs or args.list, config=config))


def _ensure_writable(path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file without --force: {path}")


def _profile_rows_by_dataset(
    jobs: tuple[MultiwfnArtifactJob, ...], profiles_root: Path
) -> dict[str, list[dict[str, str]]]:
    rows_by_dataset: dict[str, list[dict[str, str]]] = {}
    for dataset_id in sorted({job.dataset_id for job in jobs if job.rad_requested}):
        profiles_path = profiles_root / dataset_id / "profiles.csv"
        if not profiles_path.exists():
            raise FileNotFoundError(
                f"Profile CSV required for .rad export not found: {profiles_path}"
            )
        rows_by_dataset[dataset_id] = read_wide_profiles_csv(profiles_path)
    return rows_by_dataset


def _export_rad_job(
    job: MultiwfnArtifactJob,
    *,
    rows_by_dataset: Mapping[str, list[dict[str, str]]],
    output_root: Path,
    force: bool,
    check: bool,
) -> dict[str, Any]:
    rows = rows_by_dataset[job.dataset_id]
    r_bohr, rho = profile_state_density_from_wide_rows(rows, job.state_id)
    out_path = output_root / "rad" / job.dataset_id / job.rad_filename
    _ensure_writable(out_path, force=force)
    info = write_profile_state_rad(
        out_path,
        profile_r_bohr=r_bohr,
        profile_rho_e_bohr3=rho,
    )
    if check:
        from atomref_proatoms.exporters.multiwfn_rad import read_multiwfn_rad_file

        parsed = read_multiwfn_rad_file(out_path)
        if parsed.n_points != info["n_points"]:
            raise ValueError(f".rad re-read point-count mismatch for {out_path}")
    return {
        "format": "rad",
        "dataset_id": job.dataset_id,
        "state_id": job.state_id,
        "symbol": job.symbol,
        "charge": job.charge,
        "path": repo_relative_path(out_path),
        **info,
    }


def _scf_total_energy(metadata: Mapping[str, Any]) -> float | None:
    results = metadata.get("results")
    if isinstance(results, Mapping) and results.get("total_energy_hartree") is not None:
        return float(results["total_energy_hartree"])
    return None


def _export_wfn_job(
    job: MultiwfnArtifactJob,
    *,
    states: Mapping[str, AtomState],
    scf_root: Path,
    output_root: Path,
    force: bool,
    check: bool,
) -> dict[str, Any]:
    paths = scf_artifact_paths(scf_root, job.dataset_id, job.state_id)
    missing = [path for path in (paths.chk, paths.npz, paths.metadata) if not path.exists()]
    if missing:
        missing_text = ", ".join(repo_relative_path(path) for path in missing)
        raise FileNotFoundError(
            f"SCF artifact files required for .wfn export are missing: {missing_text}"
        )
    out_path = output_root / "wfn" / job.dataset_id / job.wfn_filename
    _ensure_writable(out_path, force=force)
    state = states[job.state_id]
    mol = load_mol_from_chk(paths.chk)
    arrays = load_scf_npz(paths.npz)
    metadata = read_scf_metadata(paths.metadata)
    info = write_atomref_scf_arrays_wfn(
        out_path,
        state,
        mol,
        arrays,
        title=f"atomref-proatoms {job.state_id} {job.basis_id}",
        total_energy=_scf_total_energy(metadata),
    )
    if check:
        from atomref_proatoms.validation.wfn_density import parse_wfn_file

        parsed = parse_wfn_file(out_path)
        if abs(parsed.n_electrons - float(state.electron_count)) > 1e-5:
            raise ValueError(f"WFN electron-count mismatch for {out_path}")
    return {
        "format": "wfn",
        "dataset_id": job.dataset_id,
        "state_id": job.state_id,
        "symbol": job.symbol,
        "charge": job.charge,
        "path": repo_relative_path(out_path),
        **info,
    }


def _dry_run_inputs(jobs: tuple[MultiwfnArtifactJob, ...], args: argparse.Namespace) -> None:
    rad_datasets = sorted({job.dataset_id for job in jobs if job.rad_requested})
    wfn_jobs = [job for job in jobs if job.wfn_requested]
    if rad_datasets:
        print("Required profile CSVs for .rad export:")
        for dataset_id in rad_datasets:
            print(f"  {repo_relative_path(args.profiles_root / dataset_id / 'profiles.csv')}")
    if wfn_jobs:
        print("Required SCF artifact directories for .wfn export:")
        for job in wfn_jobs[:20]:
            print(f"  {repo_relative_path(args.scf_root / job.dataset_id / job.state_id)}")
        if len(wfn_jobs) > 20:
            print(f"  ... {len(wfn_jobs) - 20} more")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_profile_dataset_config(args.config)
    dataset_ids = _selected_dataset_ids(args.dataset_ids, config.dataset_ids)
    include_rad = args.format in {"all", "rad"}
    include_wfn = args.format in {"all", "wfn"}
    states = load_atom_states(args.states_file)
    jobs = build_multiwfn_artifact_jobs(
        states,
        dataset_ids=dataset_ids,
        config=config,
        include_rad=include_rad,
        include_wfn=include_wfn,
    )
    jobs = filter_multiwfn_artifact_jobs(
        jobs,
        only_state_ids=set(args.state_ids) if args.state_ids else None,
    )
    _print_plan(args, jobs, config)
    if args.list:
        print("Plan listing completed before Multiwfn artifact export")
        return 0
    if args.dry_run:
        _dry_run_inputs(jobs, args)
        print("Dry run completed before Multiwfn artifact export")
        return 0

    rows_by_dataset = _profile_rows_by_dataset(jobs, args.profiles_root)
    states_by_id = _state_map(states)
    files: list[dict[str, Any]] = []
    for job in jobs:
        if job.rad_requested:
            files.append(
                _export_rad_job(
                    job,
                    rows_by_dataset=rows_by_dataset,
                    output_root=args.output_root,
                    force=args.force,
                    check=args.check,
                )
            )
        if job.wfn_requested:
            files.append(
                _export_wfn_job(
                    job,
                    states=states_by_id,
                    scf_root=args.scf_root,
                    output_root=args.output_root,
                    force=args.force,
                    check=args.check,
                )
            )
    manifest = write_multiwfn_manifest(
        args.output_root / "manifest.json",
        output_root=args.output_root,
        profile_data_version=config.profile_data_version,
        config_path=args.config,
        jobs=jobs,
        files=files,
    )
    print(f"Wrote {len(files)} Multiwfn interoperability files")
    print(f"Manifest: {repo_relative_path(manifest)}")
    if args.check:
        print("Re-read checks completed")
    print(json.dumps({"formats": args.format, "files": len(files)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
