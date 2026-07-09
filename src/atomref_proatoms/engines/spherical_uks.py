"""Spherical fractional-occupation PySCF helpers.

PySCF is kept as a lazy dependency: import-time tests and metadata checks can run
without PySCF, while generator entry points import PySCF only when a real SCF
object is requested.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any

import numpy as np
import numpy.typing as npt

ArrayF = npt.NDArray[np.float64]

FRACTIONAL_OCCUPATION_SPIN_SQUARE_MESSAGE = (
    "<S^2> is not defined by the one-particle density matrix of a "
    "fractional-occupation spherical ensemble"
)


_L_BY_LETTER = {"s": 0, "p": 1, "d": 2, "f": 3, "g": 4}
_SHELL_RE = re.compile(r"(\d+)([spdfg])(\d+(?:\.\d+)?)")
_CORE_CONFIGURATION_BY_SYMBOL = {
    "He": "1s2",
    "Ne": "1s2 2s2 2p6",
    "Ar": "[Ne] 3s2 3p6",
    "Kr": "[Ar] 3d10 4s2 4p6",
    "Cd": "[Kr] 4d10 5s2",
    "Xe": "[Cd] 5p6",
    "Hg": "[Xe] 4f14 5d10 6s2",
    "Rn": "[Hg] 6p6",
}


def expand_configuration_shells(configuration: str) -> tuple[tuple[int, int, float], ...]:
    """Expand a compact atomic configuration into ``(n, l, occupation)`` shells.

    The state table uses compact bracket notation such as ``[Ar] 3d8 4s2`` and,
    for some heavy p-block atoms, closed-shell labels such as ``[Cd]`` or
    ``[Hg]``. This helper expands the bracketed prefix and preserves the written
    shell order, which is the safest information available in the compact state
    record.
    """

    value = str(configuration).strip()
    if not value:
        raise ValueError("configuration must be non-empty")

    shells: list[tuple[int, int, float]] = []
    if value.startswith("["):
        close = value.find("]")
        if close < 0:
            raise ValueError(f"invalid configuration prefix in {configuration!r}")
        core_symbol = value[1:close]
        try:
            core_configuration = _CORE_CONFIGURATION_BY_SYMBOL[core_symbol]
        except KeyError as exc:
            raise ValueError(f"unsupported core configuration label [{core_symbol}]") from exc
        shells.extend(expand_configuration_shells(core_configuration))
        value = value[close + 1 :].strip()

    for principal, l_label, occupation_text in _SHELL_RE.findall(value):
        occupation = float(occupation_text)
        if occupation <= 0:
            raise ValueError(f"non-positive shell occupation in {configuration!r}")
        shells.append((int(principal), _L_BY_LETTER[l_label], occupation))

    if not shells:
        raise ValueError(f"no shell occupations found in {configuration!r}")
    return tuple(shells)


def configuration_l_counts_after_core_removal(
    configuration: str,
    core_electrons: int | float,
) -> dict[int, float]:
    """Return aggregate valence ``l`` counts after removing an ECP core.

    ``core_electrons`` is removed from the beginning of the expanded compact
    configuration. If a source uses an unusual partial-shell ECP, the remainder
    is still represented as an effective-valence occupation because the compact
    state record does not store radial-shell-resolved spin occupations.
    """

    remaining_core = float(core_electrons)
    if remaining_core < -1e-8:
        raise ValueError("core_electrons must be non-negative")
    valence_by_l: dict[int, float] = {}
    for _principal, l_value, shell_occupation in expand_configuration_shells(configuration):
        remove = min(shell_occupation, remaining_core)
        remaining_core -= remove
        valence_occupation = shell_occupation - remove
        if valence_occupation > 1e-10:
            valence_by_l[l_value] = valence_by_l.get(l_value, 0.0) + valence_occupation
    if remaining_core > 1e-8:
        raise ValueError(
            f"ECP core electron count {core_electrons:g} exceeds electrons in {configuration!r}"
        )
    return {l_value: value for l_value, value in sorted(valence_by_l.items()) if value > 1e-10}


def effective_l_counts_for_mol(state: Any, mol: Any) -> tuple[dict[int, float], dict[int, float]]:
    """Return alpha/beta ``l`` counts compatible with a built PySCF molecule.

    All-electron molecules use the curated state counts unchanged. For an ECP
    molecule, PySCF's target electron count is the explicit/effective-valence
    count, while the curated state record stores the full atomic electron count.
    The helper removes the effective core from the compact configuration and then
    keeps the curated spin imbalance in each angular-momentum manifold.
    """

    alpha_full = {int(key): float(value) for key, value in state.alpha_l_counts.items()}
    beta_full = {int(key): float(value) for key, value in state.beta_l_counts.items()}
    mol_nelectron = float(mol.nelectron)
    core_electrons = float(state.electron_count) - mol_nelectron
    rounded_core = round(core_electrons)
    if abs(core_electrons - rounded_core) > 1e-8:
        raise ValueError(
            f"non-integral effective core electron count {core_electrons:.12g} for {state.state_id}"
        )
    core_electrons = float(rounded_core)
    if core_electrons < -1e-8:
        raise ValueError(
            f"molecule electron count {mol_nelectron:g} exceeds state electron count "
            f"{state.electron_count:g} for {state.state_id}"
        )
    if core_electrons <= 1e-8:
        return alpha_full, beta_full

    valence_totals = configuration_l_counts_after_core_removal(
        str(state.record["configuration"]),
        core_electrons,
    )
    spin_delta = {
        l_value: alpha_full.get(l_value, 0.0) - beta_full.get(l_value, 0.0)
        for l_value in set(alpha_full) | set(beta_full)
    }
    alpha: dict[int, float] = {}
    beta: dict[int, float] = {}
    for l_value, total in valence_totals.items():
        delta = spin_delta.get(l_value, 0.0)
        if abs(delta) > total + 1e-8:
            raise ValueError(
                f"cannot preserve spin imbalance {delta:g} for l={l_value}; "
                f"only {total:g} valence electrons remain after ECP core removal"
            )
        alpha_l = 0.5 * (total + delta)
        beta_l = 0.5 * (total - delta)
        if alpha_l < -1e-8 or beta_l < -1e-8:
            raise ValueError(f"negative valence occupation derived for l={l_value}")
        if alpha_l > 1e-10:
            alpha[l_value] = alpha_l
        if beta_l > 1e-10:
            beta[l_value] = beta_l

    nelec = sum(alpha.values()) + sum(beta.values())
    spin = sum(alpha.values()) - sum(beta.values())
    if abs(nelec - mol_nelectron) > 1e-8:
        raise ValueError(
            f"derived ECP occupation sum {nelec:g} != PySCF target {mol_nelectron:g}"
        )
    mol_spin = float(mol.spin)
    if abs(spin - mol_spin) > 1e-8:
        raise ValueError(f"derived ECP spin {spin:g} != PySCF target spin {mol_spin:g}")
    return dict(sorted(alpha.items())), dict(sorted(beta.items()))


def validate_angular_block_size(l_value: int, block_size: int) -> None:
    """Validate that a pure/spherical AO block has complete magnetic components."""

    if l_value < 0:
        raise ValueError("l_value must be non-negative")
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    degeneracy = 2 * l_value + 1
    if block_size % degeneracy != 0:
        raise ValueError(
            f"angular-momentum block size {block_size} is not divisible by 2*l+1={degeneracy}"
        )


def require_spherical_basis(mol: object) -> None:
    """Require a PySCF molecule-like object with pure/spherical basis functions."""

    cart = getattr(mol, "cart", None)
    if cart is not False:
        raise ValueError("production spherical proatoms require mol.cart is False")


def ao_angular_momenta(mol: Any) -> npt.NDArray[np.int_]:
    """Return angular momentum ``l`` for each AO in PySCF's AO ordering.

    The function uses only the small PySCF ``Mole`` interface needed for tests and
    generator code, so unit tests can exercise it with fake molecule objects.
    """

    require_spherical_basis(mol)
    nao = int(mol.nao_nr())
    ao_l = np.empty(nao, dtype=int)
    ao_loc = mol.ao_loc_nr()
    nbas = int(mol.nbas)
    for ibas in range(nbas):
        p0, p1 = int(ao_loc[ibas]), int(ao_loc[ibas + 1])
        ao_l[p0:p1] = int(mol.bas_angular(ibas))
    return ao_l


def angular_block_indices(mol: Any) -> list[tuple[int, npt.NDArray[np.int_]]]:
    """Return AO indices grouped by angular momentum in ascending ``l`` order."""

    ao_l = ao_angular_momenta(mol)
    if ao_l.size == 0:
        raise ValueError("molecule has no AOs")
    blocks: list[tuple[int, npt.NDArray[np.int_]]] = []
    for l_value in range(int(ao_l.max()) + 1):
        idx = np.where(ao_l == l_value)[0]
        if idx.size == 0:
            continue
        validate_angular_block_size(l_value, int(idx.size))
        blocks.append((l_value, idx))
    return blocks


def validate_spherical_ao_layout(mol: Any) -> None:
    """Validate pure/spherical AO layout for angular-momentum block averaging."""

    angular_block_indices(mol)


def _as_l_count_mapping(counts: Mapping[int | str, float] | None) -> dict[int, float]:
    return {int(l_value): float(value) for l_value, value in (counts or {}).items()}


def _fractional_occupation_populations(mo_occ: Any) -> tuple[float, float] | None:
    """Return spin populations when a two-spin occupation array is fractional."""

    if mo_occ is None:
        return None
    occupations = np.asarray(mo_occ, dtype=float)
    if occupations.ndim != 2 or occupations.shape[0] != 2:
        return None
    if np.all(np.isclose(occupations, np.rint(occupations), rtol=0.0, atol=1.0e-12)):
        return None
    return float(occupations[0].sum()), float(occupations[1].sum())


def _finalize_fractional_occupation_scf(mf: Any, *, base_finalize: Any, logger: Any) -> Any:
    """Finalize without PySCF's determinant-only ``spin_square`` diagnostic."""

    base_finalize(mf)
    populations = _fractional_occupation_populations(mf.mo_occ)
    if populations is None:
        return mf
    n_alpha, n_beta = populations
    nominal_multiplicity = abs(n_alpha - n_beta) + 1.0
    logger.note(
        mf,
        "fractional-occupation spherical ensemble: <S^2> is undefined from the 1-RDM; "
        "Nalpha = %.8g  Nbeta = %.8g  nominal 2S+1 = %.8g",
        n_alpha,
        n_beta,
        nominal_multiplicity,
    )
    return mf


def occupation_from_l_counts(
    mol: Any,
    l_counts: Mapping[int | str, float],
    max_occ_per_spatial_orbital: float,
) -> ArrayF:
    """Create an MO occupation vector from total alpha/beta counts per ``l``.

    Occupations are filled radially within each angular-momentum block and repeated
    equally over all ``m`` components.  For one spin channel,
    ``max_occ_per_spatial_orbital`` should be 1.0.
    """

    if max_occ_per_spatial_orbital <= 0:
        raise ValueError("max_occ_per_spatial_orbital must be positive")

    counts = _as_l_count_mapping(l_counts)
    occ_blocks: list[ArrayF] = []
    seen_l: set[int] = set()

    for l_value, idx in angular_block_indices(mol):
        seen_l.add(l_value)
        degeneracy = 2 * l_value + 1
        nrad = int(idx.size) // degeneracy
        ne_l = counts.get(l_value, 0.0)

        shell_capacity = max_occ_per_spatial_orbital * degeneracy
        max_capacity = shell_capacity * nrad
        if ne_l < -1e-10 or ne_l > max_capacity + 1e-10:
            raise ValueError(
                f"invalid occupation for l={l_value}: requested {ne_l:g} electrons, "
                f"capacity is {max_capacity:g}"
            )

        occ_rad = np.zeros(nrad, dtype=float)
        n_full = int(np.floor((ne_l + 1e-12) / shell_capacity))
        remainder = ne_l - n_full * shell_capacity

        if n_full > 0:
            occ_rad[:n_full] = max_occ_per_spatial_orbital
        if remainder > 1e-10:
            if n_full >= nrad:
                raise ValueError(f"no radial shell left for fractional l={l_value} occupation")
            occ_rad[n_full] = remainder / degeneracy

        occ_blocks.append(np.repeat(occ_rad, degeneracy))

    unknown_l = sorted(set(counts) - seen_l)
    if unknown_l:
        raise ValueError(
            f"occupation counts reference angular momenta absent from basis: {unknown_l}"
        )
    if not occ_blocks:
        raise ValueError("no angular-momentum blocks found")
    return np.hstack(occ_blocks)


def spherical_block_eigh(mf: Any, fock: Sequence[Sequence[float]], ovlp: Sequence[Sequence[float]]):
    """Solve angular-momentum-averaged radial eigenproblems.

    The input Fock/overlap matrices are projected onto each angular-momentum block,
    averaged over magnetic components, diagonalized with ``mf._eigh``, and expanded
    back over all ``m`` components with repeated radial eigenvalues.
    """

    mol = mf.mol
    blocks = angular_block_indices(mol)
    fock_arr = np.asarray(fock)
    ovlp_arr = np.asarray(ovlp)
    if fock_arr.ndim != 2 or ovlp_arr.ndim != 2:
        raise ValueError("spherical_block_eigh expects two-dimensional Fock/overlap matrices")
    if fock_arr.shape != ovlp_arr.shape:
        raise ValueError("Fock and overlap matrices must have identical shape")
    nao = int(mol.nao_nr())
    if fock_arr.shape != (nao, nao):
        raise ValueError(f"matrix shape {fock_arr.shape} does not match nao={nao}")

    mo_energy_blocks: list[npt.NDArray[Any]] = []
    mo_coeff_blocks: list[npt.NDArray[Any]] = []

    for l_value, idx in blocks:
        degeneracy = 2 * l_value + 1
        nrad = int(idx.size) // degeneracy

        f_l = fock_arr[np.ix_(idx, idx)].reshape(nrad, degeneracy, nrad, degeneracy)
        s_l = ovlp_arr[np.ix_(idx, idx)].reshape(nrad, degeneracy, nrad, degeneracy)
        f_rad = np.einsum("p m q m -> p q", f_l) / degeneracy
        s_rad = np.einsum("p m q m -> p q", s_l) / degeneracy

        e_rad, c_rad = mf._eigh(f_rad, s_rad)

        mo_l = np.zeros((nao, nrad, degeneracy), dtype=np.asarray(c_rad).dtype)
        for m_value in range(degeneracy):
            mo_l[idx[m_value::degeneracy], :, m_value] = c_rad

        mo_energy_blocks.append(np.repeat(e_rad, degeneracy))
        mo_coeff_blocks.append(mo_l.reshape(nao, nrad * degeneracy))

    return np.hstack(mo_energy_blocks), np.hstack(mo_coeff_blocks)


@lru_cache(maxsize=1)
def get_atom_spherical_uks_class():  # pragma: no cover - requires optional PySCF
    """Return the PySCF UKS subclass implementing spherical occupations."""

    try:
        from pyscf.dft import uks as pyscf_uks  # type: ignore[import-not-found]
        from pyscf.lib import logger as pyscf_logger  # type: ignore[import-not-found]
        from pyscf.scf import hf as pyscf_hf  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError(
            "PySCF is required for spherical UKS generation. Install with "
            "`python -m pip install \"atomref-proatoms[generator]\"` or from source "
            "with `python -m pip install -e \".[generator]\"`."
        ) from exc

    class AtomSphAverageUKS(pyscf_uks.UKS):  # type: ignore[misc]
        """PySCF UKS subclass with l-block radial eigensolvers and fixed occupations."""

        def __init__(
            self,
            mol: Any,
            xc: str = "PBE0",
            alpha_l_counts: Mapping[int | str, float] | None = None,
            beta_l_counts: Mapping[int | str, float] | None = None,
        ) -> None:
            super().__init__(mol, xc=xc)
            self._keys = self._keys.union({"alpha_l_counts", "beta_l_counts"})
            self.alpha_l_counts = _as_l_count_mapping(alpha_l_counts)
            self.beta_l_counts = _as_l_count_mapping(beta_l_counts)
            self.init_guess = "1e"
            self.init_guess_breaksym = 0

        def eig(self, fock: Any, ovlp: Any, overwrite: bool = False, x: Any = None):
            del overwrite, x
            fock_arr = np.asarray(fock)
            if fock_arr.ndim == 2:
                energy, coeff = spherical_block_eigh(self, fock_arr, ovlp)
                return np.stack([energy, energy]), np.stack([coeff, coeff])
            energy_a, coeff_a = spherical_block_eigh(self, fock_arr[0], ovlp)
            energy_b, coeff_b = spherical_block_eigh(self, fock_arr[1], ovlp)
            return np.stack([energy_a, energy_b]), np.stack([coeff_a, coeff_b])

        def get_occ(self, mo_energy: Any = None, mo_coeff: Any = None):
            del mo_energy, mo_coeff
            occ_a = occupation_from_l_counts(self.mol, self.alpha_l_counts, 1.0)
            occ_b = occupation_from_l_counts(self.mol, self.beta_l_counts, 1.0)

            target_alpha, target_beta = self.mol.nelec
            if abs(float(occ_a.sum()) - target_alpha) > 1e-8:
                raise ValueError(
                    f"alpha occupation sum {occ_a.sum()} != target alpha {target_alpha}"
                )
            if abs(float(occ_b.sum()) - target_beta) > 1e-8:
                raise ValueError(f"beta occupation sum {occ_b.sum()} != target beta {target_beta}")

            return np.stack([occ_a, occ_b])

        def get_grad(self, mo_coeff: Any, mo_occ: Any, fock: Any = None):
            del mo_coeff, mo_occ, fock
            return np.zeros(0)

        def spin_square(self, mo_coeff: Any = None, s: Any = None):
            if mo_coeff is None and _fractional_occupation_populations(self.mo_occ) is not None:
                raise NotImplementedError(FRACTIONAL_OCCUPATION_SPIN_SQUARE_MESSAGE)
            return super().spin_square(mo_coeff, s)

        def _finalize(self):
            if _fractional_occupation_populations(self.mo_occ) is None:
                return super()._finalize()
            return _finalize_fractional_occupation_scf(
                self,
                base_finalize=pyscf_hf.SCF._finalize,
                logger=pyscf_logger,
            )

    AtomSphAverageUKS.__name__ = "AtomSphAverageUKS"
    return AtomSphAverageUKS


@lru_cache(maxsize=1)
def get_atom_spherical_uhf_class():  # pragma: no cover - requires optional PySCF
    """Return the PySCF UHF subclass implementing spherical occupations."""

    try:
        from pyscf.lib import logger as pyscf_logger  # type: ignore[import-not-found]
        from pyscf.scf import hf as pyscf_hf  # type: ignore[import-not-found]
        from pyscf.scf import uhf as pyscf_uhf  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError(
            "PySCF is required for spherical UHF generation. Install with "
            "`python -m pip install \"atomref-proatoms[generator]\"` or from source "
            "with `python -m pip install -e \".[generator]\"`."
        ) from exc

    class AtomSphAverageUHF(pyscf_uhf.UHF):  # type: ignore[misc]
        """PySCF UHF subclass with l-block radial eigensolvers and fixed occupations."""

        def __init__(
            self,
            mol: Any,
            alpha_l_counts: Mapping[int | str, float] | None = None,
            beta_l_counts: Mapping[int | str, float] | None = None,
        ) -> None:
            super().__init__(mol)
            self._keys = self._keys.union({"alpha_l_counts", "beta_l_counts"})
            self.alpha_l_counts = _as_l_count_mapping(alpha_l_counts)
            self.beta_l_counts = _as_l_count_mapping(beta_l_counts)
            self.init_guess = "1e"
            self.init_guess_breaksym = 0

        def eig(self, fock: Any, ovlp: Any, overwrite: bool = False, x: Any = None):
            del overwrite, x
            fock_arr = np.asarray(fock)
            if fock_arr.ndim == 2:
                energy, coeff = spherical_block_eigh(self, fock_arr, ovlp)
                return np.stack([energy, energy]), np.stack([coeff, coeff])
            energy_a, coeff_a = spherical_block_eigh(self, fock_arr[0], ovlp)
            energy_b, coeff_b = spherical_block_eigh(self, fock_arr[1], ovlp)
            return np.stack([energy_a, energy_b]), np.stack([coeff_a, coeff_b])

        def get_occ(self, mo_energy: Any = None, mo_coeff: Any = None):
            del mo_energy, mo_coeff
            occ_a = occupation_from_l_counts(self.mol, self.alpha_l_counts, 1.0)
            occ_b = occupation_from_l_counts(self.mol, self.beta_l_counts, 1.0)

            target_alpha, target_beta = self.mol.nelec
            if abs(float(occ_a.sum()) - target_alpha) > 1e-8:
                raise ValueError(
                    f"alpha occupation sum {occ_a.sum()} != target alpha {target_alpha}"
                )
            if abs(float(occ_b.sum()) - target_beta) > 1e-8:
                raise ValueError(f"beta occupation sum {occ_b.sum()} != target beta {target_beta}")

            return np.stack([occ_a, occ_b])

        def get_grad(self, mo_coeff: Any, mo_occ: Any, fock: Any = None):
            del mo_coeff, mo_occ, fock
            return np.zeros(0)

        def spin_square(self, mo_coeff: Any = None, s: Any = None):
            if mo_coeff is None and _fractional_occupation_populations(self.mo_occ) is not None:
                raise NotImplementedError(FRACTIONAL_OCCUPATION_SPIN_SQUARE_MESSAGE)
            return super().spin_square(mo_coeff, s)

        def _finalize(self):
            if _fractional_occupation_populations(self.mo_occ) is None:
                return super()._finalize()
            return _finalize_fractional_occupation_scf(
                self,
                base_finalize=pyscf_hf.SCF._finalize,
                logger=pyscf_logger,
            )

    AtomSphAverageUHF.__name__ = "AtomSphAverageUHF"
    return AtomSphAverageUHF


def make_spherical_uks(
    mol: Any,
    *,
    xc: str = "PBE0",
    alpha_l_counts: Mapping[int | str, float] | None = None,
    beta_l_counts: Mapping[int | str, float] | None = None,
):
    """Create the PySCF spherical fractional-occupation UKS object lazily."""

    validate_spherical_ao_layout(mol)
    cls = get_atom_spherical_uks_class()
    return cls(mol, xc=xc, alpha_l_counts=alpha_l_counts, beta_l_counts=beta_l_counts)


def make_spherical_uhf(
    mol: Any,
    *,
    alpha_l_counts: Mapping[int | str, float] | None = None,
    beta_l_counts: Mapping[int | str, float] | None = None,
):
    """Create the PySCF spherical fractional-occupation UHF object lazily."""

    validate_spherical_ao_layout(mol)
    cls = get_atom_spherical_uhf_class()
    return cls(mol, alpha_l_counts=alpha_l_counts, beta_l_counts=beta_l_counts)


def configure_dft_grid(mf: Any, *, level: int = 4, prune: Any = None) -> Any:
    """Apply deterministic DFT grid settings to a PySCF mean-field object."""

    mf.grids.level = level
    mf.grids.prune = prune
    return mf


def apply_x2c_if_requested(mf: Any, *, use_x2c: bool) -> Any:
    """Apply PySCF spin-free one-electron X2C while preserving occupation metadata."""

    if not use_x2c:
        return mf

    alpha_l_counts = getattr(mf, "alpha_l_counts", None)
    beta_l_counts = getattr(mf, "beta_l_counts", None)
    mf_x2c = mf.sfx2c1e()

    if hasattr(mf_x2c, "_keys"):
        mf_x2c._keys = mf_x2c._keys.union({"alpha_l_counts", "beta_l_counts"})
    if alpha_l_counts is not None:
        mf_x2c.alpha_l_counts = alpha_l_counts
    if beta_l_counts is not None:
        mf_x2c.beta_l_counts = beta_l_counts
    return mf_x2c
