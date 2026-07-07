"""PROAIM WFN export helpers for PySCF/atomref validation workflows.

The project-native SCF NPZ artifacts and radial profiles are the preferred
internal data paths.  These helpers write WFN files as an interoperability
container for Multiwfn-like workflows that need Gaussian primitive and orbital
coefficient data.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from ..validation.wfn_density import (
    MOSPIN_ALPHA,
    MOSPIN_BETA,
    parse_wfn_basic_counts,
    parse_wfn_mospin,
    parse_wfn_occupations,
    summarize_spin_types,
)

ArrayF = npt.NDArray[np.float64]
MAX_WFN_L = 5


@dataclass(frozen=True)
class WfnOrbitalExport:
    """Occupied orbital arrays prepared for WFN export."""

    coefficients: ArrayF
    occupations: ArrayF
    energies: ArrayF
    labels: list[str]
    spin_types: list[int] | None = None

    @property
    def n_orbitals(self) -> int:
        return int(self.occupations.shape[0])


def atom_wfn_filename(symbol: str) -> str:
    """Return Multiwfn's atomwfn filename convention for an element symbol."""

    if not symbol or not symbol.isalpha():
        raise ValueError(f"Invalid element symbol {symbol!r}")
    normalized = symbol[0].upper() + symbol[1:].lower()
    return f"{normalized}{' ' if len(normalized) == 1 else ''}.wfn"


def _chunked(values: Sequence[int], n_values: int) -> Iterable[list[int]]:
    for i in range(0, len(values), n_values):
        yield list(values[i : i + n_values])


def format_mospin_lines(spin_types: Iterable[int], *, per_line: int = 30) -> list[str]:
    """Format a ``$MOSPIN`` block for atomref spin-orbital WFN exports.

    The writer intentionally emits only explicit alpha/beta labels 1 and 2.  It
    does not use the ``3`` spatial-orbital reconstruction convention for
    fractional/open-shell atom WFNs.
    """

    values = [int(value) for value in spin_types]
    bad = sorted(set(values) - {MOSPIN_ALPHA, MOSPIN_BETA})
    if bad:
        raise ValueError(f"atomref WFN export permits only $MOSPIN values 1 and 2, got {bad}")
    lines = ["$MOSPIN"]
    for chunk in _chunked(values, per_line):
        lines.append("".join(f"{value:2d}" for value in chunk))
    lines.append("$END")
    return lines


def remove_existing_mospin_block(lines: list[str]) -> list[str]:
    """Return WFN lines with any existing ``$MOSPIN`` block removed."""

    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip().upper() == "$MOSPIN":
            i += 1
            while i < len(lines) and lines[i].strip().upper() != "$END":
                i += 1
            if i < len(lines) and lines[i].strip().upper() == "$END":
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return out


def patch_mo_indices_for_multiwfn_spin_fallback(
    lines: list[str], spin_types: Iterable[int] | None
) -> tuple[list[str], dict[str, Any]]:
    """Add a printed MO-index gap at the first beta orbital as a fallback hint.

    The numerical WFN contents are not changed.  Current Multiwfn reads the
    explicit ``$MOSPIN`` block directly, but the label gap preserves compatibility
    with fallback spin-block inference in older/local builds.
    """

    if spin_types is None:
        return lines, {"mo_index_gap_written": False, "mo_index_gap_reason": "no_spin_types"}
    spins = [int(value) for value in spin_types]
    bad = sorted(set(spins) - {MOSPIN_ALPHA, MOSPIN_BETA})
    if bad:
        raise ValueError(f"Cannot patch WFN MO labels for spin values {bad}")
    if not spins or MOSPIN_BETA not in spins:
        return lines, {"mo_index_gap_written": False, "mo_index_gap_reason": "no_beta_orbitals"}
    if spins != sorted(spins):
        raise ValueError("Expected alpha block followed by beta block before patching MO indices")

    n_alpha = sum(spin == MOSPIN_ALPHA for spin in spins)
    beta_seen = 0
    mo_seen = 0
    previous_new: int | None = None
    first_beta_old: int | None = None
    first_beta_new: int | None = None
    gap_ok = False
    patched: list[str] = []
    mo_line_re = re.compile(r"^(\s*MO)\s*([0-9]+)(.*)$")

    for line in lines:
        match = mo_line_re.match(line)
        if match and mo_seen < len(spins):
            old_idx = int(match.group(2))
            spin = spins[mo_seen]
            if spin == MOSPIN_ALPHA:
                new_idx = mo_seen + 1
            else:
                if beta_seen == 0:
                    first_beta_old = old_idx
                    new_idx = n_alpha + 2
                    if previous_new is not None:
                        gap_ok = new_idx > previous_new + 1
                    first_beta_new = new_idx
                else:
                    new_idx = n_alpha + 2 + beta_seen
                beta_seen += 1
            previous_new = new_idx
            patched.append(f"{match.group(1)}{new_idx:5d}{match.group(3)}")
            mo_seen += 1
        else:
            patched.append(line)

    if mo_seen != len(spins):
        raise ValueError(f"Patched {mo_seen} MO labels but expected {len(spins)} labels")
    return patched, {
        "mo_index_gap_written": bool(beta_seen),
        "mo_index_gap_ok_for_multiwfn_fallback": bool(gap_ok),
        "mo_index_gap_n_alpha": int(n_alpha),
        "mo_index_gap_n_beta": int(beta_seen),
        "mo_index_gap_first_beta_old_label": first_beta_old,
        "mo_index_gap_first_beta_new_label": first_beta_new,
    }


def _patch_wfn_title_energy_and_mospin(
    path: Path,
    *,
    title: str,
    total_energy: float | None,
    spin_types: Iterable[int] | None,
    keep_beta_index_gap: bool,
) -> dict[str, Any]:
    lines = path.read_text(encoding="ascii", errors="replace").splitlines()
    if lines and title:
        lines[0] = title[:80]
    if total_energy is not None and np.isfinite(total_energy):
        for i, line in enumerate(lines):
            if "ENERGY =" in line and "VIRIAL" in line:
                lines[i] = (
                    f"SCF      ENERGY = {float(total_energy):20.12f}   "
                    "VIRIAL(-V/T)  =   2.00000000"
                )
                break
    lines = remove_existing_mospin_block(lines)
    mo_gap_info: dict[str, Any] = {
        "mo_index_gap_written": False,
        "mo_index_gap_reason": "not_requested",
    }
    if spin_types is not None:
        spin_values = [int(value) for value in spin_types]
        if keep_beta_index_gap:
            lines, mo_gap_info = patch_mo_indices_for_multiwfn_spin_fallback(lines, spin_values)
        else:
            mo_gap_info = {"mo_index_gap_written": False, "mo_index_gap_reason": "disabled"}
        mospin_lines = format_mospin_lines(spin_values)
        insert_at = len(lines)
        for i, line in enumerate(lines):
            if line.strip().lower() == "[cell]":
                insert_at = i
                break
        lines = lines[:insert_at] + [""] + mospin_lines + lines[insert_at:]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return mo_gap_info


def _spin_pair(value: Any, *, label: str) -> tuple[ArrayF, ArrayF]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return np.asarray(value[0], dtype=float), np.asarray(value[1], dtype=float)
    array = np.asarray(value, dtype=float)
    if array.ndim >= 1 and array.shape[0] == 2:
        return np.asarray(array[0], dtype=float), np.asarray(array[1], dtype=float)
    raise ValueError(f"Expected alpha/beta pair for {label}, got shape {array.shape}")


def _collect_one_spin_channel(
    coefficients: ArrayF,
    occupations: ArrayF,
    energies: ArrayF,
    *,
    spin_label: str,
    spin_type: int,
    occ_tol: float,
) -> tuple[list[ArrayF], list[float], list[float], list[str], list[int]]:
    if coefficients.ndim != 2:
        raise ValueError(f"{spin_label} MO coefficients must be a 2D AO x MO array")
    n_orbitals = min(coefficients.shape[1], occupations.shape[0], energies.shape[0])
    coeffs: list[ArrayF] = []
    occs: list[float] = []
    ens: list[float] = []
    labels: list[str] = []
    spins: list[int] = []
    for i in range(n_orbitals):
        occupation = float(occupations[i])
        if occupation <= occ_tol:
            continue
        if occupation > 1.0 + 5e-8:
            raise ValueError(f"{spin_label} orbital {i + 1} has occupation {occupation:.12g} > 1")
        coeffs.append(np.asarray(coefficients[:, i], dtype=float))
        occs.append(occupation)
        ens.append(float(energies[i]))
        labels.append(f"{spin_label}_{i + 1}_occ{occupation:.7g}")
        spins.append(int(spin_type))
    return coeffs, occs, ens, labels, spins


def collect_unrestricted_spin_orbitals_from_mf(
    mf: Any, *, occ_tol: float = 1e-10
) -> WfnOrbitalExport:
    """Collect occupied alpha spin orbitals followed by occupied beta spin orbitals."""

    coeff_alpha, coeff_beta = _spin_pair(mf.mo_coeff, label="mo_coeff")
    occ_alpha, occ_beta = _spin_pair(mf.mo_occ, label="mo_occ")
    energy_alpha, energy_beta = _spin_pair(mf.mo_energy, label="mo_energy")
    if coeff_alpha.ndim != 2 or coeff_beta.ndim != 2:
        raise ValueError("alpha/beta MO coefficient arrays must be two-dimensional")
    if coeff_alpha.shape[0] != coeff_beta.shape[0]:
        raise ValueError("alpha and beta MO coefficient AO dimensions differ")
    nao = int(mf.mol.nao_nr())
    if coeff_alpha.shape[0] != nao:
        raise ValueError(f"MO AO dimension {coeff_alpha.shape[0]} != mol.nao_nr() {nao}")

    a_coeffs, a_occs, a_energies, a_labels, a_spins = _collect_one_spin_channel(
        coeff_alpha,
        occ_alpha,
        energy_alpha,
        spin_label="alpha",
        spin_type=MOSPIN_ALPHA,
        occ_tol=occ_tol,
    )
    b_coeffs, b_occs, b_energies, b_labels, b_spins = _collect_one_spin_channel(
        coeff_beta,
        occ_beta,
        energy_beta,
        spin_label="beta",
        spin_type=MOSPIN_BETA,
        occ_tol=occ_tol,
    )
    coeffs = a_coeffs + b_coeffs
    if not coeffs:
        raise ValueError("No occupied spin orbitals found")
    return WfnOrbitalExport(
        coefficients=np.column_stack(coeffs),
        occupations=np.asarray(a_occs + b_occs, dtype=float),
        energies=np.asarray(a_energies + b_energies, dtype=float),
        labels=a_labels + b_labels,
        spin_types=a_spins + b_spins,
    )


def collect_restricted_orbitals(
    mo_coeff: ArrayF,
    mo_occ: ArrayF,
    mo_energy: ArrayF,
    *,
    occ_tol: float = 1e-10,
) -> WfnOrbitalExport:
    """Collect occupied restricted/spatial orbitals for ordinary WFN export."""

    coefficients = np.asarray(mo_coeff, dtype=float)
    occupations = np.asarray(mo_occ, dtype=float)
    energies = np.asarray(mo_energy, dtype=float)
    keep = np.where(occupations > occ_tol)[0]
    if keep.size == 0:
        raise ValueError("No occupied restricted orbitals found")
    labels = [f"orb_{int(index) + 1}_occ{float(occupations[index]):.7g}" for index in keep]
    return WfnOrbitalExport(
        coefficients=coefficients[:, keep],
        occupations=occupations[keep],
        energies=energies[keep],
        labels=labels,
        spin_types=None,
    )


def collect_orbitals_from_mean_field(mf: Any, *, occ_tol: float = 1e-10) -> WfnOrbitalExport:
    """Collect occupied orbitals from a PySCF mean-field object for WFN export."""

    coeff = mf.mo_coeff
    coeff_array = np.asarray(coeff, dtype=object if isinstance(coeff, (list, tuple)) else float)
    if isinstance(coeff, (list, tuple)) or (coeff_array.ndim == 3 and coeff_array.shape[0] == 2):
        return collect_unrestricted_spin_orbitals_from_mf(mf, occ_tol=occ_tol)
    return collect_restricted_orbitals(
        np.asarray(mf.mo_coeff, dtype=float),
        np.asarray(mf.mo_occ, dtype=float),
        np.asarray(mf.mo_energy, dtype=float),
        occ_tol=occ_tol,
    )


def max_basis_angular_momentum(mol: Any) -> int:
    """Return the largest PySCF shell angular momentum in a molecule."""

    return int(max((mol.bas_angular(ib) for ib in range(mol.nbas)), default=0))


def strict_atom_wfn_mospin_qa(
    path: Path | str,
    *,
    expected_total: float | None = None,
    expected_alpha: float | None = None,
    expected_beta: float | None = None,
) -> dict[str, Any]:
    """Validate atomref's explicit spin-orbital WFN policy for an atom file."""

    wfn_path = Path(path)
    occupations = parse_wfn_occupations(wfn_path)
    spin_types = parse_wfn_mospin(wfn_path)
    if spin_types is None:
        raise ValueError(f"{wfn_path} has no $MOSPIN block")
    if len(spin_types) != len(occupations):
        raise ValueError(
            f"{wfn_path}: {len(occupations)} occupation records but "
            f"{len(spin_types)} $MOSPIN entries"
        )
    bad_spins = sorted(set(int(spin) for spin in spin_types) - {MOSPIN_ALPHA, MOSPIN_BETA})
    if bad_spins:
        raise ValueError(f"{wfn_path}: unexpected $MOSPIN values {bad_spins}; expected only 1/2")
    if np.any(occupations > 1.0 + 5e-8):
        raise ValueError(f"{wfn_path}: occupation > 1 found; spin-orbital WFN export is invalid")
    summary = summarize_spin_types(occupations, spin_types)
    alpha = summary["alpha_occupation_sum"]
    beta = summary["beta_occupation_sum"]
    total = float(np.sum(occupations))
    if expected_total is not None and abs(total - float(expected_total)) > 1e-5:
        raise ValueError(f"{wfn_path}: total occupation {total} != expected {expected_total}")
    if expected_alpha is not None and abs(float(alpha) - float(expected_alpha)) > 1e-5:
        raise ValueError(f"{wfn_path}: alpha occupation {alpha} != expected {expected_alpha}")
    if expected_beta is not None and abs(float(beta) - float(expected_beta)) > 1e-5:
        raise ValueError(f"{wfn_path}: beta occupation {beta} != expected {expected_beta}")
    n_alpha = int(summary["mospin_alpha_count"])
    alpha_first = all(spin == MOSPIN_ALPHA for spin in spin_types[:n_alpha]) and all(
        spin == MOSPIN_BETA for spin in spin_types[n_alpha:]
    )
    if not alpha_first:
        raise ValueError(f"{wfn_path}: expected alpha orbitals first and beta orbitals second")
    return {
        "strict_atom_mospin_qa_ok": True,
        "strict_mospin_values_only_1_2": True,
        "strict_no_occupation_above_one": bool(np.max(occupations) <= 1.0 + 5e-8),
        "strict_alpha_entries_first": bool(alpha_first),
        **summary,
    }


def write_proaim_wfn(
    path: Path | str,
    mol: Any,
    coefficients: ArrayF,
    occupations: ArrayF,
    energies: ArrayF,
    *,
    title: str,
    total_energy: float | None = None,
    spin_types: list[int] | None = None,
    keep_beta_index_gap: bool = True,
    writer_label: str | None = None,
) -> dict[str, Any]:
    """Write occupied orbitals to a PROAIM WFN file using PySCF's writer.

    ``spin_types`` should be supplied for unrestricted/open-shell atom exports.
    When it is supplied, occupations must already be spin-orbital occupations
    and therefore every occupation must be less than or equal to one.
    """

    out_path = Path(path)
    coeff = np.asarray(coefficients, dtype=float)
    occ = np.asarray(occupations, dtype=float)
    ene = np.asarray(energies, dtype=float)
    if coeff.ndim != 2:
        raise ValueError("coefficients must be a 2D AO x MO array")
    if coeff.shape[1] != occ.shape[0] or occ.shape[0] != ene.shape[0]:
        raise ValueError("coefficients, occupations, and energies have inconsistent shapes")
    if np.any(occ <= 0):
        raise ValueError("WFN export should receive occupied orbitals only")
    if spin_types is not None:
        if len(spin_types) != occ.shape[0]:
            raise ValueError("spin_types length must match number of occupied orbitals")
        if list(spin_types) != sorted(int(value) for value in spin_types):
            raise ValueError("spin_types must list alpha orbitals first, then beta orbitals")
        if np.any(occ > 1.0 + 5e-8):
            raise ValueError("spin-orbital WFN export requires all occupations <= 1")
        bad = sorted(set(int(value) for value in spin_types) - {MOSPIN_ALPHA, MOSPIN_BETA})
        if bad:
            raise ValueError(f"spin-orbital WFN export permits only $MOSPIN 1/2, got {bad}")
    max_l = max_basis_angular_momentum(mol)
    if max_l > MAX_WFN_L:
        raise ValueError(f"basis angular momentum l={max_l} exceeds WFN h-type support")
    if bool(getattr(mol, "cart", False)):
        raise ValueError("PySCF WFN export path expects mol.cart=False spherical-harmonic AOs")
    try:
        from pyscf.tools import wfn_format  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "PySCF is required to write PROAIM WFN files. Install with "
            "`python -m pip install -e .[generator]`."
        ) from exc

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="ascii") as handle:
        wfn_format.write_mo(handle, mol, coeff, ene, occ)
    mo_gap = _patch_wfn_title_energy_and_mospin(
        out_path,
        title=title,
        total_energy=total_energy,
        spin_types=spin_types,
        keep_beta_index_gap=keep_beta_index_gap,
    )
    counts = parse_wfn_basic_counts(out_path)
    spin_summary = summarize_spin_types(occ, spin_types)
    strict_summary = strict_atom_wfn_mospin_qa(out_path) if spin_types is not None else {}
    return {
        "file": str(out_path),
        **counts,
        "occupation_sum": float(np.sum(occ)),
        "has_fractional_occupations": bool(np.any(np.abs(occ - np.round(occ)) > 1e-7)),
        "max_basis_l": max_l,
        "writer": writer_label or "pyscf.tools.wfn_format.write_mo",
        **spin_summary,
        **mo_gap,
        **strict_summary,
    }


def write_mean_field_wfn(
    path: Path | str,
    mf: Any,
    *,
    title: str | None = None,
    total_energy: float | None = None,
    occ_tol: float = 1e-10,
    keep_beta_index_gap: bool = True,
) -> dict[str, Any]:
    """Collect occupied orbitals from a PySCF mean-field object and write WFN."""

    export = collect_orbitals_from_mean_field(mf, occ_tol=occ_tol)
    if total_energy is None:
        total_energy = None if getattr(mf, "e_tot", None) is None else float(mf.e_tot)
    return write_proaim_wfn(
        path,
        mf.mol,
        export.coefficients,
        export.occupations,
        export.energies,
        title=title or "atomref-proatoms WFN export",
        total_energy=total_energy,
        spin_types=export.spin_types,
        keep_beta_index_gap=keep_beta_index_gap,
    )


def write_atomref_spherical_wfn(
    path: Path | str,
    state: Any,
    scf_run_or_mf: Any,
    *,
    title: str | None = None,
    occ_tol: float = 1e-10,
    keep_beta_index_gap: bool = True,
) -> dict[str, Any]:
    """Write an atomref spherical atom/ion PySCF result as a spin-orbital WFN."""

    mf = getattr(scf_run_or_mf, "mf", scf_run_or_mf)
    label = title or f"atomref-proatoms {state.state_id} PROAIM WFN"
    info = write_mean_field_wfn(
        path,
        mf,
        title=label,
        occ_tol=occ_tol,
        keep_beta_index_gap=keep_beta_index_gap,
    )
    expected_alpha = float(sum(float(value) for value in state.alpha_l_counts.values()))
    expected_beta = float(sum(float(value) for value in state.beta_l_counts.values()))
    strict = strict_atom_wfn_mospin_qa(
        path,
        expected_total=float(state.electron_count),
        expected_alpha=expected_alpha,
        expected_beta=expected_beta,
    )
    return {**info, **strict, "state_id": str(state.state_id)}
