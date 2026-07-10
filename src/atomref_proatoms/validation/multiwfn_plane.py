"""Small Multiwfn automation and plane-output parsing helpers.

Multiwfn is optional and is never imported as a Python dependency.  These helpers
only locate a local executable, run command streams through stdin, and parse the
plain-text outputs used by the WFN interoperability validation notebook.
"""

from __future__ import annotations

import os
import re
import subprocess
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from .wfn_density import ANGSTROM_TO_BOHR, parse_float_tokens

ArrayF = npt.NDArray[np.float64]


@dataclass(frozen=True)
class MultiwfnPlane:
    """Parsed Multiwfn plane export."""

    path: Path
    x_angstrom: ArrayF
    y_angstrom: ArrayF
    z_angstrom: ArrayF
    values: ArrayF
    plot_x_angstrom: ArrayF | None = None
    plot_y_angstrom: ArrayF | None = None

    @property
    def n_points(self) -> int:
        return int(self.values.shape[0])

    @property
    def points_angstrom(self) -> ArrayF:
        return np.column_stack((self.x_angstrom, self.y_angstrom, self.z_angstrom))

    @property
    def points_bohr(self) -> ArrayF:
        return self.points_angstrom * ANGSTROM_TO_BOHR


@dataclass(frozen=True)
class MultiwfnJobResult:
    """Metadata for a completed local Multiwfn command-stream run."""

    label: str
    returncode: int
    executable: Path
    cwd: Path
    input_file: str
    log: Path
    settings_ini: Path | None = None
    plane_output: Path | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "returncode": self.returncode,
            "executable": str(self.executable),
            "cwd": str(self.cwd),
            "input_file": self.input_file,
            "log": str(self.log),
            "settings_ini": None if self.settings_ini is None else str(self.settings_ini),
            "plane_output": None if self.plane_output is None else str(self.plane_output),
            "commands_passed_via_stdin": True,
            "command_file_written": False,
        }


def is_probable_multiwfn_binary(path: Path) -> bool:
    """Return true if a path looks like a local Multiwfn executable."""

    if not path.is_file():
        return False
    name = path.name.lower()
    if name.endswith((".zip", ".tar", ".gz", ".xz", ".bz2", ".7z", ".txt", ".md", ".ini")):
        return False
    return path.name in {"Multiwfn", "Multiwfn_noGUI"} or name.startswith("multiwfn")


def find_multiwfn_executable(local_data: Path | str = Path("local-data")) -> Path:
    """Find an executable Multiwfn binary under a local-data directory."""

    root = Path(local_data)
    direct = [root / "Multiwfn", root / "Multiwfn_noGUI"]
    recursive: list[Path] = []
    for pattern in ("**/Multiwfn", "**/Multiwfn_noGUI", "**/Multiwfn*"):
        recursive.extend(root.glob(pattern))

    seen: set[Path] = set()
    candidates: list[Path] = []
    for path in [*direct, *recursive]:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if is_probable_multiwfn_binary(path):
            candidates.append(path)

    for path in candidates:
        with suppress(OSError):
            path.chmod(path.stat().st_mode | 0o111)
        if os.access(path, os.X_OK):
            return path.resolve()
    raise FileNotFoundError(
        "Could not find an executable Multiwfn binary under local-data/. "
        "Place the executable as local-data/Multiwfn or under a local-data/Multiwfn*/ directory."
    )


def run_multiwfn_stdin_job(
    *,
    label: str,
    input_file_relative_to_cwd: str,
    commands: list[str],
    cwd: Path | str = Path("local-data"),
    executable: Path | str | None = None,
    settings_ini: Path | str | None = None,
    log_path: Path | str | None = None,
    plane_output_path: Path | str | None = None,
    timeout_seconds: int = 900,
) -> MultiwfnJobResult:
    """Run Multiwfn in silent mode using a command stream passed through stdin."""

    run_cwd = Path(cwd)
    exe = (
        Path(executable).resolve()
        if executable is not None
        else find_multiwfn_executable(run_cwd)
    )
    settings = Path(settings_ini) if settings_ini is not None else run_cwd / "settings.ini"
    settings_for_cmd = settings.resolve() if settings.exists() else None
    cmd = [str(exe), input_file_relative_to_cwd]
    if settings_for_cmd is not None:
        cmd.extend(["-set", str(settings_for_cmd)])
    cmd.append("-silent")

    plane_txt = run_cwd / "plane.txt"
    if plane_txt.exists():
        plane_txt.unlink()

    log = Path(log_path) if log_path is not None else run_cwd / f"multiwfn_{label}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    stdin_text = "\n".join(str(command) for command in commands) + "\n"
    proc = subprocess.run(
        cmd,
        input=stdin_text,
        cwd=run_cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_seconds,
        check=False,
    )
    log.write_text(proc.stdout or "", encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(
            f"Multiwfn job {label!r} failed with return code {proc.returncode}. See {log}"
        )

    plane_output: Path | None = None
    if plane_output_path is not None:
        plane_output = Path(plane_output_path)
        if not plane_txt.exists():
            raise FileNotFoundError(
                f"Multiwfn job {label!r} finished but did not create {plane_txt}. See {log}"
            )
        plane_output.parent.mkdir(parents=True, exist_ok=True)
        if plane_output.exists():
            plane_output.unlink()
        plane_txt.replace(plane_output)
    return MultiwfnJobResult(
        label=label,
        returncode=int(proc.returncode),
        executable=exe,
        cwd=run_cwd,
        input_file=input_file_relative_to_cwd,
        log=log,
        settings_ini=settings_for_cmd,
        plane_output=plane_output,
    )


def read_multiwfn_plane(path: Path | str) -> MultiwfnPlane:
    """Parse Multiwfn ``plane.txt`` style numeric output."""

    plane_path = Path(path)
    x_values: list[float] = []
    y_values: list[float] = []
    z_values: list[float] = []
    plot_x: list[float] = []
    plot_y: list[float] = []
    values: list[float] = []
    saw_plot_columns = False
    for line in plane_path.read_text(encoding="utf-8", errors="replace").splitlines():
        tokens = parse_float_tokens(line)
        if len(tokens) == 4:
            x_values.append(tokens[0])
            y_values.append(tokens[1])
            z_values.append(tokens[2])
            values.append(tokens[3])
        elif len(tokens) >= 6:
            saw_plot_columns = True
            x_values.append(tokens[0])
            y_values.append(tokens[1])
            z_values.append(tokens[2])
            plot_x.append(tokens[3])
            plot_y.append(tokens[4])
            values.append(tokens[-1])
    if not values:
        raise ValueError(f"No numeric plane rows parsed from {plane_path}")
    plot_x_arr = np.asarray(plot_x, dtype=float) if saw_plot_columns else None
    plot_y_arr = np.asarray(plot_y, dtype=float) if saw_plot_columns else None
    return MultiwfnPlane(
        path=plane_path,
        x_angstrom=np.asarray(x_values, dtype=float),
        y_angstrom=np.asarray(y_values, dtype=float),
        z_angstrom=np.asarray(z_values, dtype=float),
        values=np.asarray(values, dtype=float),
        plot_x_angstrom=plot_x_arr,
        plot_y_angstrom=plot_y_arr,
    )


def plane_error_metrics(
    observed: ArrayF, reference: ArrayF, *, prefix: str = "plane"
) -> dict[str, float]:
    """Return compact absolute-error metrics for two plane arrays."""

    obs = np.asarray(observed, dtype=float)
    ref = np.asarray(reference, dtype=float)
    if obs.shape != ref.shape:
        raise ValueError(f"observed/reference shapes differ: {obs.shape} != {ref.shape}")
    error = obs - ref
    rmse = float(np.sqrt(np.mean(error * error)))
    return {
        f"{prefix}_max_abs_error": float(np.max(np.abs(error))),
        f"{prefix}_p95_abs_error": float(np.quantile(np.abs(error), 0.95)),
        f"{prefix}_rmse": rmse,
        f"{prefix}_relative_rmse_vs_max_abs_reference": rmse
        / max(float(np.max(np.abs(ref))), 1e-300),
    }


def parse_multiwfn_point_density_log(path: Path | str) -> dict[str, float]:
    """Parse total, alpha, beta, and spin density from a Multiwfn point log."""

    text = Path(path).read_text(encoding="utf-8", errors="replace")
    number = r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?)"
    patterns = {
        "multiwfn_total_density": rf"Density of all electrons:\s*{number}",
        "multiwfn_alpha_density": rf"Density of Alpha electrons:\s*{number}",
        "multiwfn_beta_density": rf"Density of Beta electrons:\s*{number}",
        "multiwfn_spin_density": rf"Spin density of electrons:\s*{number}",
    }
    out: dict[str, float] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            out[key] = float(match.group(1).replace("D", "E").replace("d", "E"))
    missing = sorted(set(patterns) - set(out))
    if missing:
        raise ValueError(f"Could not parse {missing} from {path}")
    return out
