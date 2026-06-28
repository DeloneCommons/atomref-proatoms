#!/usr/bin/env python3
"""Run one pilot spherical proatom profile.

This is intentionally not a full dataset builder yet.  It provides the first local
PySCF smoke path for Stage 5: choose one curated state and one dataset, enforce the
basis/dataset no-fallback rule, run spherical UKS, evaluate a profile, and write the
standard per-state artifacts.
"""

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

from atomref_proatoms.artifacts import (  # noqa: E402
    derived_radii_from_profile,
    profile_metadata_template,
    write_state_profile_artifacts,
)
from atomref_proatoms.basis import list_basis_bundles, sha256_file  # noqa: E402
from atomref_proatoms.datasets import (  # noqa: E402
    assert_dataset_basis_match,
    dataset_scope,
    expected_basis_for_dataset,
    state_allowed_in_dataset,
)
from atomref_proatoms.profiles import density_profile_from_mf  # noqa: E402
from atomref_proatoms.qa import (  # noqa: E402
    ANGULAR_SIGMA_RHO_FLOOR,
    linear_dependency_diagnostics_from_log,
    qa_result_from_profile,
    spin_diagnostics_from_mf,
)
from atomref_proatoms.scf import SCFSettings, import_pyscf_modules, run_dataset_state  # noqa: E402
from atomref_proatoms.states import AtomState, load_atom_states  # noqa: E402


class TeeCapture(io.StringIO):
    """Capture PySCF text while still echoing it to the terminal."""

    def __init__(self, stream: Any) -> None:
        super().__init__()
        self._stream = stream

    def write(self, text: str) -> int:
        self._stream.write(text)
        return super().write(text)

    def flush(self) -> None:
        self._stream.flush()
        super().flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-id", required=True, help="Curated state_id, e.g. C_q0_mult3_hund")
    parser.add_argument("--dataset-id", required=True, help="Target profile dataset_id")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "local-data" / "pilot-profiles",
        help="Output root for local pilot artifacts; defaults to local-data/pilot-profiles",
    )
    parser.add_argument("--no-x2c", action="store_true", help="Disable sf-X2C for debugging only")
    parser.add_argument("--xc", default="PBE0", help="XC functional, default PBE0")
    parser.add_argument("--conv-tol", type=float, default=1e-9, help="SCF convergence tolerance")
    parser.add_argument("--max-cycle", type=int, default=100, help="Maximum SCF cycles")
    parser.add_argument("--grid-level", type=int, default=4, help="PySCF DFT grid level")
    parser.add_argument(
        "--profile-n-ang", type=int, default=110, help="Angular grid size for profiles"
    )
    parser.add_argument(
        "--no-profile-qa",
        action="store_true",
        help="Skip independent electron-count QA integration",
    )
    parser.add_argument(
        "--qa-n-r",
        type=int,
        default=400,
        help="Number of log-r radial nodes for independent electron-count QA",
    )
    parser.add_argument(
        "--qa-n-ang",
        type=int,
        default=110,
        help="Angular grid size for independent electron-count QA",
    )
    parser.add_argument(
        "--qa-r-min",
        type=float,
        default=1.0e-7,
        help="Minimum radius for independent electron-count QA",
    )
    parser.add_argument(
        "--qa-r-max",
        type=float,
        default=120.0,
        help="Maximum radius for independent electron-count QA",
    )
    parser.add_argument(
        "--angular-sigma-rho-floor",
        type=float,
        default=ANGULAR_SIGMA_RHO_FLOOR,
        help="Ignore profile-grid angular sigma points with rho at or below this value",
    )
    parser.add_argument(
        "--profile-archive-format",
        choices=("zip", "csv.gz"),
        default="zip",
        help="Profile archive format; defaults to per-state .csv.zip archives",
    )
    parser.add_argument("--verbose", type=int, default=3, help="PySCF verbosity")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate state/dataset/basis selection without importing or running PySCF",
    )
    return parser.parse_args()


def find_state(state_id: str) -> AtomState:
    states = load_atom_states(ROOT / "data" / "states" / "curated" / "atom_states_v0.json")
    by_id = {state.state_id: state for state in states}
    try:
        return by_id[state_id]
    except KeyError as exc:
        raise SystemExit(f"Unknown state_id {state_id!r}") from exc


def find_basis_bundle(dataset_id: str):
    basis_id = expected_basis_for_dataset(dataset_id)
    bundles = list_basis_bundles(ROOT / "data" / "basis_sets")
    by_id = {bundle.basis_id: bundle for bundle in bundles}
    try:
        return by_id[basis_id]
    except KeyError as exc:
        raise SystemExit(f"Missing basis bundle {basis_id!r} for dataset {dataset_id!r}") from exc


def git_commit_or_none() -> str | None:
    git_dir = ROOT / ".git"
    if not git_dir.exists():
        return None
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def main() -> int:
    args = parse_args()
    state = find_state(args.state_id)
    scope = dataset_scope(args.dataset_id)
    bundle = find_basis_bundle(args.dataset_id)
    assert_dataset_basis_match(args.dataset_id, bundle.basis_id)
    if not state_allowed_in_dataset(args.dataset_id, z=state.z, charge=state.charge):
        raise SystemExit(
            f"State {state.state_id} (Z={state.z}, charge={state.charge}) is not allowed in "
            f"dataset {args.dataset_id} ({scope.role}, {scope.coverage_label})"
        )

    print(
        f"Selected {state.state_id}: {state.symbol}, charge={state.charge}, "
        f"multiplicity={state.multiplicity}"
    )
    print(f"Dataset: {args.dataset_id}")
    print(f"Basis: {bundle.basis_id} ({bundle.basis_sha256})")

    if args.dry_run:
        print("Dry run completed before PySCF import/SCF execution.")
        return 0

    scf_stdout = TeeCapture(sys.stdout)
    try:
        _gto, _dft, _pyscf_basis, pyscf_version = import_pyscf_modules()
        settings = SCFSettings(
            xc=args.xc,
            use_x2c=not args.no_x2c,
            conv_tol=args.conv_tol,
            max_cycle=args.max_cycle,
            grid_level=args.grid_level,
            verbose=args.verbose,
            stdout=scf_stdout,
        )
        run = run_dataset_state(state, bundle, dataset_id=args.dataset_id, settings=settings)
        profile = density_profile_from_mf(
            run.mf,
            n_ang=args.profile_n_ang,
            compute_qa=not args.no_profile_qa,
            qa_r_min=args.qa_r_min,
            qa_r_max=args.qa_r_max,
            qa_n_r=args.qa_n_r,
            qa_n_ang=args.qa_n_ang,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    derived = derived_radii_from_profile(profile)
    linear_dependency = linear_dependency_diagnostics_from_log(scf_stdout.getvalue())
    spin_diagnostics = spin_diagnostics_from_mf(run.mf, spin_2s=state.spin_2s)
    qa = qa_result_from_profile(
        scf_converged=bool(run.mf.converged),
        electron_count_exact=int(run.mf.mol.nelectron),
        derived=derived,
        profile=profile,
        linear_dependency_vectors_removed=linear_dependency.vectors_removed,
        angular_sigma_rho_floor=args.angular_sigma_rho_floor,
    ).to_json()
    metadata = profile_metadata_template(
        dataset_id=args.dataset_id,
        state=state,
        basis_id=bundle.basis_id,
        basis_sha256=bundle.basis_sha256,
        engine_version=pyscf_version,
        xc=args.xc,
        relativity="none" if args.no_x2c else "sf-X2C-1e",
        derived=derived,
        qa=qa,
        generator_git_commit=git_commit_or_none(),
        basis_manifest_sha256=sha256_file(bundle.path / "manifest.json"),
        diagnostics={
            "spin": spin_diagnostics.to_json(),
            "linear_dependency": linear_dependency.to_json(),
            "scf_log": {
                "captured": True,
                "line_count": len(scf_stdout.getvalue().splitlines()),
            },
        },
    )
    dataset_dir = args.output_dir / args.dataset_id
    profile_path, metadata_path = write_state_profile_artifacts(
        dataset_dir,
        state_id=state.state_id,
        profile=profile,
        metadata=metadata,
        profile_archive_format=args.profile_archive_format,
    )
    print(f"SCF converged: {bool(run.mf.converged)}")
    print(f"Energy / Eh: {float(run.mf.e_tot):.12g}")
    spin_json = spin_diagnostics.to_json()
    if spin_json["reported_spin_square"] is not None:
        print(
            "Spin diagnostic <S^2>: "
            f"{spin_json['reported_spin_square']:.6g} "
            f"(target {spin_json['target_spin_square']:.6g}; diagnostic only)"
        )
    if linear_dependency.vectors_removed is not None:
        print(f"Linear-dependency vectors removed: {linear_dependency.vectors_removed}")
    if qa["electron_count_error_qa"] is None:
        print("QA electron count error: skipped")
    else:
        print(f"QA electron count error: {qa['electron_count_error_qa']:.6g}")
    if qa["max_rel_angular_sigma"] is None:
        print("QA max relative angular sigma: unavailable")
    else:
        print(f"QA max relative angular sigma: {qa['max_rel_angular_sigma']:.6g}")
    print(f"Profile archive: {profile_path}")
    print(f"Metadata: {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
