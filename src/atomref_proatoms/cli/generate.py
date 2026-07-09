"""Generate subcommand implementation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from atomref_proatoms.generator.execution import ExecutionOptions, execute_generation_plan
from atomref_proatoms.generator.planner import (
    DEFAULT_WORKDIR,
    GeneratorRequest,
    build_generation_plan,
    parse_artifacts,
    write_dry_run_files,
)
from atomref_proatoms.generator.state_selection import parse_charges, parse_elements


def add_generate_parser(parser: argparse.ArgumentParser) -> None:
    element_group = parser.add_argument_group("element selection")
    element_group.add_argument("--elements", help="Comma-separated element symbols, e.g. C,N,O.")
    element_group.add_argument("--element-range", help="Closed element range, e.g. H-Ar.")
    element_group.add_argument(
        "--charges",
        help="Optional comma-separated charge filter for selected curated states, e.g. -1,0,+1.",
    )

    method_group = parser.add_argument_group("method and basis")
    method_group.add_argument(
        "--method",
        required=True,
        help="hf or any PySCF-accepted DFT XC string, e.g. PBE0 or 'wB97X-D'.",
    )
    method_group.add_argument(
        "--relativity",
        default="x2c",
        choices=("x2c", "none"),
        help="Scalar-relativity convention. Default: x2c.",
    )
    basis_group = method_group.add_mutually_exclusive_group(required=True)
    basis_group.add_argument(
        "--basis",
        help="Basis source: bare/PySCF name, pyscf:NAME, or bse:NAME.",
    )
    basis_group.add_argument(
        "--basis-file",
        type=Path,
        help="User-supplied NWChem-format basis file.",
    )
    method_group.add_argument(
        "--basis-name",
        help="Name to record for --basis-file; defaults to file stem.",
    )
    method_group.add_argument(
        "--allow-ecp",
        action="store_true",
        help="Allow detected ECP/effective-core basis data.",
    )
    method_group.add_argument(
        "--allow-unverified-basis",
        action="store_true",
        help="Allow WFN planning with basis sources whose full-electron status is unknown.",
    )

    output_group = parser.add_argument_group("output and planning")
    output_group.add_argument(
        "--state-policy",
        default="neutral",
        choices=("neutral", "stockholder"),
        help="Curated state policy. Default: neutral.",
    )
    output_group.add_argument(
        "--artifacts",
        default="profiles,rad",
        help="Comma-separated subset of profiles,rad,wfn,all. Default: profiles,rad.",
    )
    output_group.add_argument(
        "--workdir",
        type=Path,
        default=Path(DEFAULT_WORKDIR),
        help=f"Generator work directory. Default: ./{DEFAULT_WORKDIR}.",
    )
    output_group.add_argument(
        "--resource-root",
        type=Path,
        help="Development override for packaged service resources.",
    )
    output_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve inputs and write run_config/plan JSON without running SCF.",
    )
    output_group.add_argument("--resume", action="store_true", help="Reuse matching SCF cache.")
    output_group.add_argument("--force", action="store_true", help="Overwrite generated outputs.")
    output_group.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue selected states after a generation failure.",
    )
    output_group.add_argument(
        "--allow-pyscf-version-mismatch",
        action="store_true",
        help="Allow execution with a PySCF version different from tool defaults.",
    )
    output_group.add_argument("--conv-tol", type=float, default=None, help="Override SCF conv_tol.")
    output_group.add_argument("--max-cycle", type=int, default=None, help="Override SCF max_cycle.")
    output_group.add_argument(
        "--diis-space",
        type=int,
        default=None,
        help="Override PySCF DIIS space.",
    )
    output_group.add_argument(
        "--diis-start-cycle",
        type=int,
        default=None,
        help="Override the SCF cycle where DIIS acceleration starts.",
    )
    output_group.add_argument(
        "--grid-level",
        type=int,
        default=None,
        help="Override PySCF DFT grid level.",
    )
    output_group.add_argument("--verbose", type=int, default=3, help="PySCF verbosity.")
    output_group.add_argument(
        "--quiet-scf-log",
        action="store_true",
        help="Capture PySCF logs to scf.log without echoing them to stdout.",
    )
    output_group.add_argument(
        "--rad-angular-points",
        type=int,
        default=1,
        help="Angular points for .rad density evaluation. Default: 1 fixed ray.",
    )
    output_group.add_argument(
        "--rad-eval-chunk-size",
        type=int,
        default=8192,
        help="Coordinate block size for .rad AO evaluation.",
    )


def run_generate(args: argparse.Namespace) -> int:
    elements: tuple[str, ...] = ()
    if args.elements:
        elements = parse_elements(args.elements)
    request = GeneratorRequest(
        elements=elements,
        element_range=args.element_range,
        method=args.method,
        relativity=args.relativity,
        basis=args.basis,
        basis_file=args.basis_file,
        basis_name=args.basis_name,
        state_policy=args.state_policy,
        charges=parse_charges(args.charges),
        artifacts=parse_artifacts(
            args.artifacts,
            defaults={"default_artifacts": ["profiles", "rad"]},
        ),
        workdir=args.workdir,
        resource_root=args.resource_root,
        allow_ecp=bool(args.allow_ecp),
        allow_unverified_basis=bool(args.allow_unverified_basis),
        dry_run=bool(args.dry_run),
    )
    plan = build_generation_plan(request)
    if args.dry_run:
        paths = write_dry_run_files(plan)
        _print_summary(plan.plan_dict(), paths)
        return 2 if plan.errors else 0
    if plan.errors:
        for error in plan.errors:
            print(f"error: {error}", file=sys.stderr)
        return 2
    write_dry_run_files(plan)
    options = ExecutionOptions(
        resume=bool(args.resume),
        force=bool(args.force),
        continue_on_error=bool(args.continue_on_error),
        conv_tol=args.conv_tol,
        max_cycle=args.max_cycle,
        diis_space=args.diis_space,
        diis_start_cycle=args.diis_start_cycle,
        grid_level=args.grid_level,
        verbose=int(args.verbose),
        quiet_scf_log=bool(args.quiet_scf_log),
        allow_pyscf_version_mismatch=bool(args.allow_pyscf_version_mismatch),
        rad_angular_points=int(args.rad_angular_points),
        rad_eval_chunk_size=int(args.rad_eval_chunk_size),
    )
    try:
        result = execute_generation_plan(plan, options)
    except (RuntimeError, NotImplementedError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print_execution_summary(result)
    return 1 if result.failed_jobs else 0


def _print_summary(plan: dict[str, Any], paths: dict[str, Path]) -> None:
    errors = plan.get("errors", [])
    warnings = plan.get("warnings", [])
    print("atomref-proatoms generate dry run")
    print(f"  run_id: {plan['run_id']}")
    print(f"  selected states: {plan['selected_state_count']}")
    print(f"  artifacts: {','.join(plan['artifacts'])}")
    print(f"  workdir: {Path(paths['plan']).parent.as_posix()}")
    print(f"  wrote: {paths['run_config_input'].as_posix()}")
    print(f"  wrote: {paths['run_config_resolved'].as_posix()}")
    print(f"  wrote: {paths['plan'].as_posix()}")
    if warnings:
        print(f"  warnings: {len(warnings)}")
    if errors:
        print(f"  errors: {len(errors)}", file=sys.stderr)


def _print_execution_summary(result: Any) -> None:
    print("atomref-proatoms generate execution")
    print(f"  status: {result.status}")
    print(f"  scf computed: {result.computed_scf}")
    print(f"  scf reused: {result.reused_scf}")
    print(f"  failed jobs: {result.failed_jobs}")
    print(f"  manifest: {result.manifest_path.as_posix()}")
    print(f"  failures: {result.failures_path.as_posix()}")
    print(f"  generated files: {len(result.written_files)}")
