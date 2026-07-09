"""Generate subcommand implementation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

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


def run_generate(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print(
            "error: execution is not implemented yet; rerun with --dry-run",
            file=sys.stderr,
        )
        return 2

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
        dry_run=True,
    )
    plan = build_generation_plan(request)
    paths = write_dry_run_files(plan)
    _print_summary(plan.plan_dict(), paths)
    return 2 if plan.errors else 0


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
