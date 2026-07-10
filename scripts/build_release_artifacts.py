#!/usr/bin/env python3
"""Build and validate PyPI distributions from a clean staged source tree."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from smoke_installed_wheel import (
    WHEEL_GLOB,
    _assert_wheel_contents,
    _clean_env,
    _stage_clean_source,
)

SDIST_GLOB = "atomref_proatoms-*.tar.gz"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run(cmd: list[str | os.PathLike[str]], *, cwd: Path, env: dict[str, str]) -> None:
    print(f"[{cwd}] " + " ".join(str(part) for part in cmd))
    subprocess.run([str(part) for part in cmd], cwd=cwd, env=env, check=True)


def _assert_sdist_contents(sdist: Path) -> None:
    with tarfile.open(sdist, "r:gz") as archive:
        names = archive.getnames()
    required_suffixes = (
        "/pyproject.toml",
        "/README.md",
        "/LICENSE.md",
        "/CHANGELOG.md",
        "/CITATION.cff",
        "/src/atomref_proatoms/engines/spherical_scf.py",
    )
    missing = [suffix for suffix in required_suffixes if not any(n.endswith(suffix) for n in names)]
    if missing:
        raise SystemExit("sdist is missing required files: " + ", ".join(missing))
    forbidden = sorted(
        name
        for name in names
        if name.endswith(("spherical_uks.py", ".pyc", ".pyo"))
        or "/__pycache__/" in name
        or "/build/" in name
    )
    if forbidden:
        raise SystemExit("sdist contains forbidden stale/build files: " + ", ".join(forbidden))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_repo_root(),
        help="source repository root; default is inferred from this script",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("dist"),
        help="empty output directory for the wheel and sdist; default: ./dist",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
        help="Python executable providing build and twine",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.expanduser().resolve(strict=True)
    python = args.python.expanduser().resolve(strict=True)
    outdir = args.outdir.expanduser().resolve(strict=False)
    outdir.mkdir(parents=True, exist_ok=True)
    existing = sorted(path.name for path in outdir.iterdir())
    if existing:
        raise SystemExit(
            f"release output directory must be empty: {outdir} contains " + ", ".join(existing)
        )

    env = _clean_env()
    with tempfile.TemporaryDirectory(prefix="atomref-proatoms-release-build-") as temp:
        staged_source = _stage_clean_source(repo_root, Path(temp) / "clean-source")
        _run(
            [python, "-m", "build", "--outdir", outdir],
            cwd=staged_source,
            env=env,
        )

    wheels = sorted(outdir.glob(WHEEL_GLOB))
    sdists = sorted(outdir.glob(SDIST_GLOB))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit(
            f"expected one wheel and one sdist in {outdir}; found "
            f"{len(wheels)} wheel(s) and {len(sdists)} sdist(s)"
        )
    _assert_wheel_contents(wheels[0])
    _assert_sdist_contents(sdists[0])
    _run([python, "-m", "twine", "check", wheels[0], sdists[0]], cwd=repo_root, env=env)
    print(f"OK: validated release artifacts in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
