"""Dry-run planning for the public generator CLI."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .. import __version__
from ..dataio.resources import resource_bytes, resource_origin, resource_text
from ..exporters.multiwfn_rad import multiwfn_rad_filename
from ..exporters.proaim_wfn import atom_wfn_filename
from ..states.state_tables import AtomState
from .basis_resolver import (
    BasisCheckResult,
    BasisPolicy,
    BasisPolicyDecision,
    BasisSpec,
    apply_basis_policy,
    check_basis_source,
    parse_basis_spec,
)
from .methods import (
    MethodCheck,
    MethodSpec,
    RelativitySpec,
    check_method_with_pyscf,
    parse_method,
    parse_relativity,
)
from .state_selection import (
    StateSelection,
    parse_element_range,
    parse_elements,
    select_packaged_states,
)
from .workspace import WorkspaceContext, WorkspaceStatus, require_compatible_workspace

ALLOWED_ARTIFACTS = frozenset({"profiles", "rad", "wfn"})
DEFAULT_WORKDIR = "atomref-proatoms-run"
TOOL_DEFAULTS_RESOURCE = "presets/tool_defaults.yaml"
STATE_TABLE_RESOURCE = "states/atom_states_v2.json"


@dataclass(frozen=True)
class GeneratorRequest:
    """Raw generator request used by the dry-run planner."""

    elements: tuple[str, ...] = ()
    element_range: str | None = None
    method: str | None = None
    relativity: str | None = None
    basis: str | None = None
    basis_file: Path | None = None
    basis_name: str | None = None
    state_policy: str | None = None
    charges: tuple[int, ...] | None = None
    artifacts: tuple[str, ...] | None = None
    workdir: Path = Path(DEFAULT_WORKDIR)
    resource_root: Path | None = None
    allow_ecp: bool = False
    allow_unverified_basis: bool = False
    resume: bool = False
    force: bool = False
    continue_on_error: bool = False
    allow_pyscf_version_mismatch: bool = False
    conv_tol: float | None = None
    max_cycle: int | None = None
    diis_space: int | None = None
    diis_start_cycle: int | None = None
    grid_level: int | None = None
    verbose: int = 3
    quiet_scf_log: bool = False
    rad_angular_points: int = 1
    rad_eval_chunk_size: int = 8192
    dry_run: bool = True

    def input_dict(self) -> dict[str, Any]:
        return {
            "elements": list(self.elements),
            "element_range": self.element_range,
            "method": self.method,
            "relativity": self.relativity,
            "basis": self.basis,
            "basis_file": self.basis_file.as_posix() if self.basis_file is not None else None,
            "basis_name": self.basis_name,
            "state_policy": self.state_policy,
            "charges": list(self.charges) if self.charges is not None else None,
            "artifacts": list(self.artifacts) if self.artifacts is not None else None,
            "workdir": self.workdir.as_posix(),
            "resource_root": (
                self.resource_root.as_posix() if self.resource_root is not None else None
            ),
            "allow_ecp": self.allow_ecp,
            "allow_unverified_basis": self.allow_unverified_basis,
            "resume": self.resume,
            "force": self.force,
            "continue_on_error": self.continue_on_error,
            "allow_pyscf_version_mismatch": self.allow_pyscf_version_mismatch,
            "conv_tol": self.conv_tol,
            "max_cycle": self.max_cycle,
            "diis_space": self.diis_space,
            "diis_start_cycle": self.diis_start_cycle,
            "grid_level": self.grid_level,
            "verbose": self.verbose,
            "quiet_scf_log": self.quiet_scf_log,
            "rad_angular_points": self.rad_angular_points,
            "rad_eval_chunk_size": self.rad_eval_chunk_size,
            "dry_run": self.dry_run,
        }


@dataclass(frozen=True)
class GeneratorPlan:
    """Resolved dry-run plan and the JSON files written for it."""

    request: GeneratorRequest
    run_id: str
    method: MethodSpec
    method_check: MethodCheck
    relativity: RelativitySpec
    basis: BasisSpec
    basis_check: BasisCheckResult
    basis_policy: BasisPolicyDecision
    state_selection: StateSelection
    artifacts: tuple[str, ...]
    jobs: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    workspace_status: WorkspaceStatus
    defaults: dict[str, Any]
    state_table_sha256: str
    tool_defaults_sha256: str

    def resolved_scf_settings(self) -> dict[str, Any]:
        settings = dict(self.defaults.get("scf_defaults", {}))
        overrides = {
            "conv_tol": self.request.conv_tol,
            "max_cycle": self.request.max_cycle,
            "diis_space": self.request.diis_space,
            "diis_start_cycle": self.request.diis_start_cycle,
            "grid_level": self.request.grid_level,
        }
        settings.update({key: value for key, value in overrides.items() if value is not None})
        settings["verbose"] = self.request.verbose
        return settings

    def resolved_execution_policy(self) -> dict[str, Any]:
        return {
            "resume": self.request.resume,
            "force": self.request.force,
            "continue_on_error": self.request.continue_on_error,
            "allow_pyscf_version_mismatch": self.request.allow_pyscf_version_mismatch,
            "quiet_scf_log": self.request.quiet_scf_log,
            "rad_angular_points": self.request.rad_angular_points,
            "rad_eval_chunk_size": self.request.rad_eval_chunk_size,
        }

    def resolved_config_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "atomref.proatoms.generator_resolved_config.v1",
            "package_version": __version__,
            "run_id": self.run_id,
            "resource_origin": resource_origin(resource_root=self.request.resource_root),
            "state_table_sha256": self.state_table_sha256,
            "tool_defaults_sha256": self.tool_defaults_sha256,
            "method": self.method.as_dict(),
            "method_check": self.method_check.as_dict(),
            "relativity": self.relativity.as_dict(),
            "basis": self.basis.as_dict(),
            "basis_check": self.basis_check.as_dict(),
            "basis_policy": self.basis_policy.as_dict(),
            "state_selection": self.state_selection.summary(),
            "artifacts": list(self.artifacts),
            "workspace": self.workspace_status.as_dict(),
            "scf_defaults": self.defaults.get("scf_defaults", {}),
            "scf_settings": self.resolved_scf_settings(),
            "execution_policy": self.resolved_execution_policy(),
            "profile_grid": self.defaults.get("profile_grid", {}),
            "qa_grid": self.defaults.get("qa_grid", {}),
            "cutoffs_e_bohr3": self.defaults.get("cutoffs_e_bohr3", []),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }

    def plan_dict(self) -> dict[str, Any]:
        workdir = self.request.workdir.expanduser()
        return {
            "schema_version": "atomref.proatoms.generator_plan.v1",
            "run_id": self.run_id,
            "package_version": __version__,
            "resource_origin": resource_origin(resource_root=self.request.resource_root),
            "state_table_sha256": self.state_table_sha256,
            "tool_defaults_sha256": self.tool_defaults_sha256,
            "elements": list(self.state_selection.elements),
            "selected_state_count": len(self.state_selection.states),
            "selected_states": [_state_plan_record(state) for state in self.state_selection.states],
            "method": self.method.as_dict(),
            "method_check": self.method_check.as_dict(),
            "relativity": self.relativity.as_dict(),
            "basis_source": self.basis.as_dict(),
            "basis_check_status": self.basis_check.as_dict(),
            "basis_policy": self.basis_policy.as_dict(),
            "artifacts": list(self.artifacts),
            "scf_settings": self.resolved_scf_settings(),
            "execution_policy": self.resolved_execution_policy(),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "jobs": list(self.jobs),
            "would_write": {
                "workspace_marker": (workdir / "atomref_proatoms_workspace.json").as_posix(),
                "run_config_input": (workdir / "run_config.input.json").as_posix(),
                "run_config_resolved": (workdir / "run_config.resolved.json").as_posix(),
                "plan": (workdir / "plan.json").as_posix(),
                "manifest": (workdir / "manifest.json").as_posix(),
                "failures": (workdir / "failures.csv").as_posix(),
                "basis_dir": (workdir / "basis").as_posix(),
                "scf_dir": (workdir / "scf").as_posix(),
                "profiles_dir": (workdir / "profiles").as_posix(),
                "radii_dir": (workdir / "radii").as_posix(),
                "qa_dir": (workdir / "qa").as_posix(),
                "multiwfn_dir": (workdir / "multiwfn").as_posix(),
            },
        }


def load_tool_defaults(*, resource_root: Path | str | None = None) -> dict[str, Any]:
    """Load packaged generator defaults."""

    text = resource_text(TOOL_DEFAULTS_RESOURCE, resource_root=resource_root)
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("tool defaults resource must contain a mapping")
    return data


def resource_sha256(relpath: str, *, resource_root: Path | str | None = None) -> str:
    """Return a SHA-256 digest of a service resource."""

    return hashlib.sha256(resource_bytes(relpath, resource_root=resource_root)).hexdigest()


def parse_artifacts(
    value: str | list[str] | tuple[str, ...] | None,
    *,
    defaults: dict[str, Any],
) -> tuple[str, ...]:
    """Parse artifact list, expanding ``all`` to the current public artifact set."""

    if value is None:
        raw_items = defaults.get("default_artifacts", ["profiles", "rad"])
    elif isinstance(value, str):
        raw_items = value.split(",")
    else:
        raw_items = list(value)
    result: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        artifact = str(item).strip().lower()
        if not artifact:
            continue
        expanded = ("profiles", "rad", "wfn") if artifact == "all" else (artifact,)
        for expanded_artifact in expanded:
            if expanded_artifact not in ALLOWED_ARTIFACTS:
                raise ValueError(
                    "artifacts must be a comma-separated subset of profiles,rad,wfn,all"
                )
            if expanded_artifact not in seen:
                result.append(expanded_artifact)
                seen.add(expanded_artifact)
    if not result:
        raise ValueError("at least one artifact is required")
    return tuple(result)


def resolve_requested_elements(
    *,
    elements: tuple[str, ...] | list[str] | str | None,
    element_range: str | None,
) -> tuple[str, ...]:
    """Resolve ``--elements`` and optional ``--element-range`` into a unique symbol list."""

    pieces: list[str] = []
    if elements:
        pieces.extend(parse_elements(elements))
    if element_range:
        pieces.extend(parse_element_range(element_range))
    if not pieces:
        raise ValueError("provide --elements and/or --element-range")
    return parse_elements(tuple(pieces))


def _validate_integer_control(name: str, value: int | None, *, minimum: int) -> None:
    if value is None:
        return
    if isinstance(value, bool) or int(value) != value or int(value) < minimum:
        qualifier = "positive" if minimum == 1 else "non-negative"
        raise ValueError(f"--{name} must be a {qualifier} integer")


def validate_generator_request(request: GeneratorRequest) -> None:
    """Validate runtime controls shared by CLI and programmatic planning."""

    if request.conv_tol is not None:
        conv_tol = float(request.conv_tol)
        if not math.isfinite(conv_tol) or conv_tol <= 0:
            raise ValueError("--conv-tol must be a positive finite number")
    _validate_integer_control("max-cycle", request.max_cycle, minimum=1)
    _validate_integer_control("diis-space", request.diis_space, minimum=1)
    _validate_integer_control("diis-start-cycle", request.diis_start_cycle, minimum=0)
    _validate_integer_control("grid-level", request.grid_level, minimum=0)
    _validate_integer_control("verbose", request.verbose, minimum=0)
    _validate_integer_control("rad-eval-chunk-size", request.rad_eval_chunk_size, minimum=1)
    _validate_integer_control("rad-angular-points", request.rad_angular_points, minimum=1)
    if request.rad_angular_points not in {1} and request.rad_angular_points < 4:
        raise ValueError("--rad-angular-points must be 1 or an integer >= 4")


def build_generation_plan(request: GeneratorRequest) -> GeneratorPlan:
    """Resolve a generator request and initialize/check the dry-run workspace."""

    validate_generator_request(request)
    defaults = load_tool_defaults(resource_root=request.resource_root)
    artifacts = parse_artifacts(request.artifacts, defaults=defaults)
    if not request.method:
        raise ValueError("--method is required")
    method = parse_method(request.method)
    method_check = check_method_with_pyscf(method)
    relativity = parse_relativity(
        request.relativity or str(defaults.get("default_relativity", "x2c"))
    )
    basis = parse_basis_spec(
        basis=request.basis,
        basis_file=request.basis_file,
        basis_name=request.basis_name,
    )
    selected_elements = resolve_requested_elements(
        elements=request.elements,
        element_range=request.element_range,
    )
    charges = request.charges
    state_policy = request.state_policy or str(defaults.get("default_state_policy", "neutral"))
    state_selection = select_packaged_states(
        elements=selected_elements,
        policy=state_policy,
        charges=charges,
        resource_root=request.resource_root,
    )
    basis_check = check_basis_source(basis, state_selection.elements)
    basis_policy = apply_basis_policy(
        basis_check,
        BasisPolicy(
            allow_ecp=request.allow_ecp,
            allow_unverified_basis=request.allow_unverified_basis,
            artifact_requires_wfn="wfn" in artifacts,
        ),
    )
    run_id = _run_id(
        method=method,
        relativity=relativity,
        basis=basis,
        state_policy=state_selection.policy,
    )
    workspace_status = require_compatible_workspace(
        request.workdir,
        WorkspaceContext(
            method=method.method_id,
            relativity=relativity.relativity,
            basis_key=basis.basis_key,
            state_policy=state_selection.policy,
        ),
    )
    jobs, job_warnings, job_errors = _build_jobs(
        states=state_selection.states,
        requested_artifacts=artifacts,
        run_id=run_id,
        method=method,
        relativity=relativity,
        basis=basis,
    )
    warnings = [*state_selection.warnings, *basis_policy.warnings, *job_warnings]
    errors = [*basis_policy.errors, *job_errors]
    if method_check.status.startswith("not_performed"):
        warnings.append(method_check.status)
    elif method_check.status == "error":
        errors.append(method_check.message)
    state_table_sha256 = resource_sha256(STATE_TABLE_RESOURCE, resource_root=request.resource_root)
    tool_defaults_sha256 = resource_sha256(
        TOOL_DEFAULTS_RESOURCE,
        resource_root=request.resource_root,
    )
    return GeneratorPlan(
        request=request,
        run_id=run_id,
        method=method,
        method_check=method_check,
        relativity=relativity,
        basis=basis,
        basis_check=basis_check,
        basis_policy=basis_policy,
        state_selection=state_selection,
        artifacts=artifacts,
        jobs=tuple(jobs),
        warnings=tuple(warnings),
        errors=tuple(errors),
        workspace_status=workspace_status,
        defaults=defaults,
        state_table_sha256=state_table_sha256,
        tool_defaults_sha256=tool_defaults_sha256,
    )


def write_dry_run_files(plan: GeneratorPlan) -> dict[str, Path]:
    """Write the dry-run JSON files for a resolved generator plan."""

    workdir = plan.request.workdir.expanduser()
    workdir.mkdir(parents=True, exist_ok=True)
    paths = {
        "run_config_input": workdir / "run_config.input.json",
        "run_config_resolved": workdir / "run_config.resolved.json",
        "plan": workdir / "plan.json",
    }
    _write_json(paths["run_config_input"], plan.request.input_dict())
    _write_json(paths["run_config_resolved"], plan.resolved_config_dict())
    _write_json(paths["plan"], plan.plan_dict())
    return paths


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _state_plan_record(state: AtomState) -> dict[str, Any]:
    return {
        "state_id": state.state_id,
        "symbol": state.symbol,
        "z": state.z,
        "charge": state.charge,
        "electron_count": state.electron_count,
        "multiplicity": state.multiplicity,
        "configuration": state.record.get("configuration"),
        "state_role": state.record.get("state_role"),
        "state_category": state.state_category,
        "state_source": state.record.get("state_source"),
        "physical_status": state.record.get("physical_status"),
    }


def _build_jobs(
    *,
    states: tuple[AtomState, ...],
    requested_artifacts: tuple[str, ...],
    run_id: str,
    method: MethodSpec,
    relativity: RelativitySpec,
    basis: BasisSpec,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    jobs: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    eligible_wfn_count = 0
    for state in states:
        wfn_eligible = state.charge == 0
        if wfn_eligible:
            eligible_wfn_count += 1
        job_artifacts = [
            artifact for artifact in requested_artifacts if artifact != "wfn" or wfn_eligible
        ]
        if "wfn" in requested_artifacts and not wfn_eligible:
            warnings.append(f"WFN export will skip non-neutral state {state.state_id}")
        jobs.append(
            {
                "state_id": state.state_id,
                "symbol": state.symbol,
                "z": state.z,
                "charge": state.charge,
                "electron_count": state.electron_count,
                "multiplicity": state.multiplicity,
                "state_role": state.record.get("state_role"),
                "state_category": state.state_category,
                "method_kind": method.method_kind,
                "xc": method.xc,
                "relativity": relativity.relativity,
                "basis_key": basis.basis_key,
                "requested_artifacts": list(requested_artifacts),
                "artifacts": job_artifacts,
                "wfn_eligible": wfn_eligible,
                "basis_status": None,
                "output_paths": _job_output_paths(state, job_artifacts, run_id),
            }
        )
    if "wfn" in requested_artifacts and requested_artifacts == ("wfn",) and eligible_wfn_count == 0:
        errors.append("WFN-only request selected no neutral WFN-eligible states")
    return jobs, warnings, errors


def _job_output_paths(state: AtomState, artifacts: list[str], run_id: str) -> dict[str, str]:
    paths: dict[str, str] = {}
    if artifacts:
        paths["scf_dir"] = f"scf/{run_id}/{state.state_id}"
    if "profiles" in artifacts:
        paths.update(
            {
                "profiles_csv": "profiles/profiles.csv",
                "radii_csv": "radii/radii.csv",
                "qa_csv": "qa/qa.csv",
            }
        )
    if "rad" in artifacts:
        paths["rad"] = f"multiwfn/rad/{multiwfn_rad_filename(state.symbol, state.charge)}"
    if "wfn" in artifacts:
        paths["wfn"] = f"multiwfn/wfn/{atom_wfn_filename(state.symbol)}"
    return paths


def _run_id(
    *,
    method: MethodSpec,
    relativity: RelativitySpec,
    basis: BasisSpec,
    state_policy: str,
) -> str:
    return "_".join(
        _slug(part)
        for part in (
            method.method_id,
            relativity.relativity,
            basis.source,
            basis.label,
            state_policy,
        )
    )


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", str(value).strip().lower()).strip("-")
    return text or "unknown"
