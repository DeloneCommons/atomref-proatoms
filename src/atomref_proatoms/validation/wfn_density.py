"""Minimal PROAIM WFN parser and density evaluator for validation workflows.

This module intentionally implements only the WFN functionality needed for the
atomref-proatoms interoperability tests and documentation notebooks.  It is not a
recommended internal storage path for proatomic data; the project-native NPZ and
radial-profile artifacts remain the efficient package data representations.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

ArrayF = npt.NDArray[np.float64]
ArrayI = npt.NDArray[np.int_]

ANGSTROM_TO_BOHR = 1.889726124565062
BOHR_TO_ANGSTROM = 1.0 / ANGSTROM_TO_BOHR

MOSPIN_ALPHA = 1
MOSPIN_BETA = 2
MOSPIN_SPATIAL = 3

# Multiwfn define.f90 type2ix/type2iy/type2iz arrays for primitive type IDs 1..56.
# Index 0 is unused so that the WFN/Multiwfn type number can index directly into
# these arrays.  The arrays cover Cartesian S through H primitives.
_TYPE2IX = np.array(
    [
        0,
        0,
        1,
        0,
        0,
        2,
        0,
        0,
        1,
        1,
        0,
        3,
        0,
        0,
        2,
        2,
        0,
        1,
        1,
        0,
        1,
        0,
        0,
        0,
        0,
        0,
        1,
        1,
        1,
        1,
        2,
        2,
        2,
        3,
        3,
        4,
        0,
        0,
        0,
        0,
        0,
        0,
        1,
        1,
        1,
        1,
        1,
        2,
        2,
        2,
        2,
        3,
        3,
        3,
        4,
        4,
        5,
    ],
    dtype=int,
)
_TYPE2IY = np.array(
    [
        0,
        0,
        0,
        1,
        0,
        0,
        2,
        0,
        1,
        0,
        1,
        0,
        3,
        0,
        1,
        0,
        2,
        2,
        0,
        1,
        1,
        0,
        1,
        2,
        3,
        4,
        0,
        1,
        2,
        3,
        0,
        1,
        2,
        0,
        1,
        0,
        0,
        1,
        2,
        3,
        4,
        5,
        0,
        1,
        2,
        3,
        4,
        0,
        1,
        2,
        3,
        0,
        1,
        2,
        0,
        1,
        0,
    ],
    dtype=int,
)
_TYPE2IZ = np.array(
    [
        0,
        0,
        0,
        0,
        1,
        0,
        0,
        2,
        0,
        1,
        1,
        0,
        0,
        3,
        0,
        1,
        1,
        0,
        2,
        2,
        1,
        4,
        3,
        2,
        1,
        0,
        3,
        2,
        1,
        0,
        2,
        1,
        0,
        1,
        0,
        0,
        5,
        4,
        3,
        2,
        1,
        0,
        4,
        3,
        2,
        1,
        0,
        3,
        2,
        1,
        0,
        2,
        1,
        0,
        1,
        0,
        0,
    ],
    dtype=int,
)

# A WFN file produced by Gaussian >=09 B.01 or Molden2AIM may store g primitives
# in the external PROAIM/Gaussian WFN sequence.  Multiwfn converts external WFN
# IDs 21..35 to the internal sequence below before evaluating real-space
# functions.  H types 36..56 use the same sequence in WFN and Multiwfn, so no
# analogous conversion is needed for h primitives.
_WFN_G_EXTERNAL_TO_MULTIWFN_INTERNAL = np.arange(57, dtype=int)
_WFN_G_EXTERNAL_TO_MULTIWFN_INTERNAL[21:36] = np.array(
    [35, 25, 21, 34, 33, 29, 24, 26, 22, 32, 30, 23, 31, 28, 27],
    dtype=int,
)


@dataclass(frozen=True)
class WfnData:
    """Parsed subset of a PROAIM WFN file sufficient for density validation."""

    path: Path
    title: str
    centers_bohr: ArrayF
    symbols: list[str]
    charges: ArrayF
    primitive_centers: ArrayI
    primitive_types: ArrayI
    exponents: ArrayF
    mo_indices: ArrayI
    occupations: ArrayF
    energies: ArrayF
    coefficients: ArrayF
    spin_types: ArrayI | None = None

    @property
    def n_centers(self) -> int:
        return len(self.symbols)

    @property
    def n_primitives(self) -> int:
        return int(self.exponents.shape[0])

    @property
    def n_mos(self) -> int:
        return int(self.occupations.shape[0])

    @property
    def n_electrons(self) -> float:
        return float(np.sum(self.occupations))

    @property
    def has_mospin(self) -> bool:
        return self.spin_types is not None



def parse_float_tokens(text: str) -> list[float]:
    """Return Fortran/decimal numeric tokens from a line of text."""

    normalized = text.replace("D", "E").replace("d", "E")
    return [
        float(match)
        for match in re.findall(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?", normalized)
    ]


def parse_wfn_basic_counts(path: Path) -> dict[str, int]:
    """Parse WFN header counts without reading all orbital data."""

    lines = Path(path).read_text(encoding="ascii", errors="replace").splitlines()
    header = lines[1] if len(lines) > 1 else ""
    match = re.search(
        r"GAUSSIAN\s+(\d+)\s+MOL ORBITALS\s+(\d+)\s+PRIMITIVES\s+(\d+)\s+NUCLEI",
        header,
    )
    if not match:
        raise ValueError(f"Cannot parse WFN header in {path}")
    nmo, nprim, ncenters = map(int, match.groups())
    return {"n_mos": nmo, "n_primitives": nprim, "n_centers": ncenters}


def parse_wfn_mospin(path: Path) -> list[int] | None:
    """Return the external ``$MOSPIN`` values if a WFN file contains the block."""

    lines = Path(path).read_text(encoding="ascii", errors="replace").splitlines()
    for i, line in enumerate(lines):
        if line.strip().upper() == "$MOSPIN":
            values: list[int] = []
            for row in lines[i + 1 :]:
                if row.strip().upper() == "$END":
                    return values
                values.extend(int(token) for token in row.split())
            return values
    return None


def parse_wfn_occupations(path: Path) -> ArrayF:
    """Return MO occupations in WFN order."""

    text = Path(path).read_text(encoding="ascii", errors="replace")
    normalized = text.replace("D", "E").replace("d", "E")
    values = [
        float(match.group(1))
        for match in re.finditer(
            r"OCC\s+NO\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)",
            normalized,
        )
    ]
    if not values:
        raise ValueError(f"No OCC NO records found in {path}")
    return np.asarray(values, dtype=float)


def _read_repeated_records(
    lines: list[str], start: int, prefix: str, n_values: int, *, cast: type = float
) -> tuple[list[Any], int]:
    values: list[Any] = []
    i = start
    while len(values) < n_values:
        if i >= len(lines):
            raise ValueError(f"Unexpected EOF while reading {prefix}")
        line = lines[i]
        stripped = line.lstrip()
        if not stripped.startswith(prefix):
            raise ValueError(f"Expected {prefix!r} line, got: {line!r}")
        body = stripped[len(prefix) :]
        if cast is int:
            values.extend(int(token) for token in re.findall(r"[+-]?\d+", body))
        else:
            values.extend(parse_float_tokens(body))
        i += 1
    return values[:n_values], i


def _parse_center_line(line: str, path: Path) -> tuple[str, list[float], float]:
    center_re = re.compile(
        r"^\s*([A-Za-z]{1,2})\s+\d+\s+\(CENTRE\s+\d+\)\s+"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[DEde][+-]?\d+)?)\s+"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[DEde][+-]?\d+)?)\s+"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[DEde][+-]?\d+)?)\s+CHARGE\s*=\s*"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[DEde][+-]?\d+)?)"
    )
    match = center_re.search(line)
    if not match:
        raise ValueError(f"Cannot parse WFN center line in {path}: {line!r}")
    symbol = match.group(1).strip()
    xyz = [float(match.group(i).replace("D", "E").replace("d", "E")) for i in range(2, 5)]
    charge = float(match.group(5).replace("D", "E").replace("d", "E"))
    return symbol, xyz, charge


def parse_wfn_file(path: Path | str) -> WfnData:
    """Parse a PROAIM WFN file into arrays used by the validation evaluator."""

    wfn_path = Path(path)
    lines = wfn_path.read_text(encoding="ascii", errors="replace").splitlines()
    if len(lines) < 2:
        raise ValueError(f"Too few lines in {wfn_path}")
    title = lines[0]
    counts = parse_wfn_basic_counts(wfn_path)
    nmo = counts["n_mos"]
    nprim = counts["n_primitives"]
    ncenters = counts["n_centers"]

    symbols: list[str] = []
    centers: list[list[float]] = []
    charges: list[float] = []
    i = 2
    for _ in range(ncenters):
        symbol, center, charge = _parse_center_line(lines[i], wfn_path)
        symbols.append(symbol)
        centers.append(center)
        charges.append(charge)
        i += 1

    primitive_centers_1, i = _read_repeated_records(
        lines, i, "CENTRE ASSIGNMENTS", nprim, cast=int
    )
    primitive_types, i = _read_repeated_records(lines, i, "TYPE ASSIGNMENTS", nprim, cast=int)
    exponents, i = _read_repeated_records(lines, i, "EXPONENTS", nprim, cast=float)
    primitive_types_arr = np.asarray(primitive_types, dtype=int)
    if primitive_types_arr.size == 0:
        raise ValueError(f"No WFN primitives found in {wfn_path}")
    min_type = int(np.min(primitive_types_arr))
    max_type = int(np.max(primitive_types_arr))
    if min_type < 1 or max_type > 56:
        raise ValueError(
            f"Unsupported WFN primitive type range in {wfn_path}: {min_type}..{max_type}"
        )

    mo_indices: list[int] = []
    occupations: list[float] = []
    energies: list[float] = []
    coefficients: list[list[float]] = []
    mo_re = re.compile(
        r"MO\s+(\d+).*?OCC\s+NO\s*=\s*"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[DEde][+-]?\d+)?)"
        r".*?ORB\.\s+ENERGY\s*=\s*"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[DEde][+-]?\d+)?)"
    )
    while i < len(lines) and len(occupations) < nmo:
        if not lines[i].lstrip().startswith("MO"):
            i += 1
            continue
        match = mo_re.search(lines[i])
        if not match:
            raise ValueError(f"Cannot parse MO header in {wfn_path}: {lines[i]!r}")
        mo_indices.append(int(match.group(1)))
        occupations.append(float(match.group(2).replace("D", "E").replace("d", "E")))
        energies.append(float(match.group(3).replace("D", "E").replace("d", "E")))
        i += 1
        values: list[float] = []
        while len(values) < nprim:
            if i >= len(lines):
                raise ValueError(f"Unexpected EOF while reading MO coefficients in {wfn_path}")
            values.extend(parse_float_tokens(lines[i]))
            i += 1
        coefficients.append(values[:nprim])

    if len(occupations) != nmo:
        raise ValueError(f"Expected {nmo} MOs in {wfn_path}, parsed {len(occupations)}")

    spin_values = parse_wfn_mospin(wfn_path)
    spin_arr: ArrayI | None = None
    if spin_values is not None:
        if len(spin_values) != nmo:
            raise ValueError(
                f"{wfn_path}: $MOSPIN has {len(spin_values)} entries but WFN header has {nmo} MOs"
            )
        allowed_spins = {MOSPIN_ALPHA, MOSPIN_BETA, MOSPIN_SPATIAL}
        bad_spins = sorted(set(int(value) for value in spin_values) - allowed_spins)
        if bad_spins:
            raise ValueError(f"{wfn_path}: unsupported $MOSPIN values {bad_spins}")
        spin_arr = np.asarray(spin_values, dtype=int)

    primitive_centers = np.asarray(primitive_centers_1, dtype=int) - 1
    if np.any(primitive_centers < 0) or np.any(primitive_centers >= ncenters):
        raise ValueError(f"Primitive center assignment out of range in {wfn_path}")

    return WfnData(
        path=wfn_path,
        title=title,
        centers_bohr=np.asarray(centers, dtype=float),
        symbols=symbols,
        charges=np.asarray(charges, dtype=float),
        primitive_centers=primitive_centers,
        primitive_types=primitive_types_arr,
        exponents=np.asarray(exponents, dtype=float),
        mo_indices=np.asarray(mo_indices, dtype=int),
        occupations=np.asarray(occupations, dtype=float),
        energies=np.asarray(energies, dtype=float),
        coefficients=np.asarray(coefficients, dtype=float),
        spin_types=spin_arr,
    )


# Backward-friendly alias matching the validation notebook helper name.
parse_wfn = parse_wfn_file


def multiwfn_internal_primitive_types_from_wfn_external(types: ArrayI | Iterable[int]) -> ArrayI:
    """Map saved WFN primitive type IDs to the sequence Multiwfn evaluates."""

    mapped = np.asarray(
        list(types) if not isinstance(types, np.ndarray) else types, dtype=int
    ).copy()
    if mapped.size == 0:
        return mapped
    if int(np.min(mapped)) < 1 or int(np.max(mapped)) > 56:
        raise ValueError(
            "Unsupported WFN primitive type range: "
            f"{int(np.min(mapped))}..{int(np.max(mapped))}"
        )
    g_mask = (mapped >= 21) & (mapped <= 35)
    mapped[g_mask] = _WFN_G_EXTERNAL_TO_MULTIWFN_INTERNAL[mapped[g_mask]]
    return mapped


def primitive_type_powers(types: ArrayI | Iterable[int], *, wfn_external: bool = True) -> ArrayI:
    """Return Cartesian powers ``(ix, iy, iz)`` for WFN primitive type IDs."""

    type_arr = np.asarray(list(types) if not isinstance(types, np.ndarray) else types, dtype=int)
    if wfn_external:
        type_arr = multiwfn_internal_primitive_types_from_wfn_external(type_arr)
    if type_arr.size == 0:
        return np.empty((0, 3), dtype=int)
    if int(np.min(type_arr)) < 1 or int(np.max(type_arr)) > 56:
        raise ValueError(
            "Unsupported primitive type range: "
            f"{int(np.min(type_arr))}..{int(np.max(type_arr))}"
        )
    return np.column_stack((_TYPE2IX[type_arr], _TYPE2IY[type_arr], _TYPE2IZ[type_arr])).astype(int)


def primitive_values(
    wfn: WfnData, points_bohr: ArrayF, *, wfn_external_types: bool = True
) -> ArrayF:
    """Evaluate Cartesian primitive values at points in bohr."""

    points = np.asarray(points_bohr, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("points_bohr must have shape (n_points, 3)")
    centers = wfn.centers_bohr[wfn.primitive_centers]
    delta = points[:, None, :] - centers[None, :, :]
    r2 = np.sum(delta * delta, axis=2)
    values = np.exp(-wfn.exponents[None, :] * r2)
    powers = primitive_type_powers(wfn.primitive_types, wfn_external=wfn_external_types)
    for axis in range(3):
        axis_powers = powers[:, axis]
        nonzero = axis_powers > 0
        if np.any(nonzero):
            values[:, nonzero] *= delta[:, nonzero, axis] ** axis_powers[nonzero][None, :]
    return values


def evaluate_mo_values(
    wfn: WfnData, points_bohr: ArrayF, *, chunk_size: int = 20_000
) -> Iterable[tuple[slice, ArrayF]]:
    """Yield MO values at points in chunks."""

    points = np.asarray(points_bohr, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("points_bohr must have shape (n_points, 3)")
    for start in range(0, points.shape[0], chunk_size):
        stop = min(start + chunk_size, points.shape[0])
        prim = primitive_values(wfn, points[start:stop])
        yield slice(start, stop), prim @ wfn.coefficients.T


def evaluate_density(wfn: WfnData, points_bohr: ArrayF, *, chunk_size: int = 20_000) -> ArrayF:
    """Evaluate the total electron density from WFN orbitals."""

    points = np.asarray(points_bohr, dtype=float)
    out = np.empty(points.shape[0], dtype=float)
    for chunk_slice, psi in evaluate_mo_values(wfn, points, chunk_size=chunk_size):
        out[chunk_slice] = np.sum((psi * psi) * wfn.occupations[None, :], axis=1)
    return out


# Alias used in the exploratory validation notebook.
eval_wfn_density = evaluate_density


def _effective_spin_types(wfn: WfnData) -> ArrayI:
    if wfn.spin_types is None:
        return np.full(wfn.n_mos, MOSPIN_SPATIAL, dtype=int)
    return np.asarray(wfn.spin_types, dtype=int)


def evaluate_alpha_beta_density(
    wfn: WfnData, points_bohr: ArrayF, *, chunk_size: int = 20_000
) -> tuple[ArrayF, ArrayF]:
    """Evaluate alpha and beta densities using ``$MOSPIN`` when available.

    If the WFN file has no ``$MOSPIN`` block, each spatial-orbital occupation is
    divided equally between alpha and beta channels.
    """

    points = np.asarray(points_bohr, dtype=float)
    alpha = np.zeros(points.shape[0], dtype=float)
    beta = np.zeros(points.shape[0], dtype=float)
    spin_types = _effective_spin_types(wfn)
    spatial_mask = (spin_types == MOSPIN_SPATIAL) | (spin_types == 0)
    alpha_mask = spin_types == MOSPIN_ALPHA
    beta_mask = spin_types == MOSPIN_BETA
    for chunk_slice, psi in evaluate_mo_values(wfn, points, chunk_size=chunk_size):
        psi2 = psi * psi
        if np.any(alpha_mask):
            alpha[chunk_slice] += np.sum(
                psi2[:, alpha_mask] * wfn.occupations[alpha_mask][None, :], axis=1
            )
        if np.any(beta_mask):
            beta[chunk_slice] += np.sum(
                psi2[:, beta_mask] * wfn.occupations[beta_mask][None, :], axis=1
            )
        if np.any(spatial_mask):
            half_density = 0.5 * np.sum(
                psi2[:, spatial_mask] * wfn.occupations[spatial_mask][None, :], axis=1
            )
            alpha[chunk_slice] += half_density
            beta[chunk_slice] += half_density
    return alpha, beta


# Alias used in the exploratory validation notebook.
eval_wfn_alpha_beta_density = evaluate_alpha_beta_density


def evaluate_spin_density(wfn: WfnData, points_bohr: ArrayF, *, chunk_size: int = 20_000) -> ArrayF:
    """Evaluate alpha-minus-beta spin density."""

    alpha, beta = evaluate_alpha_beta_density(wfn, points_bohr, chunk_size=chunk_size)
    return alpha - beta


def translate_one_center_wfn(
    template: WfnData, center_bohr: ArrayF, label: str | Path = "translated"
) -> WfnData:
    """Return a one-center WFN template translated to a new center."""

    center = np.asarray(center_bohr, dtype=float)
    if template.n_centers != 1:
        raise ValueError("Expected a one-center atom WFN template")
    if center.shape != (3,):
        raise ValueError("center_bohr must have shape (3,)")
    return replace(template, path=Path(label), centers_bohr=center.reshape(1, 3))


# Alias used in the exploratory validation notebook.
translated_one_center_wfn = translate_one_center_wfn


def promolecule_density_from_templates(
    molecule_wfn: WfnData,
    atom_templates: dict[str, WfnData],
    points_bohr: ArrayF,
    *,
    chunk_size: int = 20_000,
) -> ArrayF:
    """Evaluate a promolecular density by translating one-center WFN templates."""

    atom_terms = []
    for atom_index, (symbol, center) in enumerate(
        zip(molecule_wfn.symbols, molecule_wfn.centers_bohr, strict=True)
    ):
        try:
            template = atom_templates[symbol]
        except KeyError as exc:
            raise KeyError(f"No atom WFN template supplied for symbol {symbol!r}") from exc
        translated = translate_one_center_wfn(template, center, label=f"{symbol}{atom_index + 1}")
        atom_terms.append(evaluate_density(translated, points_bohr, chunk_size=chunk_size))
    if not atom_terms:
        return np.zeros(np.asarray(points_bohr).shape[0], dtype=float)
    return np.sum(atom_terms, axis=0)


def deformation_density_from_templates(
    molecule_wfn: WfnData,
    atom_templates: dict[str, WfnData],
    points_bohr: ArrayF,
    *,
    chunk_size: int = 20_000,
) -> ArrayF:
    """Evaluate molecular minus promolecular density from WFN files."""

    rho_molecule = evaluate_density(molecule_wfn, points_bohr, chunk_size=chunk_size)
    rho_promolecule = promolecule_density_from_templates(
        molecule_wfn, atom_templates, points_bohr, chunk_size=chunk_size
    )
    return rho_molecule - rho_promolecule


def summarize_spin_types(
    occupations: ArrayF | Iterable[float], spin_types: ArrayI | Iterable[int] | None
) -> dict[str, Any]:
    """Summarize WFN spin labels and alpha/beta occupation totals."""

    occ = np.asarray(
        list(occupations) if not isinstance(occupations, np.ndarray) else occupations,
        dtype=float,
    )
    rec: dict[str, Any] = {
        "has_mospin": spin_types is not None,
        "max_occupation": float(np.max(occ)) if occ.size else 0.0,
    }
    if spin_types is None:
        rec.update(
            {
                "mospin_alpha_count": 0,
                "mospin_beta_count": 0,
                "mospin_spatial_count": 0,
                "alpha_occupation_sum": None,
                "beta_occupation_sum": None,
                "spin_population_alpha_minus_beta": None,
            }
        )
        return rec
    spins = np.asarray(
        list(spin_types) if not isinstance(spin_types, np.ndarray) else spin_types,
        dtype=int,
    )
    spatial_mask = (spins == MOSPIN_SPATIAL) | (spins == 0)
    rec.update(
        {
            "mospin_alpha_count": int(np.sum(spins == MOSPIN_ALPHA)),
            "mospin_beta_count": int(np.sum(spins == MOSPIN_BETA)),
            "mospin_spatial_count": int(np.sum(spatial_mask)),
            "mospin_length_mismatch": bool(spins.shape[0] != occ.shape[0]),
        }
    )
    if spins.shape[0] != occ.shape[0]:
        rec.update(
            {
                "alpha_occupation_sum": None,
                "beta_occupation_sum": None,
                "spin_population_alpha_minus_beta": None,
            }
        )
        return rec
    alpha_occ = float(np.sum(occ[spins == MOSPIN_ALPHA]) + 0.5 * np.sum(occ[spatial_mask]))
    beta_occ = float(np.sum(occ[spins == MOSPIN_BETA]) + 0.5 * np.sum(occ[spatial_mask]))
    rec.update(
        {
            "alpha_occupation_sum": alpha_occ,
            "beta_occupation_sum": beta_occ,
            "spin_population_alpha_minus_beta": alpha_occ - beta_occ,
        }
    )
    return rec
