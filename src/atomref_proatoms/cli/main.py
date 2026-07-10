"""Command-line entry point for atomref-proatoms."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from atomref_proatoms import __version__

from .generate import add_generate_parser, normalize_generate_argv, run_generate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atomref-proatoms",
        description="Generate atomref-proatoms-style spherical proatomic artifacts.",
    )
    parser.add_argument("--version", action="version", version=f"atomref-proatoms {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    generate_parser = subparsers.add_parser(
        "generate",
        help="Plan or generate curated spherical proatomic artifacts.",
        description="Plan or generate curated spherical proatomic artifacts.",
    )
    add_generate_parser(generate_parser)
    generate_parser.set_defaults(func=run_generate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(normalize_generate_argv(argv))
    except SystemExit as exc:
        return int(exc.code)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    try:
        return int(args.func(args))
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
