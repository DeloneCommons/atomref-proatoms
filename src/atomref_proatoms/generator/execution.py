"""Execution bridge for the conservative public generator CLI.

This module connects the dry-run plan to the existing spherical-SCF,
profile, QA, Multiwfn ``.rad``, and neutral-only PROAIM ``.wfn`` machinery.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from .. import __version__
from ..engines.pyscf_backend import (
    SCFSettings,
    import_pyscf_modules,
    load_mol_from_chk,
    load_scf_npz,
    read_scf_metadata,
    scf_artifact_is_reusable,
    scf_artifact_paths,
    scf_fingerprints,
    scf_metadata,
    write_scf_npz,
)
from ..engines.spherical_scf import (
    apply_x2c_if_requested,
    configure_dft_grid,
    effective_l_counts_for_mol,
    make_spherical_uhf,
    make_spherical_uks,
    validate_spherical_ao_layout,
)
from ..exporters.multiwfn_rad import (
    MULTIWFN_ATMRAD_GRID_BOHR,
    evaluate_scf_radial_density,
    multiwfn_rad_filename,
    write_multiwfn_rad_file,
)
from ..exporters.proaim_wfn import atom_wfn_filename, write_atomref_scf_arrays_wfn
from ..profiles.artifacts import (
    profile_density_column,
    write_json,
    write_profile_dataset_artifacts,
    write_qa_dataset_artifacts,
    write_radii_dataset_artifacts,
)
from ..profiles.grids import log_radial_grid
from ..profiles.qa import (
    electron_count_tolerance,
    linear_dependency_diagnostics_from_log,
    qa_result_from_profile,
)
from ..profiles.radial import density_profile_from_mf, derived_radii
from ..states.state_tables import AtomState
from .basis_resolver import BasisCheckResult, BasisSpec, check_basis_source, sha256_text
from .planner import GeneratorPlan, build_generation_plan

GENERATOR_MANIFEST_SCHEMA_VERSION = "atomref.proatoms.generator_manifest.v1"
GENERATOR_PROFILE_DATASET_SCHEMA_VERSION = "atomref.proatoms.generator_profile_dataset.v1"
ANGULAR_SIGMA_REL_TOL = 1.0e-8


@dataclass(frozen=True)
class ExecutionOptions:
    """Runtime controls for the public generator execution path."""

    resume: bool = False
    force: bool = False
    continue_on_error: bool = False
    conv_tol: float | None = None
    max_cycle: int | None = None
    diis_space: int | None = None
    diis_start_cycle: int | None = None
    grid_level: int | None = None
    verbose: int = 3
    quiet_scf_log: bool = False
    allow_pyscf_version_mismatch: bool = False
    rad_angular_points: int = 1
    rad_eval_chunk_size: int = 8192


@dataclass(frozen=True)
class ExecutionResult:
    """Summary returned by generator execution."""

    status: str
    manifest_path: Path
    failures_path: Path
    computed_scf: int
    reused_scf: int
    failed_jobs: int
    written_files: tuple[Path, ...]


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


def execute_generation_plan(plan: GeneratorPlan, options: ExecutionOptions) -> ExecutionResult:
    """Execute profiles/radii/QA and ``.rad`` generation for a resolved plan."""

    if plan.errors:
        raise ValueError("plan has errors; rerun --dry-run and inspect plan.json")

    workdir = plan.request.workdir.expanduser()
    workdir.mkdir(parents=True, exist_ok=True)
    basis_check = _prepare_basis_cache(plan, workdir)
    _gto, _dft, _pyscf_basis, pyscf_version = import_pyscf_modules()
    _check_pyscf_version(plan, pyscf_version, options)

    states_by_id = {state.state_id: state for state in plan.state_selection.states}
    successful_state_ids: list[str] = []
    failures: list[dict[str, Any]] = []
    scf_status: dict[str, str] = {}

    for index, job in enumerate(plan.jobs, start=1):
        state = states_by_id[str(job["state_id"])]
        if not job.get("artifacts"):
            scf_status[state.state_id] = "skipped_no_requested_artifacts"
            continue
        print(f"[{index}/{len(plan.jobs)}] SCF {state.state_id}", flush=True)
        try:
            status = _ensure_scf_artifacts(
                plan=plan,
                state=state,
                basis_check=basis_check,
                pyscf_version=pyscf_version,
                options=options,
            )
        except Exception as exc:
            failures.append(_failure_record(state=state, stage="scf", exc=exc))
            print(f"ERROR: SCF {state.state_id}: {exc}", file=sys.stderr)
            if not options.continue_on_error:
                _write_failures_csv(workdir / "failures.csv", failures)
                manifest_path = _write_manifest(
                    plan,
                    workdir=workdir,
                    status="failed",
                    scf_status=scf_status,
                    generated_files=(),
                    failures=failures,
                )
                return ExecutionResult(
                    status="failed",
                    manifest_path=manifest_path,
                    failures_path=workdir / "failures.csv",
                    computed_scf=sum(1 for value in scf_status.values() if value == "computed"),
                    reused_scf=sum(1 for value in scf_status.values() if value == "reused"),
                    failed_jobs=len(failures),
                    written_files=(),
                )
            continue
        scf_status[state.state_id] = status
        successful_state_ids.append(state.state_id)

    generated_files: list[Path] = []
    successful_states = tuple(states_by_id[state_id] for state_id in successful_state_ids)
    if successful_states and "profiles" in plan.artifacts:
        try:
            generated_files.extend(
                _write_profile_outputs(
                    plan,
                    workdir,
                    successful_states,
                    basis_check=basis_check,
                )
            )
        except Exception as exc:
            failures.append({"stage": "profiles", "state_id": None, "error": repr(exc)})
            print(f"ERROR: profile/radii/QA generation: {exc}", file=sys.stderr)
            if not options.continue_on_error:
                _write_failures_csv(workdir / "failures.csv", failures)
                manifest_path = _write_manifest(
                    plan,
                    workdir=workdir,
                    status="failed",
                    scf_status=scf_status,
                    generated_files=tuple(generated_files),
                    failures=failures,
                )
                return ExecutionResult(
                    status="failed",
                    manifest_path=manifest_path,
                    failures_path=workdir / "failures.csv",
                    computed_scf=sum(1 for value in scf_status.values() if value == "computed"),
                    reused_scf=sum(1 for value in scf_status.values() if value == "reused"),
                    failed_jobs=len(failures),
                    written_files=tuple(generated_files),
                )

    multiwfn_records: list[dict[str, Any]] = []
    if successful_states and "rad" in plan.artifacts:
        rad_files, rad_records = _write_rad_outputs(
            plan,
            workdir,
            successful_states,
            options=options,
            failures=failures,
        )
        generated_files.extend(rad_files)
        multiwfn_records.extend(rad_records)

    if successful_states and "wfn" in plan.artifacts:
        wfn_files, wfn_records = _write_wfn_outputs(
            plan,
            workdir,
            successful_states,
            options=options,
            failures=failures,
        )
        generated_files.extend(wfn_files)
        multiwfn_records.extend(wfn_records)

    if "rad" in plan.artifacts or "wfn" in plan.artifacts:
        generated_files.append(_write_multiwfn_manifest(plan, workdir, multiwfn_records))

    failures_path = _write_failures_csv(workdir / "failures.csv", failures)
    status = "failed" if failures else "ok"
    manifest_path = _write_manifest(
        plan,
        workdir=workdir,
        status=status,
        scf_status=scf_status,
        generated_files=tuple(generated_files),
        failures=failures,
    )
    return ExecutionResult(
        status=status,
        manifest_path=manifest_path,
        failures_path=failures_path,
        computed_scf=sum(1 for value in scf_status.values() if value == "computed"),
        reused_scf=sum(1 for value in scf_status.values() if value == "reused"),
        failed_jobs=len(failures),
        written_files=tuple(generated_files),
    )


def execute_request(request: Any, options: ExecutionOptions) -> ExecutionResult:
    """Build and execute a plan for a raw request object."""

    return execute_generation_plan(build_generation_plan(request), options)


def _check_pyscf_version(
    plan: GeneratorPlan,
    pyscf_version: str,
    options: ExecutionOptions,
) -> None:
    expected = str(plan.defaults.get("scf_defaults", {}).get("expected_engine_version", "")).strip()
    if expected and pyscf_version != expected and not options.allow_pyscf_version_mismatch:
        raise RuntimeError(
            "Installed PySCF version "
            f"{pyscf_version!r} does not match the release-pinned version {expected!r}. "
            "Install the generator extra from this repo or rerun with "
            "--allow-pyscf-version-mismatch for debugging-only artifacts."
        )


def _prepare_basis_cache(plan: GeneratorPlan, workdir: Path) -> BasisCheckResult:
    """Write basis provenance files and return an execution-ready basis check."""

    basis_check = check_basis_source(plan.basis, plan.state_selection.elements)
    if basis_check.status.startswith("not_performed"):
        raise RuntimeError(
            f"basis source {plan.basis.basis_key!r} could not be resolved for execution: "
            f"{basis_check.status}"
        )
    if basis_check.status != "ok":
        raise RuntimeError("basis check failed: " + "; ".join(basis_check.errors))
    if basis_check.full_electron_status == "ecp_detected" and not plan.request.allow_ecp:
        raise RuntimeError(
            "ECP/effective-core basis data were detected; rerun with --allow-ecp to allow it."
        )

    basis_dir = workdir / "basis"
    basis_dir.mkdir(parents=True, exist_ok=True)
    write_json(basis_dir / "basis_source.json", plan.basis.as_dict())
    write_json(basis_dir / "basis_check.json", basis_check.as_dict())
    basis_sha256 = _execution_basis_sha256(plan, basis_check)
    write_json(
        basis_dir / "manifest.json",
        {
            "schema_version": "atomref.proatoms.generator_basis_manifest.v1",
            "basis_key": plan.basis.basis_key,
            "basis_sha256": basis_sha256,
            "basis_source": plan.basis.as_dict(),
            "check_method": basis_check.check_method,
            "full_electron_status": basis_check.full_electron_status,
            "ecp_detected": basis_check.ecp_detected,
            "ecp_symbols": list(basis_check.ecp_symbols),
        },
    )
    checksum_rows: list[tuple[str, str]] = []
    if basis_check.rendered_nwchem is not None:
        basis_path = basis_dir / "basis.nw"
        basis_path.write_text(basis_check.rendered_nwchem, encoding="utf-8")
        checksum_rows.append((sha256_text(basis_check.rendered_nwchem), "basis.nw"))
    checksum_rows.extend(
        (
            (
                sha256_text((basis_dir / "basis_source.json").read_text(encoding="utf-8")),
                "basis_source.json",
            ),
            (
                sha256_text((basis_dir / "basis_check.json").read_text(encoding="utf-8")),
                "basis_check.json",
            ),
            (
                sha256_text((basis_dir / "manifest.json").read_text(encoding="utf-8")),
                "manifest.json",
            ),
        )
    )
    (basis_dir / "sha256sums.txt").write_text(
        "".join(f"{digest}  {name}\n" for digest, name in checksum_rows),
        encoding="utf-8",
    )
    return basis_check


def _build_atom_mol(
    *,
    state: AtomState,
    basis: BasisSpec,
    basis_check: BasisCheckResult,
    allow_ecp: bool,
    verbose: int,
    stdout: Any | None,
) -> Any:
    gto, _dft, pyscf_basis, _version = import_pyscf_modules()
    mol = gto.Mole()
    mol.atom = f"{state.symbol} 0 0 0"
    if basis.source == "pyscf":
        mol.basis = {state.symbol: basis.name}
        if allow_ecp and basis_check.ecp_detected:
            mol.ecp = {state.symbol: basis.name}
    else:
        if basis_check.rendered_nwchem is None:
            raise RuntimeError(f"basis source {basis.basis_key!r} has no rendered NWChem text")
        basis_text = _nwchem_basis_block(basis_check.rendered_nwchem)
        mol.basis = {state.symbol: pyscf_basis.parse(basis_text, symb=state.symbol)}
        if allow_ecp and _basis_check_has_ecp_for_symbol(basis_check, state.symbol):
            try:
                ecp_text = _nwchem_ecp_block(basis_check.rendered_nwchem)
                mol.ecp = {state.symbol: pyscf_basis.parse_ecp(ecp_text, symb=state.symbol)}
            except Exception as exc:
                raise RuntimeError(
                    f"Could not parse NWChem ECP data for {state.symbol} from "
                    f"basis source {basis.basis_key!r}"
                ) from exc
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
    return mol


def _extract_nwchem_block(text: str, header: str) -> str:
    lines = text.splitlines()
    selected: list[str] = []
    active = False
    for raw_line in lines:
        stripped = raw_line.strip()
        if not active and stripped.lower().startswith(header.lower()):
            active = True
        if active:
            selected.append(raw_line)
            if stripped.lower() == "end":
                break
    return "\n".join(selected) + "\n" if selected else text


def _nwchem_basis_block(text: str) -> str:
    return _extract_nwchem_block(text, "basis")


def _nwchem_ecp_block(text: str) -> str:
    return _extract_nwchem_block(text, "ecp")


def _basis_check_has_ecp_for_symbol(basis_check: BasisCheckResult, symbol: str) -> bool:
    ecp_symbols = getattr(basis_check, "ecp_symbols", ())
    if ecp_symbols:
        return symbol in set(ecp_symbols)
    return bool(basis_check.ecp_detected)


def _scf_settings(plan: GeneratorPlan, options: ExecutionOptions, chkfile: Path) -> SCFSettings:
    defaults = dict(plan.defaults.get("scf_defaults", {}))
    xc = plan.method.xc or "HF"
    return SCFSettings(
        xc=xc,
        use_x2c=plan.relativity.relativity == "x2c",
        conv_tol=float(
            options.conv_tol if options.conv_tol is not None else defaults.get("conv_tol", 1e-9)
        ),
        max_cycle=int(
            options.max_cycle
            if options.max_cycle is not None
            else defaults.get("max_cycle", 300)
        ),
        diis_space=int(
            options.diis_space
            if options.diis_space is not None
            else defaults.get("diis_space", 12)
        ),
        diis_start_cycle=int(
            options.diis_start_cycle
            if options.diis_start_cycle is not None
            else defaults.get("diis_start_cycle", 1)
        ),
        grid_level=int(
            options.grid_level
            if options.grid_level is not None
            else defaults.get("grid_level", 4)
        ),
        verbose=options.verbose,
        chkfile=chkfile,
    )


def _density_model(plan: GeneratorPlan) -> str:
    if plan.method.method_kind == "hf":
        return "self_consistent_fractional_occupation_spherical_uhf"
    return "self_consistent_fractional_occupation_spherical_uks"


def _profile_config_proxy(plan: GeneratorPlan) -> Any:
    return SimpleNamespace(
        defaults={
            "engine": "pyscf",
            "expected_engine_version": str(
                plan.defaults.get("scf_defaults", {}).get("expected_engine_version", "")
            ),
            "scf_type": plan.method.scf_type,
            "xc": plan.method.xc or "HF",
            "relativity": plan.relativity.engine_label,
            "density_model": _density_model(plan),
        }
    )


def _execution_basis_sha256(plan: GeneratorPlan, basis_check: BasisCheckResult) -> str:
    if basis_check.basis_sha256:
        return str(basis_check.basis_sha256)
    payload = {
        "basis": plan.basis.as_dict(),
        "requested_symbols": list(basis_check.requested_symbols),
        "check_method": basis_check.check_method,
    }
    return sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _basis_bundle_proxy(plan: GeneratorPlan, basis_check: BasisCheckResult) -> Any:
    basis_dir = plan.request.workdir.expanduser() / "basis"
    rendered_basis_path = basis_dir / "basis.nw"
    basis_path = (
        rendered_basis_path
        if rendered_basis_path.exists()
        else basis_dir / "basis_source.json"
    )
    return SimpleNamespace(
        basis_id=plan.basis.basis_key,
        basis_sha256=_execution_basis_sha256(plan, basis_check),
        basis_path=basis_path,
        path=basis_path.parent,
        manifest={"source": {"source_api_url": str(plan.basis.original or plan.basis.basis_key)}},
    )


def _apply_common_scf_controls(
    mf: Any,
    settings: SCFSettings,
    *,
    configure_grid: bool,
) -> None:
    if settings.stdout is not None:
        mf.stdout = settings.stdout
    if settings.chkfile is not None:
        mf.chkfile = str(settings.chkfile)
    mf.conv_tol = settings.conv_tol
    mf.max_cycle = settings.max_cycle
    mf.diis_space = settings.diis_space
    mf.diis_start_cycle = settings.diis_start_cycle
    if configure_grid and hasattr(mf, "grids"):
        configure_dft_grid(mf, level=settings.grid_level, prune=settings.grid_prune)


def _ensure_scf_artifacts(
    *,
    plan: GeneratorPlan,
    state: AtomState,
    basis_check: BasisCheckResult,
    pyscf_version: str,
    options: ExecutionOptions,
) -> str:
    scf_root = plan.request.workdir.expanduser() / "scf"
    paths = scf_artifact_paths(scf_root, plan.run_id, state.state_id)
    config_proxy = _profile_config_proxy(plan)
    bundle_proxy = _basis_bundle_proxy(plan, basis_check)
    settings = _scf_settings(plan, options, paths.chk)
    fingerprints = scf_fingerprints(
        config_path=plan.request.workdir / "run_config.resolved.json",
        config=config_proxy,
        state=state,
        bundle=bundle_proxy,
        settings=settings,
        pyscf_version=pyscf_version,
    )
    if options.resume and scf_artifact_is_reusable(paths, fingerprints):
        return "reused"

    paths.state_dir.mkdir(parents=True, exist_ok=True)
    log_capture = TeeCapture(None if options.quiet_scf_log else sys.stdout)
    run_settings = SCFSettings(
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
    mol = _build_atom_mol(
        state=state,
        basis=plan.basis,
        basis_check=basis_check,
        allow_ecp=plan.request.allow_ecp,
        verbose=run_settings.verbose,
        stdout=run_settings.stdout,
    )
    alpha_l_counts, beta_l_counts = effective_l_counts_for_mol(state, mol)
    if plan.method.method_kind == "hf":
        mf = make_spherical_uhf(
            mol,
            alpha_l_counts=alpha_l_counts,
            beta_l_counts=beta_l_counts,
        )
        _apply_common_scf_controls(mf, run_settings, configure_grid=False)
    else:
        mf = make_spherical_uks(
            mol,
            xc=run_settings.xc,
            alpha_l_counts=alpha_l_counts,
            beta_l_counts=beta_l_counts,
        )
        _apply_common_scf_controls(mf, run_settings, configure_grid=True)
    mf = apply_x2c_if_requested(mf, use_x2c=run_settings.use_x2c)
    _apply_common_scf_controls(mf, run_settings, configure_grid=False)
    mf.kernel()
    log_text = log_capture.getvalue()
    paths.log.write_text(log_text, encoding="utf-8")
    write_scf_npz(paths.npz, mf)
    metadata = scf_metadata(
        dataset_id=plan.run_id,
        state=state,
        bundle=bundle_proxy,
        config=config_proxy,
        config_path=plan.request.workdir / "run_config.resolved.json",
        settings=run_settings,
        pyscf_version=pyscf_version,
        mf=mf,
        log_text=log_text,
    )
    metadata["generator"] = {
        "schema_version": GENERATOR_MANIFEST_SCHEMA_VERSION,
        "package_version": __version__,
        "basis_source": plan.basis.as_dict(),
    }
    write_json(paths.metadata, metadata)
    if not bool(metadata.get("results", {}).get("converged")):
        raise RuntimeError(
            "SCF did not converge; diagnostic artifacts were written to "
            f"{paths.state_dir}"
        )
    return "computed"


def _profile_grid(plan: GeneratorPlan) -> np.ndarray:
    grid = plan.defaults.get("profile_grid", {})
    if grid.get("type") != "log":
        raise ValueError(f"Unsupported profile grid type {grid.get('type')!r}")
    return log_radial_grid(
        float(grid["r_min_bohr"]),
        float(grid["r_max_bohr"]),
        int(grid["n"]),
    )


def _qa_grid_kwargs(plan: GeneratorPlan) -> dict[str, Any]:
    grid = plan.defaults.get("qa_grid", {})
    if grid.get("type") != "gauss_legendre_log_r":
        raise ValueError(f"Unsupported QA grid type {grid.get('type')!r}")
    return {
        "qa_r_min": float(grid["r_min_bohr"]),
        "qa_r_max": float(grid["r_max_bohr"]),
        "qa_n_r": int(grid["n"]),
        "qa_n_ang": int(grid.get("angular_points", 110)),
    }


def _state_metadata(state: AtomState, scf_meta: Mapping[str, Any]) -> dict[str, Any]:
    results = scf_meta.get("results", {})
    explicit_electron_count = int(results.get("nelectron", state.electron_count))
    return {
        "symbol": state.symbol,
        "z": state.z,
        "charge": state.charge,
        "electron_count": explicit_electron_count,
        "explicit_electron_count": explicit_electron_count,
        "state_electron_count": state.electron_count,
        "effective_core_electrons": int(results.get("effective_core_electrons", 0)),
        "spin_2s": state.spin_2s,
        "multiplicity": state.multiplicity,
        "configuration": state.record["configuration"],
        "spin_model": state.record["spin_model"],
        "spin_variant": state.record["spin_variant"],
        "occupation_policy": state.record["occupation_policy"],
        "state_category": state.record["state_category"],
        "state_role": state.record["state_role"],
        "curation_status": state.record["curation_status"],
        "scf_state_metadata": dict(scf_meta.get("state", {})),
    }


def _write_profile_outputs(
    plan: GeneratorPlan,
    workdir: Path,
    states: tuple[AtomState, ...],
    *,
    basis_check: BasisCheckResult,
) -> tuple[Path, ...]:
    r_grid = _profile_grid(plan)
    qa_kwargs = _qa_grid_kwargs(plan)
    profile_n_ang = int(plan.defaults.get("profile_grid", {}).get("angular_points", 110))
    cutoffs = [float(value) for value in plan.defaults.get("cutoffs_e_bohr3", [])]
    densities: dict[str, Any] = {}
    columns: dict[str, dict[str, Any]] = {}
    states_metadata: dict[str, dict[str, Any]] = {}
    derived_by_state: dict[str, dict[str, float]] = {}
    qa_by_state: dict[str, dict[str, Any]] = {}
    scf_artifacts: dict[str, dict[str, Any]] = {}
    method: dict[str, Any] | None = None

    for state in states:
        paths = scf_artifact_paths(workdir / "scf", plan.run_id, state.state_id)
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
            compute_qa=True,
            **qa_kwargs,
        )
        scf_meta = read_scf_metadata(paths.metadata)
        state_derived = derived_radii(profile["r_bohr"], profile["rho_e_bohr3"], cutoffs)
        linear_dependency = linear_dependency_diagnostics_from_log(
            paths.log.read_text(encoding="utf-8")
        )
        results = scf_meta.get("results", {})
        explicit_electron_count = int(results.get("nelectron", state.electron_count))
        effective_core_electrons = int(results.get("effective_core_electrons", 0))
        qa_result = qa_result_from_profile(
            scf_converged=bool(results.get("converged")),
            electron_count_exact=explicit_electron_count,
            derived=state_derived,
            profile=profile,
            linear_dependency_vectors_removed=linear_dependency.vectors_removed,
        ).to_json()
        qa_result["linear_dependency_warning_count"] = linear_dependency.warning_count
        qa_result["electron_count_reference"] = explicit_electron_count
        qa_result["state_electron_count"] = state.electron_count
        qa_result["effective_core_electrons"] = effective_core_electrons
        qa_result["electron_count_tolerance"] = electron_count_tolerance(explicit_electron_count)
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
            "electron_count": explicit_electron_count,
            "state_electron_count": state.electron_count,
            "effective_core_electrons": effective_core_electrons,
            "multiplicity": state.multiplicity,
        }
        states_metadata[state.state_id] = _state_metadata(state, scf_meta)
        derived_by_state[state.state_id] = state_derived
        qa_by_state[state.state_id] = qa_result
        scf_artifacts[state.state_id] = _scf_artifact_summary(workdir, paths, scf_meta)
        job_method = dict(scf_meta.get("method", {}))
        method = job_method if method is None else method

    if method is None:
        raise ValueError("no successful SCF states available for profile generation")
    metadata = {
        "schema_version": GENERATOR_PROFILE_DATASET_SCHEMA_VERSION,
        "profile_data_version": str(plan.defaults.get("profile_data_version", "2.0.0")),
        "dataset_id": plan.run_id,
        "basis_id": plan.basis.basis_key,
        "basis_sha256": _execution_basis_sha256(plan, basis_check),
        "density_model": _density_model(plan),
        "method": method,
        "units": {"r": "bohr", "rho": "electron/bohr^3"},
        "profile_grid": dict(plan.defaults.get("profile_grid", {})),
        "qa_grid": dict(plan.defaults.get("qa_grid", {})),
        "cutoffs_e_bohr3": cutoffs,
        "columns": columns,
        "states": states_metadata,
        "scf_artifacts": scf_artifacts,
        "related_artifacts": {
            "profiles_csv": "profiles/profiles.csv",
            "profile_metadata_json": "profiles/metadata.json",
            "radii_csv": "radii/radii.csv",
            "radii_metadata_json": "radii/metadata.json",
            "qa_csv": "qa/qa.csv",
            "qa_metadata_json": "qa/metadata.json",
        },
        "provenance": {
            "generator_run_id": plan.run_id,
            "state_table_sha256": plan.state_table_sha256,
            "tool_defaults_sha256": plan.tool_defaults_sha256,
        },
    }
    profiles_csv, profiles_metadata = write_profile_dataset_artifacts(
        workdir / "profiles",
        r_bohr=r_grid,
        densities_by_state_id=densities,
        metadata=metadata,
    )
    radii_csv, radii_metadata = write_radii_dataset_artifacts(
        workdir / "radii",
        dataset_id=plan.run_id,
        profile_data_version=str(plan.defaults.get("profile_data_version", "2.0.0")),
        basis_id=plan.basis.basis_key,
        cutoffs_e_bohr3=cutoffs,
        states=states_metadata,
        derived_radii_by_state_id=derived_by_state,
        source_profiles_csv="profiles/profiles.csv",
        source_metadata_json="profiles/metadata.json",
        provenance={"generator_run_id": plan.run_id},
    )
    qa_csv, qa_metadata = write_qa_dataset_artifacts(
        workdir / "qa",
        dataset_id=plan.run_id,
        profile_data_version=str(plan.defaults.get("profile_data_version", "2.0.0")),
        basis_id=plan.basis.basis_key,
        states=states_metadata,
        qa_by_state_id=qa_by_state,
        source_profiles_csv="profiles/profiles.csv",
        source_metadata_json="profiles/metadata.json",
        provenance={"generator_run_id": plan.run_id},
    )
    return (profiles_csv, profiles_metadata, radii_csv, radii_metadata, qa_csv, qa_metadata)


def _scf_artifact_summary(workdir: Path, paths: Any, metadata: Mapping[str, Any]) -> dict[str, Any]:
    def rel(path: Path) -> str:
        return path.relative_to(workdir).as_posix()

    return {
        "schema_version": metadata.get("schema_version"),
        "scf_chk": rel(paths.chk),
        "scf_npz": rel(paths.npz),
        "scf_json": rel(paths.metadata),
        "scf_log": rel(paths.log),
        "results": dict(metadata.get("results", {})),
    }


def _write_rad_outputs(
    plan: GeneratorPlan,
    workdir: Path,
    states: tuple[AtomState, ...],
    *,
    options: ExecutionOptions,
    failures: list[dict[str, Any]],
) -> tuple[tuple[Path, ...], tuple[dict[str, Any], ...]]:
    written: list[Path] = []
    rad_dir = workdir / "multiwfn" / "rad"
    manifest_files: list[dict[str, Any]] = []
    for state in states:
        try:
            paths = scf_artifact_paths(workdir / "scf", plan.run_id, state.state_id)
            mol = load_mol_from_chk(paths.chk)
            arrays = load_scf_npz(paths.npz)
            metadata = read_scf_metadata(paths.metadata)
            dm_total = np.asarray(arrays["dm_alpha"], dtype=float) + np.asarray(
                arrays["dm_beta"], dtype=float
            )
            r_bohr, rho_e_bohr3 = evaluate_scf_radial_density(
                mol,
                dm_total,
                r_bohr=MULTIWFN_ATMRAD_GRID_BOHR,
                n_ang=options.rad_angular_points,
                coord_block_size=options.rad_eval_chunk_size,
            )
            out_path = rad_dir / multiwfn_rad_filename(state.symbol, state.charge)
            if out_path.exists() and not options.force:
                raise FileExistsError(
                    "Refusing to overwrite existing file without --force: "
                    f"{out_path}"
                )
            info = write_multiwfn_rad_file(out_path, r_bohr, rho_e_bohr3)
            written.append(out_path)
            manifest_files.append(
                {
                    "format": "rad",
                    "state_id": state.state_id,
                    "symbol": state.symbol,
                    "charge": state.charge,
                    "electron_count": int(
                        metadata.get("results", {}).get("nelectron", state.electron_count)
                    ),
                    "state_electron_count": state.electron_count,
                    "effective_core_electrons": int(
                        metadata.get("results", {}).get("effective_core_electrons", 0)
                    ),
                    "path": out_path.relative_to(workdir).as_posix(),
                    "source": "scf_density_evaluation",
                    "rad_grid_source": "Multiwfn atmrad exemplar grid",
                    "rad_angular_points": int(options.rad_angular_points),
                    "source_scf_checkpoint": paths.chk.relative_to(workdir).as_posix(),
                    "source_scf_npz": paths.npz.relative_to(workdir).as_posix(),
                    "source_scf_metadata": paths.metadata.relative_to(workdir).as_posix(),
                    "source_scf_converged": bool(metadata.get("results", {}).get("converged")),
                    **info,
                }
            )
        except Exception as exc:
            failures.append(_failure_record(state=state, stage="rad", exc=exc))
            print(f"ERROR: .rad {state.state_id}: {exc}", file=sys.stderr)
            if not options.continue_on_error:
                break
    return tuple(written), tuple(manifest_files)


def _scf_total_energy(metadata: Mapping[str, Any]) -> float | None:
    results = metadata.get("results")
    if isinstance(results, Mapping) and results.get("total_energy_hartree") is not None:
        return float(results["total_energy_hartree"])
    return None


def _write_wfn_outputs(
    plan: GeneratorPlan,
    workdir: Path,
    states: tuple[AtomState, ...],
    *,
    options: ExecutionOptions,
    failures: list[dict[str, Any]],
) -> tuple[tuple[Path, ...], tuple[dict[str, Any], ...]]:
    written: list[Path] = []
    manifest_files: list[dict[str, Any]] = []
    wfn_dir = workdir / "multiwfn" / "wfn"
    for state in states:
        if state.charge != 0:
            continue
        try:
            paths = scf_artifact_paths(workdir / "scf", plan.run_id, state.state_id)
            mol = load_mol_from_chk(paths.chk)
            arrays = load_scf_npz(paths.npz)
            metadata = read_scf_metadata(paths.metadata)
            out_path = wfn_dir / atom_wfn_filename(state.symbol)
            if out_path.exists() and not options.force:
                raise FileExistsError(
                    "Refusing to overwrite existing file without --force: "
                    f"{out_path}"
                )
            info = write_atomref_scf_arrays_wfn(
                out_path,
                state,
                mol,
                arrays,
                title=f"atomref-proatoms {state.state_id} {plan.basis.basis_key}",
                total_energy=_scf_total_energy(metadata),
            )
            written.append(out_path)
            manifest_files.append(
                {
                    "format": "wfn",
                    "state_id": state.state_id,
                    "symbol": state.symbol,
                    "charge": state.charge,
                    "electron_count": state.electron_count,
                    "path": out_path.relative_to(workdir).as_posix(),
                    "source": "scf_wavefunction_export",
                    "source_scf_checkpoint": paths.chk.relative_to(workdir).as_posix(),
                    "source_scf_npz": paths.npz.relative_to(workdir).as_posix(),
                    "source_scf_metadata": paths.metadata.relative_to(workdir).as_posix(),
                    "source_scf_converged": bool(metadata.get("results", {}).get("converged")),
                    **info,
                }
            )
        except Exception as exc:
            failures.append(_failure_record(state=state, stage="wfn", exc=exc))
            print(f"ERROR: .wfn {state.state_id}: {exc}", file=sys.stderr)
            if not options.continue_on_error:
                break
    return tuple(written), tuple(manifest_files)


def _write_multiwfn_manifest(
    plan: GeneratorPlan,
    workdir: Path,
    files: list[dict[str, Any]],
) -> Path:
    path = workdir / "multiwfn" / "manifest.json"
    write_json(
        path,
        {
            "schema_version": "atomref.proatoms.generator_multiwfn_manifest.v1",
            "run_id": plan.run_id,
            "profile_data_version": str(plan.defaults.get("profile_data_version", "2.0.0")),
            "files": files,
            "notes": {
                "rad": (
                    "Density-only Multiwfn .rad files evaluated from local SCF "
                    "arrays/checkpoints."
                ),
                "wfn": (
                    "Neutral-only PROAIM WFN files generated from local SCF "
                    "arrays/checkpoints."
                ),
            },
        },
    )
    return path


def _failure_record(*, state: AtomState, stage: str, exc: Exception) -> dict[str, Any]:
    return {
        "stage": stage,
        "state_id": state.state_id,
        "symbol": state.symbol,
        "charge": state.charge,
        "error": repr(exc),
    }


def _write_failures_csv(path: Path, failures: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["stage", "state_id", "symbol", "charge", "error"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for failure in failures:
            writer.writerow(failure)
    return path


def _write_manifest(
    plan: GeneratorPlan,
    *,
    workdir: Path,
    status: str,
    scf_status: Mapping[str, str],
    generated_files: tuple[Path, ...],
    failures: list[dict[str, Any]],
) -> Path:
    def rel(path: Path) -> str:
        try:
            return path.relative_to(workdir).as_posix()
        except ValueError:
            return path.as_posix()

    path = workdir / "manifest.json"
    write_json(
        path,
        {
            "schema_version": GENERATOR_MANIFEST_SCHEMA_VERSION,
            "package_version": __version__,
            "run_id": plan.run_id,
            "status": status,
            "method": plan.method.as_dict(),
            "relativity": plan.relativity.as_dict(),
            "basis": plan.basis.as_dict(),
            "state_selection": plan.state_selection.summary(),
            "artifacts": list(plan.artifacts),
            "scf_status": dict(scf_status),
            "generated_files": [rel(path) for path in generated_files],
            "failure_count": len(failures),
            "failures_csv": "failures.csv",
        },
    )
    return path
