"""Multiwfn ``.rad`` density-only export helpers.

The project-native radial profile CSV/metadata files remain the canonical compact
Python-side data layer.  Multiwfn ``.rad`` files are written as a density-only
interoperability product for Hirshfeld-I/stockholder-like workflows.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from ..profiles.artifacts import profile_density_column

ArrayF = npt.NDArray[np.float64]

RAD_EXPORT_SCHEMA_VERSION = "atomref.proatoms.multiwfn_rad.v1"

# Radius grid copied from the longest file in the Multiwfn atmrad exemplar set
# supplied with the project (Ba-1.rad, first line declares 176 rows).  The values
# are in bohr and are written with the same decimal precision as the exemplar
# files.  The grid is intentionally fixed so generated .rad files are stable and
# do not depend on a local Multiwfn installation.
MULTIWFN_ATMRAD_GRID_BOHR = np.asarray(
    [
        0.000061075260,
        0.000244330883,
        0.000549856433,
        0.000977801287,
        0.001528374788,
        0.002201846466,
        0.002998546315,
        0.003918865143,
        0.004963254972,
        0.006132229517,
        0.007426364720,
        0.008846299360,
        0.010392735719,
        0.012066440329,
        0.013868244780,
        0.015799046605,
        0.017859810234,
        0.020051568030,
        0.022375421393,
        0.024832541952,
        0.027424172828,
        0.030151629995,
        0.033016303708,
        0.036019660040,
        0.039163242499,
        0.042448673736,
        0.045877657369,
        0.049451979889,
        0.053173512681,
        0.057044214160,
        0.061066132006,
        0.065241405533,
        0.069572268168,
        0.074061050073,
        0.078710180880,
        0.083522192589,
        0.088499722592,
        0.093645516858,
        0.098962433279,
        0.104453445171,
        0.110121644962,
        0.115970248051,
        0.122002596863,
        0.128222165100,
        0.134632562205,
        0.141237538039,
        0.148040987794,
        0.155046957146,
        0.162259647661,
        0.169683422466,
        0.177322812205,
        0.185182521286,
        0.193267434443,
        0.201582623623,
        0.210133355215,
        0.218925097650,
        0.227963529377,
        0.237254547246,
        0.246804275323,
        0.256619074146,
        0.266705550468,
        0.277070567496,
        0.287721255663,
        0.298665023973,
        0.309909571926,
        0.321462902090,
        0.333333333333,
        0.345529514769,
        0.358060440449,
        0.370935464858,
        0.384164319257,
        0.397757128917,
        0.411724431318,
        0.426077195359,
        0.440826841646,
        0.455985263933,
        0.471564851785,
        0.487578514544,
        0.504039706682,
        0.520962454634,
        0.538361385218,
        0.556251755729,
        0.574649485843,
        0.593571191436,
        0.613034220471,
        0.633056691076,
        0.653657531977,
        0.674856525463,
        0.696674353043,
        0.719132644006,
        0.742254027097,
        0.766062185522,
        0.790581915550,
        0.815839188963,
        0.841861219669,
        0.868676534765,
        0.896315050428,
        0.924808152980,
        0.954188785560,
        0.984491540829,
        1.015752760209,
        1.048010640173,
        1.081305346171,
        1.115679134834,
        1.151176485123,
        1.187844239213,
        1.225731753915,
        1.264891063572,
        1.305377055412,
        1.347247658475,
        1.390564047307,
        1.435390861789,
        1.481796444531,
        1.529853097500,
        1.579637359650,
        1.631230307553,
        1.684717881238,
        1.740191237679,
        1.797747134638,
        1.857488347896,
        1.919524125213,
        1.983970680770,
        2.050951734275,
        2.120599099390,
        2.193053326713,
        2.268464407173,
        2.346992542413,
        2.428808989542,
        2.514096988589,
        2.603052782034,
        2.695886737016,
        2.792824582205,
        2.894108772933,
        3.000000000000,
        3.110778859705,
        3.226747705102,
        3.348232701300,
        3.475586110920,
        3.609188839646,
        3.749453276258,
        3.896826466726,
        4.051793668048,
        4.214882334640,
        4.386666598533,
        4.567772314521,
        4.758882753174,
        4.960745038575,
        5.174177444232,
        5.400077680426,
        5.639432330035,
        5.893327618371,
        6.162961737023,
        6.449658983346,
        6.754886027865,
        7.080270683611,
        7.427623627024,
        7.798963613022,
        8.196546841737,
        8.622901276901,
        9.080866893590,
        9.573643055680,
        10.104844503823,
        10.678567789992,
        11.299470447062,
        11.972865761768,
        12.704836767182,
        13.502374041661,
        14.373543170651,
        15.327689399669,
        16.375689226576,
        17.530261652746,
        18.806355825878,
        20.221637278194,
        21.797102496932,
        23.557862047967,
        25.534147230985,
    ],
    dtype=float,
)


@dataclass(frozen=True)
class RadData:
    """Parsed Multiwfn ``.rad`` file contents."""

    path: Path
    r_bohr: ArrayF
    rho_e_bohr3: ArrayF

    @property
    def n_points(self) -> int:
        return int(self.r_bohr.shape[0])


def multiwfn_rad_filename(symbol: str, charge: int) -> str:
    """Return the Multiwfn ``atmrad`` filename convention for one atom/ion."""

    if not symbol or not symbol.isalpha():
        raise ValueError(f"Invalid element symbol {symbol!r}")
    normalized = symbol[0].upper() + symbol[1:].lower()
    if int(charge) == 0:
        suffix = "_0"
    elif int(charge) > 0:
        suffix = f"+{int(charge)}"
    else:
        suffix = f"{int(charge)}"
    return f"{normalized}{suffix}.rad"


def _as_float_array(values: Sequence[float] | Iterable[float], *, label: str) -> ArrayF:
    arr = np.asarray(list(values) if not isinstance(values, np.ndarray) else values, dtype=float)
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError(f"{label} must be a non-empty one-dimensional sequence")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{label} contains non-finite values")
    return arr


def interpolate_density_to_rad_grid(
    source_r_bohr: Sequence[float] | Iterable[float],
    source_rho_e_bohr3: Sequence[float] | Iterable[float],
    *,
    target_r_bohr: Sequence[float] | Iterable[float] = MULTIWFN_ATMRAD_GRID_BOHR,
) -> ArrayF:
    """Interpolate a released profile density to the fixed Multiwfn atmrad grid."""

    source_r = _as_float_array(source_r_bohr, label="source_r_bohr")
    source_rho = _as_float_array(source_rho_e_bohr3, label="source_rho_e_bohr3")
    target_r = _as_float_array(target_r_bohr, label="target_r_bohr")
    if source_r.shape != source_rho.shape:
        raise ValueError("source radius and density arrays have different lengths")
    if np.any(source_r <= 0) or np.any(target_r <= 0):
        raise ValueError("radial grids must be strictly positive")
    if np.any(np.diff(source_r) <= 0):
        raise ValueError("source_r_bohr must be strictly increasing")
    if np.any(np.diff(target_r) <= 0):
        raise ValueError("target_r_bohr must be strictly increasing")
    if target_r[0] < source_r[0] or target_r[-1] > source_r[-1]:
        raise ValueError(
            "target Multiwfn .rad grid is outside the source profile range: "
            f"target {target_r[0]:.6g}..{target_r[-1]:.6g}, "
            f"source {source_r[0]:.6g}..{source_r[-1]:.6g} bohr"
        )
    if np.any(source_rho < 0):
        raise ValueError("source densities must be non-negative")
    positive = source_rho > 0.0
    if np.all(positive):
        out = np.exp(np.interp(np.log(target_r), np.log(source_r), np.log(source_rho)))
    else:
        out = np.interp(target_r, source_r, source_rho)
    return np.maximum(out, 0.0)


def write_multiwfn_rad_file(
    path: Path | str,
    r_bohr: Sequence[float] | Iterable[float],
    rho_e_bohr3: Sequence[float] | Iterable[float],
) -> dict[str, Any]:
    """Write a Multiwfn ``.rad`` file and return compact validation metadata."""

    out_path = Path(path)
    r_values = _as_float_array(r_bohr, label="r_bohr")
    rho_values = _as_float_array(rho_e_bohr3, label="rho_e_bohr3")
    if r_values.shape != rho_values.shape:
        raise ValueError("r_bohr and rho_e_bohr3 have different lengths")
    if np.any(r_values <= 0) or np.any(np.diff(r_values) <= 0):
        raise ValueError("r_bohr must be strictly positive and increasing")
    if np.any(rho_values < 0):
        raise ValueError("rho_e_bohr3 must be non-negative")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="ascii", newline="") as handle:
        handle.write(f"{r_values.size:12d}\n")
        for r_value, rho_value in zip(r_values, rho_values, strict=True):
            handle.write(f"{r_value:20.12f} {rho_value:17.10E}\n")
    return {
        "schema_version": RAD_EXPORT_SCHEMA_VERSION,
        "file": str(out_path),
        "n_points": int(r_values.size),
        "r_min_bohr": float(r_values[0]),
        "r_max_bohr": float(r_values[-1]),
        "min_density_e_bohr3": float(np.min(rho_values)),
        "max_density_e_bohr3": float(np.max(rho_values)),
        "integral_electrons_trapezoid": radial_density_integral(r_values, rho_values),
    }


def read_multiwfn_rad_file(path: Path | str) -> RadData:
    """Parse a Multiwfn ``.rad`` file."""

    rad_path = Path(path)
    lines = rad_path.read_text(encoding="ascii", errors="replace").splitlines()
    if not lines:
        raise ValueError(f"empty .rad file: {rad_path}")
    try:
        n_points = int(lines[0].strip())
    except ValueError as exc:
        raise ValueError(f"cannot parse .rad point count in {rad_path}: {lines[0]!r}") from exc
    rows: list[tuple[float, float]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 2:
            raise ValueError(f"cannot parse .rad row in {rad_path}: {line!r}")
        r_text = parts[0].replace("D", "E").replace("d", "E")
        rho_text = parts[1].replace("D", "E").replace("d", "E")
        rows.append((float(r_text), float(rho_text)))
    if len(rows) != n_points:
        raise ValueError(f"{rad_path}: header says {n_points} points but parsed {len(rows)}")
    if not rows:
        return RadData(rad_path, np.empty(0, dtype=float), np.empty(0, dtype=float))
    r_values = np.asarray([row[0] for row in rows], dtype=float)
    rho_values = np.asarray([row[1] for row in rows], dtype=float)
    if np.any(r_values <= 0) or np.any(np.diff(r_values) <= 0):
        raise ValueError(f"{rad_path}: radius grid must be strictly positive and increasing")
    if np.any(rho_values < 0) or not np.all(np.isfinite(rho_values)):
        raise ValueError(f"{rad_path}: densities must be finite and non-negative")
    return RadData(rad_path, r_values, rho_values)


def radial_density_integral(r_bohr: Sequence[float], rho_e_bohr3: Sequence[float]) -> float:
    """Return trapezoid integral of ``4πr²ρ(r)`` over a finite radial grid."""

    r_values = _as_float_array(r_bohr, label="r_bohr")
    rho_values = _as_float_array(rho_e_bohr3, label="rho_e_bohr3")
    if r_values.shape != rho_values.shape:
        raise ValueError("r_bohr and rho_e_bohr3 have different lengths")
    if r_values.size == 0:
        return 0.0
    # Include the origin as a finite endpoint.  The first .rad point is very close
    # to zero, so this only stabilizes the near-nuclear trapezoid interval.
    r_int = np.concatenate(([0.0], r_values))
    rho_int = np.concatenate(([rho_values[0]], rho_values))
    distribution = 4.0 * math.pi * r_int * r_int * rho_int
    return float(np.trapezoid(distribution, r_int))


def _tail_integral_beyond(
    source_r_bohr: Sequence[float], source_rho_e_bohr3: Sequence[float], r_cut_bohr: float
) -> float:
    source_r = _as_float_array(source_r_bohr, label="source_r_bohr")
    source_rho = _as_float_array(source_rho_e_bohr3, label="source_rho_e_bohr3")
    mask = source_r >= float(r_cut_bohr)
    if not np.any(mask):
        return 0.0
    r_tail = source_r[mask]
    rho_tail = source_rho[mask]
    if r_tail[0] > r_cut_bohr and r_cut_bohr > source_r[0]:
        rho_cut = interpolate_density_to_rad_grid(
            source_r, source_rho, target_r_bohr=[r_cut_bohr]
        )[0]
        r_tail = np.concatenate(([float(r_cut_bohr)], r_tail))
        rho_tail = np.concatenate(([float(rho_cut)], rho_tail))
    distribution = 4.0 * math.pi * r_tail * r_tail * rho_tail
    return float(np.trapezoid(distribution, r_tail))


def write_profile_state_rad(
    path: Path | str,
    *,
    profile_r_bohr: Sequence[float],
    profile_rho_e_bohr3: Sequence[float],
    rad_grid_bohr: Sequence[float] = MULTIWFN_ATMRAD_GRID_BOHR,
) -> dict[str, Any]:
    """Interpolate one profile state to the Multiwfn grid and write ``.rad``."""

    rad_r = _as_float_array(rad_grid_bohr, label="rad_grid_bohr")
    rad_rho = interpolate_density_to_rad_grid(
        profile_r_bohr, profile_rho_e_bohr3, target_r_bohr=rad_r
    )
    info = write_multiwfn_rad_file(path, rad_r, rad_rho)
    profile_on_rad_integral = radial_density_integral(rad_r, rad_rho)
    tail_beyond = _tail_integral_beyond(profile_r_bohr, profile_rho_e_bohr3, float(rad_r[-1]))
    return {
        **info,
        "source": "profile_interpolation",
        "rad_grid_source": "Multiwfn atmrad exemplar grid",
        "profile_interpolated_integral_electrons_trapezoid": profile_on_rad_integral,
        "source_profile_tail_beyond_rad_grid_electrons_trapezoid": tail_beyond,
    }


def profile_state_density_from_wide_rows(
    rows: Sequence[Mapping[str, str]], state_id: str
) -> tuple[ArrayF, ArrayF]:
    """Return ``r`` and ``rho`` arrays for one state from parsed profile CSV rows."""

    column = profile_density_column(state_id)
    if not rows:
        raise ValueError("profile CSV rows are empty")
    if column not in rows[0]:
        raise KeyError(f"profile column {column!r} not found")
    r_values = np.asarray([float(row["r_bohr"]) for row in rows], dtype=float)
    rho_values = np.asarray([float(row[column]) for row in rows], dtype=float)
    return r_values, rho_values


def read_wide_profiles_csv(path: Path | str) -> list[dict[str, str]]:
    """Read a released wide profile CSV into row dictionaries."""

    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
