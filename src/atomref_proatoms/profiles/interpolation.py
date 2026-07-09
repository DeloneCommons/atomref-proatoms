"""Small radial-density interpolation helpers.

All radii are in bohr and all densities are in electron/bohr^3.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import numpy.typing as npt

ArrayF = npt.NDArray[np.float64]


def _as_1d_float_array(values: Iterable[float], *, label: str) -> ArrayF:
    arr = np.asarray(list(values), dtype=float)
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError(f"{label} must be a non-empty one-dimensional sequence")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{label} contains non-finite values")
    return arr


def _validate_profile_arrays(r_bohr: ArrayF, rho_e_bohr3: ArrayF) -> None:
    if r_bohr.shape != rho_e_bohr3.shape:
        raise ValueError("r_bohr and rho_e_bohr3 must have the same shape")
    if r_bohr.size < 2:
        raise ValueError("at least two profile points are required")
    if np.any(r_bohr <= 0):
        raise ValueError("r_bohr must be positive")
    if np.any(np.diff(r_bohr) <= 0):
        raise ValueError("r_bohr must be strictly increasing")


def load_profile_csv(
    path: Path | str,
    *,
    density_column: str | None = None,
) -> tuple[ArrayF, ArrayF]:
    """Load ``r_bohr`` and one density column from a profile CSV.

    If ``density_column`` is omitted, the file must contain exactly one
    ``rho_e_bohr3__...`` density column.
    """

    csv_path = Path(path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "r_bohr" not in reader.fieldnames:
            raise ValueError(f"profile CSV must contain r_bohr column: {csv_path}")
        density_columns = [name for name in reader.fieldnames if name.startswith("rho_e_bohr3__")]
        selected_column = density_column
        if selected_column is None:
            if len(density_columns) != 1:
                raise ValueError(
                    "density_column must be supplied when the profile CSV contains "
                    f"{len(density_columns)} density columns"
                )
            selected_column = density_columns[0]
        if selected_column not in reader.fieldnames:
            raise ValueError(f"density column {selected_column!r} not found in {csv_path}")
        radii: list[float] = []
        densities: list[float] = []
        for row in reader:
            radii.append(float(row["r_bohr"]))
            densities.append(float(row[selected_column]))
    r_arr = _as_1d_float_array(radii, label="r_bohr")
    rho_arr = _as_1d_float_array(densities, label="rho_e_bohr3")
    _validate_profile_arrays(r_arr, rho_arr)
    return r_arr, rho_arr


def interpolate_density(
    r_bohr: Iterable[float],
    rho_e_bohr3: Iterable[float],
    r_query_bohr: Iterable[float] | float,
    *,
    mode: str = "loglog",
    fill_value: float = 0.0,
) -> ArrayF:
    """Interpolate a radial density profile.

    Parameters use bohr and electron/bohr^3.  ``mode='loglog'`` interpolates
    ``log(rho)`` against ``log(r)`` for strictly positive density profiles.
    When any density is zero or negative, it falls back to linear interpolation
    to avoid invalid logarithms.
    """

    r_arr = _as_1d_float_array(r_bohr, label="r_bohr")
    rho_arr = _as_1d_float_array(rho_e_bohr3, label="rho_e_bohr3")
    _validate_profile_arrays(r_arr, rho_arr)
    scalar = np.isscalar(r_query_bohr)
    query = np.asarray([r_query_bohr] if scalar else list(r_query_bohr), dtype=float)
    if query.ndim != 1:
        raise ValueError("r_query_bohr must be a scalar or one-dimensional sequence")
    if not np.all(np.isfinite(query)):
        raise ValueError("r_query_bohr contains non-finite values")
    mode_value = mode.lower()
    if mode_value not in {"loglog", "linear"}:
        raise ValueError("mode must be 'loglog' or 'linear'")
    if mode_value == "loglog" and np.all(rho_arr > 0) and fill_value > 0:
        out = np.exp(
            np.interp(
                np.log(query),
                np.log(r_arr),
                np.log(rho_arr),
                left=np.log(fill_value),
                right=np.log(fill_value),
            )
        )
    elif mode_value == "loglog" and np.all(rho_arr > 0):
        inside = (query >= r_arr[0]) & (query <= r_arr[-1])
        out = np.full(query.shape, float(fill_value), dtype=float)
        out[inside] = np.exp(
            np.interp(np.log(query[inside]), np.log(r_arr), np.log(rho_arr))
        )
    else:
        out = np.interp(query, r_arr, rho_arr, left=fill_value, right=fill_value)
    return out.astype(float, copy=False)
