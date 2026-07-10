#!/usr/bin/env python3
"""Smoke-test atomref-proatoms from an installed wheel, isolated from source imports.

The goal is intentionally narrower than the normal pytest suite: build a wheel,
install that wheel into a fresh virtual environment, and run the public CLI from a
separate working directory without importing the checkout's ``src`` package. This
catches packaging/resource mistakes that source-tree tests can hide. The working
directory itself may be below the repository, for example under ``local-data/``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PROJECT_NAME = "atomref-proatoms"
WHEEL_GLOB = "atomref_proatoms-*.whl"
STAGED_FILES = (
    "pyproject.toml",
    "MANIFEST.in",
    "README.md",
    "LICENSE.md",
    "AI_NOTE.md",
    "CHANGELOG.md",
    "CITATION.cff",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "PYTHONPATH",
        "ATOMREF_PROATOMS_ROOT",
        "ATOMREF_PROATOMS_RESOURCE_ROOT",
    ):
        env.pop(key, None)
    env.setdefault("PYTHONNOUSERSITE", "1")
    return env


def _run(
    cmd: list[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    printable = " ".join(str(part) for part in cmd)
    if cwd is not None:
        print(f"[{cwd}] {printable}")
    else:
        print(printable)
    return subprocess.run(
        [str(part) for part in cmd],
        cwd=cwd,
        env=env,
        check=True,
        text=True,
    )


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_script(venv_dir: Path, name: str) -> Path:
    script_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    candidates = [script_dir / name]
    if os.name == "nt":
        candidates.insert(0, script_dir / f"{name}.exe")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _stage_clean_source(repo_root: Path, stage_root: Path) -> Path:
    """Copy only declared build inputs into a fresh source tree."""
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True)
    for relative in STAGED_FILES:
        source = repo_root / relative
        if not source.is_file():
            raise SystemExit(f"required build input is missing: {source}")
        shutil.copy2(source, stage_root / relative)
    source_tree = repo_root / "src"
    if not source_tree.is_dir():
        raise SystemExit(f"package source directory is missing: {source_tree}")
    shutil.copytree(
        source_tree,
        stage_root / "src",
        ignore=shutil.ignore_patterns("*.egg-info", "__pycache__", "*.pyc", "*.pyo"),
    )
    return stage_root


def _assert_wheel_contents(wheel: Path) -> None:
    """Reject incomplete wheels and common source-tree contamination."""
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    required = {
        "atomref_proatoms/engines/spherical_scf.py",
        "atomref_proatoms/resources/states/atom_states_v2.json",
        "atomref_proatoms/resources/presets/tool_defaults.yaml",
        "atomref_proatoms/resources/grids/multiwfn_atmrad_grid.csv",
        "atomref_proatoms/resources/schemas/manifest.schema.json",
        "atomref_proatoms/resources/schemas/run_config.schema.json",
    }
    missing = sorted(required - names)
    if missing:
        raise SystemExit("wheel is missing required files: " + ", ".join(missing))
    forbidden = sorted(
        name
        for name in names
        if name.endswith(("spherical_uks.py", ".pyc", ".pyo"))
        or "/__pycache__/" in name
        or ".egg-info/" in name
    )
    if forbidden:
        raise SystemExit("wheel contains forbidden stale/build files: " + ", ".join(forbidden))


def _build_wheel(
    *,
    python: Path,
    repo_root: Path,
    wheelhouse: Path,
    no_build_isolation: bool,
    env: dict[str, str],
) -> Path:
    wheelhouse.mkdir(parents=True, exist_ok=True)
    staged_source = _stage_clean_source(repo_root, wheelhouse.parent / "clean-source")
    cmd: list[str | os.PathLike[str]] = [
        str(python),
        "-m",
        "pip",
        "wheel",
        "--no-deps",
        "--wheel-dir",
        wheelhouse,
    ]
    if no_build_isolation:
        cmd.append("--no-build-isolation")
    cmd.append(staged_source)
    _run(cmd, cwd=staged_source, env=env)
    wheels = sorted(wheelhouse.glob(WHEEL_GLOB))
    if not wheels:
        raise SystemExit(f"no wheel matching {WHEEL_GLOB!r} was built in {wheelhouse}")
    if len(wheels) > 1:
        names = ", ".join(path.name for path in wheels)
        raise SystemExit(f"expected exactly one built wheel, found: {names}")
    return wheels[0]


def _install_wheel(
    *,
    venv_python: Path,
    wheel: Path,
    no_deps: bool,
    env: dict[str, str],
) -> None:
    cmd: list[str | os.PathLike[str]] = [venv_python, "-m", "pip", "install"]
    if no_deps:
        cmd.append("--no-deps")
    cmd.append(wheel)
    _run(cmd, env=env)


def _install_generator_extra(
    *,
    venv_python: Path,
    wheel: Path,
    env: dict[str, str],
) -> None:
    # pip accepts extras on local wheel paths using the /path/package.whl[extra] form.
    _run([venv_python, "-m", "pip", "install", f"{wheel}[generator]"], env=env)


def _assert_installed_package(
    *,
    venv_python: Path,
    repo_root: Path,
    run_dir: Path,
    env: dict[str, str],
) -> None:
    code = r"""
from __future__ import annotations

import json
from pathlib import Path

import atomref_proatoms
from atomref_proatoms.dataio.resources import resource_text

module_path = Path(atomref_proatoms.__file__).resolve()
repo_root = Path(__import__('os').environ['ATOMREF_PROATOMS_SMOKE_REPO']).resolve()
source_package = (repo_root / 'src' / 'atomref_proatoms').resolve()
if module_path == source_package or source_package in module_path.parents:
    raise SystemExit(f'atomref_proatoms imported from source tree: {module_path}')

states = json.loads(resource_text('states/atom_states_v2.json'))
if not isinstance(states, list) or len(states) < 100:
    raise SystemExit('packaged atom state resource did not load correctly')
print(f'imported atomref_proatoms {atomref_proatoms.__version__} from {module_path}')
print(f'loaded {len(states)} packaged atom states')
"""
    scoped_env = env.copy()
    scoped_env["ATOMREF_PROATOMS_SMOKE_REPO"] = repo_root.as_posix()
    _run([venv_python, "-c", code], cwd=run_dir, env=scoped_env)


def _assert_dry_run(
    *,
    cli: Path,
    run_dir: Path,
    env: dict[str, str],
) -> None:
    workdir = run_dir / "smoke-plan"
    _run(
        [
            cli,
            "generate",
            "--elements",
            "C",
            "--method",
            "PBE0",
            "--relativity",
            "x2c",
            "--basis",
            "def2-SVP",
            "--state-policy",
            "neutral",
            "--artifacts",
            "profiles,rad",
            "--workdir",
            workdir,
            "--dry-run",
        ],
        cwd=run_dir,
        env=env,
    )
    expected = [
        workdir / "atomref_proatoms_workspace.json",
        workdir / "run_config.input.json",
        workdir / "run_config.resolved.json",
        workdir / "plan.json",
    ]
    missing = [path for path in expected if not path.is_file()]
    if missing:
        raise SystemExit("dry-run did not write expected files: " + ", ".join(map(str, missing)))
    plan = json.loads((workdir / "plan.json").read_text(encoding="utf-8"))
    if plan.get("selected_state_count") != 1:
        raise SystemExit(
            f"unexpected dry-run selected_state_count: {plan.get('selected_state_count')!r}"
        )
    if not plan.get("jobs"):
        raise SystemExit("dry-run plan did not contain jobs")


def _assert_generator_execution(
    *,
    cli: Path,
    run_dir: Path,
    env: dict[str, str],
) -> None:
    workdir = run_dir / "tiny-h-generation"
    _run(
        [
            cli,
            "generate",
            "--elements",
            "H",
            "--method",
            "PBE0",
            "--relativity",
            "none",
            "--basis",
            "sto-3g",
            "--state-policy",
            "neutral",
            "--artifacts",
            "profiles,rad",
            "--workdir",
            workdir,
            "--allow-pyscf-version-mismatch",
            "--force",
        ],
        cwd=run_dir,
        env=env,
    )
    expected = [
        workdir / "manifest.json",
        workdir / "profiles" / "profiles.csv",
        workdir / "radii" / "radii.csv",
        workdir / "qa" / "qa.csv",
        workdir / "multiwfn" / "rad" / "H_0.rad",
    ]
    missing = [path for path in expected if not path.is_file()]
    if missing:
        raise SystemExit(
            "generator execution did not write expected files: " + ", ".join(map(str, missing))
        )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stage clean atomref-proatoms build inputs, build a wheel, install it into a "
            "fresh virtual environment, and run import/CLI/dry-run checks without "
            "source-tree imports."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_repo_root(),
        help="source repository root; default is inferred from this script",
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=None,
        help="working directory for wheelhouse, venv, and run directory; default is a temp dir",
    )
    parser.add_argument(
        "--wheel",
        type=Path,
        default=None,
        help="use an already-built wheel instead of building one from --repo-root",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
        help="Python executable used to build the wheel and create the smoke venv",
    )
    parser.add_argument(
        "--no-build-isolation",
        action="store_true",
        help="pass --no-build-isolation to pip wheel; useful for offline/local smoke runs",
    )
    parser.add_argument(
        "--no-deps",
        action="store_true",
        help=(
            "install the built wheel without resolving runtime dependencies; useful with "
            "--system-site-packages or a pre-provisioned environment"
        ),
    )
    parser.add_argument(
        "--system-site-packages",
        action="store_true",
        help="create the smoke virtual environment with access to system site packages",
    )
    parser.add_argument(
        "--with-generator-execution",
        action="store_true",
        help=(
            "also install the generator extra and run a tiny H profiles/.rad "
            "generation smoke test"
        ),
    )
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="keep the smoke work directory after a successful run",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.expanduser().resolve(strict=True)
    env = _clean_env()

    temp_context: tempfile.TemporaryDirectory[str] | None = None
    if args.work_root is None:
        temp_context = tempfile.TemporaryDirectory(prefix="atomref-proatoms-wheel-smoke-")
        work_root = Path(temp_context.name)
    else:
        work_root = args.work_root.expanduser().resolve(strict=False)
        work_root.mkdir(parents=True, exist_ok=True)

    try:
        wheelhouse = work_root / "wheelhouse"
        venv_dir = work_root / "venv"
        run_dir = work_root / "run-isolated-from-source"
        run_dir.mkdir(parents=True, exist_ok=True)

        wheel = (
            args.wheel.expanduser().resolve(strict=True)
            if args.wheel is not None
            else _build_wheel(
                python=args.python.expanduser().resolve(strict=True),
                repo_root=repo_root,
                wheelhouse=wheelhouse,
                no_build_isolation=args.no_build_isolation,
                env=env,
            )
        )
        print(f"Built/selected wheel: {wheel}")
        _assert_wheel_contents(wheel)

        if venv_dir.exists():
            shutil.rmtree(venv_dir)
        venv.EnvBuilder(
            with_pip=True,
            system_site_packages=args.system_site_packages,
        ).create(venv_dir)
        venv_python = _venv_python(venv_dir)
        cli = _venv_script(venv_dir, PROJECT_NAME)

        _install_wheel(venv_python=venv_python, wheel=wheel, no_deps=args.no_deps, env=env)
        _assert_installed_package(
            venv_python=venv_python,
            repo_root=repo_root,
            run_dir=run_dir,
            env=env,
        )
        _run([cli, "--help"], cwd=run_dir, env=env)
        _run([cli, "--version"], cwd=run_dir, env=env)
        _run([cli, "generate", "--help"], cwd=run_dir, env=env)
        _assert_dry_run(cli=cli, run_dir=run_dir, env=env)

        if args.with_generator_execution:
            if args.no_deps:
                raise SystemExit("--with-generator-execution cannot be combined with --no-deps")
            _install_generator_extra(venv_python=venv_python, wheel=wheel, env=env)
            _assert_generator_execution(cli=cli, run_dir=run_dir, env=env)

        print("OK: installed-wheel smoke test passed")
        print(f"work root: {work_root}")
        return 0
    finally:
        if temp_context is not None and not args.keep_workdir:
            temp_context.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
