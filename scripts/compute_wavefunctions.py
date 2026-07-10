#!/usr/bin/env python3
"""Compute persistent spherical-atom SCF artifacts for configured datasets."""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atomref_proatoms.dataio.basis import list_basis_bundles  # noqa: E402
from atomref_proatoms.dataio.datasets import DATASET_IDS, load_profile_dataset_config  # noqa: E402
from atomref_proatoms.dataio.paths import (  # noqa: E402
    BASIS_ROOT,
    PROFILE_DATASETS_FILE,
    SCF_ROOT,
    STATES_FILE,
    repo_relative_path,
)
from atomref_proatoms.engines.pyscf_backend import (  # noqa: E402
    SCFSettings,
    import_pyscf_modules,
    run_dataset_state,
    scf_artifact_is_reusable,
    scf_artifact_paths,
    scf_fingerprints,
    scf_metadata,
    write_scf_npz,
)
from atomref_proatoms.profiles.artifacts import write_json  # noqa: E402
from atomref_proatoms.profiles.build_plan import (  # noqa: E402
    ALL_PROFILE_DATASETS,
    ProfileBuildJob,
    build_jobs_for_datasets,
    filter_build_jobs,
    format_build_plan,
)
from atomref_proatoms.states.state_tables import AtomState, load_atom_states  # noqa: E402


class TeeCapture(io.StringIO):
    """Capture PySCF text while optionally echoing it to the terminal."""

    def __init__(self, stream: Any | None = None) -> None:
        super().__init__()
        self._stream = stream

    def write(self, text: str) -> int:
        if self._stream is not None:
            self._stream.write(text)
        return super().write(text)

    def flush(self) -> None:
        if self._stream is not None:
            self._stream.flush()
        super().flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROFILE_DATASETS_FILE,
        help="Profile dataset YAML; defaults to data/profile_datasets.yaml.",
    )
    parser.add_argument(
        "--dataset",
        "--dataset-id",
        dest="dataset_ids",
        action="append",
        default=[],
        help=(
            "Dataset ID to compute; may be repeated. Use 'all' for all "
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
        default=SCF_ROOT,
        help="Local SCF artifact root; defaults to local-data/scf.",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Reuse matching local SCF artifacts."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate SCF artifacts even when matching local artifacts exist.",
    )
    parser.add_argument("--no-x2c", action="store_true", help="Disable sf-X2C for debugging only.")
    parser.add_argument("--xc", default=None, help="Override XC functional from the YAML default.")
    parser.add_argument("--conv-tol", type=float, default=None, help="Override SCF conv_tol.")
    parser.add_argument("--max-cycle", type=int, default=None, help="Override maximum SCF cycles.")
    parser.add_argument("--diis-space", type=int, default=None, help="Override PySCF DIIS space.")
    parser.add_argument(
        "--diis-start-cycle",
        type=int,
        default=None,
        help="Override the SCF cycle where DIIS acceleration starts.",
    )
    parser.add_argument(
        "--grid-level", type=int, default=None, help="Override PySCF DFT grid level."
    )
    parser.add_argument("--verbose", type=int, default=3, help="PySCF verbosity.")
    parser.add_argument(
        "--quiet-scf-log",
        action="store_true",
        help="Capture PySCF logs to scf.log without echoing them to stdout.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue selected jobs after one SCF failure.",
    )
    parser.add_argument(
        "--allow-pyscf-version-mismatch",
        action="store_true",
        help=(
            "Allow generator execution when the installed PySCF version differs from "
            "defaults.expected_engine_version in data/profile_datasets.yaml. This is "
            "for debugging only and should not be used for release data."
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the selected wavefunction plan and exit before running PySCF.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate/print the plan and exit before importing or running PySCF.",
    )
    parser.add_argument(
        "--show-jobs",
        action="store_true",
        help="Print every selected state/dataset job.",
    )
    return parser.parse_args()


def _selected_dataset_ids(values: list[str], configured_ids: tuple[str, ...]) -> tuple[str, ...]:
    if not values:
        return configured_ids
    expanded: list[str] = []
    aliases = {ALL_PROFILE_DATASETS}
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


def _settings_from_args(
    args: argparse.Namespace, defaults: dict[str, Any], chkfile: Path
) -> SCFSettings:
    relativity = str(defaults.get("relativity", "sf-X2C-1e"))
    use_x2c = (relativity != "none") and not args.no_x2c
    return SCFSettings(
        xc=str(args.xc or defaults.get("xc", "PBE0")),
        use_x2c=use_x2c,
        conv_tol=float(
            args.conv_tol if args.conv_tol is not None else defaults.get("conv_tol", 1e-9)
        ),
        max_cycle=int(
            args.max_cycle if args.max_cycle is not None else defaults.get("max_cycle", 300)
        ),
        diis_space=int(
            args.diis_space if args.diis_space is not None else defaults.get("diis_space", 12)
        ),
        diis_start_cycle=int(
            args.diis_start_cycle
            if args.diis_start_cycle is not None
            else defaults.get("diis_start_cycle", 1)
        ),
        grid_level=int(
            args.grid_level if args.grid_level is not None else defaults.get("grid_level", 4)
        ),
        verbose=args.verbose,
        chkfile=chkfile,
    )


def _print_plan(args: argparse.Namespace, jobs: tuple[ProfileBuildJob, ...], config: Any) -> None:
    print(f"Profile data version: {config.profile_data_version}")
    print(f"Dataset config: {repo_relative_path(args.config)}")
    print(f"SCF artifact root: {repo_relative_path(args.scf_root)}")
    print(
        format_build_plan(
            jobs, show_jobs=args.show_jobs, config=config
        )
    )


def _compute_one_job(
    *,
    job: ProfileBuildJob,
    state: AtomState,
    bundle: Any,
    config: Any,
    config_path: Path,
    scf_root: Path,
    args: argparse.Namespace,
    pyscf_version: str,
) -> str:
    paths = scf_artifact_paths(scf_root, job.dataset_id, job.state_id)
    settings = _settings_from_args(args, config.defaults, paths.chk)
    fingerprints = scf_fingerprints(
        config_path=config_path,
        config=config,
        state=state,
        bundle=bundle,
        settings=settings,
        pyscf_version=pyscf_version,
    )
    if args.resume and not args.force and scf_artifact_is_reusable(paths, fingerprints):
        return "skipped_reusable"

    paths.state_dir.mkdir(parents=True, exist_ok=True)
    log_capture = TeeCapture(None if args.quiet_scf_log else sys.stdout)
    settings = SCFSettings(
        xc=settings.xc,
        use_x2c=settings.use_x2c,
        conv_tol=settings.conv_tol,
        max_cycle=settings.max_cycle,
        diis_space=settings.diis_space,
        diis_start_cycle=settings.diis_start_cycle,
        grid_level=settings.grid_level,
        grid_prune=settings.grid_prune,
        verbose=settings.verbose,
        stdout=log_capture,
        chkfile=settings.chkfile,
    )
    run = run_dataset_state(state, bundle, dataset_id=job.dataset_id, settings=settings)
    log_text = log_capture.getvalue()
    paths.log.write_text(log_text, encoding="utf-8")
    write_scf_npz(paths.npz, run.mf)
    metadata = scf_metadata(
        dataset_id=job.dataset_id,
        state=state,
        bundle=bundle,
        config=config,
        config_path=config_path,
        settings=settings,
        pyscf_version=pyscf_version,
        mf=run.mf,
        log_text=log_text,
    )
    write_json(paths.metadata, metadata)
    if not bool(metadata.get("results", {}).get("converged")):
        raise RuntimeError(
            "SCF did not converge; diagnostic artifacts were written to "
            f"{repo_relative_path(paths.state_dir)}"
        )
    return "computed"


def main() -> int:
    args = parse_args()
    config = load_profile_dataset_config(args.config)
    dataset_ids = _selected_dataset_ids(args.dataset_ids, config.dataset_ids or DATASET_IDS)
    states = load_atom_states(STATES_FILE)
    jobs = build_jobs_for_datasets(states, dataset_ids=dataset_ids, config=config)
    try:
        jobs = filter_build_jobs(jobs, only_state_ids=set(args.state_ids) or None)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not jobs:
        raise SystemExit("Selected wavefunction plan is empty")

    _print_plan(args, jobs, config)

    if args.list or args.dry_run:
        print("Dry run completed before PySCF import/SCF execution.")
        return 0

    state_by_id = {state.state_id: state for state in states}
    bundle_by_id = {bundle.basis_id: bundle for bundle in list_basis_bundles(BASIS_ROOT)}
    try:
        _gto, _dft, _pyscf_basis, pyscf_version = import_pyscf_modules()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    expected_pyscf_version = str(config.defaults.get("expected_engine_version", "")).strip()
    if (
        expected_pyscf_version
        and pyscf_version != expected_pyscf_version
        and not args.allow_pyscf_version_mismatch
    ):
        raise SystemExit(
            "Installed PySCF version "
            f"{pyscf_version!r} does not match the release-pinned version "
            f"{expected_pyscf_version!r}. Install the generator extra from this repo "
            "or rerun with --allow-pyscf-version-mismatch for debugging-only artifacts."
        )

    counts = {"computed": 0, "skipped_reusable": 0, "failed": 0}
    for index, job in enumerate(jobs, start=1):
        print(f"[{index}/{len(jobs)}] {job.dataset_id} :: {job.state_id}")
        state = state_by_id[job.state_id]
        bundle = bundle_by_id[job.basis_id]
        try:
            status = _compute_one_job(
                job=job,
                state=state,
                bundle=bundle,
                config=config,
                config_path=args.config,
                scf_root=args.scf_root,
                args=args,
                pyscf_version=pyscf_version,
            )
        except Exception as exc:
            counts["failed"] += 1
            print(f"ERROR: {job.dataset_id} :: {job.state_id}: {exc}", file=sys.stderr)
            if not args.continue_on_error:
                return 1
        else:
            counts[status] += 1
            print(f"SCF artifact status: {status}")

    print(
        "SCF summary: "
        f"computed={counts['computed']}, "
        f"skipped_reusable={counts['skipped_reusable']}, "
        f"failed={counts['failed']}"
    )
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
