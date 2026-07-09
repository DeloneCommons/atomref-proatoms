from __future__ import annotations

import io

import pytest

from atomref_proatoms.engines.spherical_uks import (
    FRACTIONAL_OCCUPATION_SPIN_SQUARE_MESSAGE,
    make_spherical_uhf,
    make_spherical_uks,
)


@pytest.mark.parametrize("method", ["uhf", "uks_hf"])
def test_fractional_spherical_scf_reports_truthful_spin_diagnostic(method: str) -> None:
    gto = pytest.importorskip("pyscf.gto")
    mol = gto.M(
        atom="C 0 0 0",
        basis="sto-3g",
        charge=0,
        spin=2,
        cart=False,
        verbose=0,
    )
    kwargs = {
        "alpha_l_counts": {0: 2.0, 1: 2.0},
        "beta_l_counts": {0: 2.0},
    }
    if method == "uhf":
        mf = make_spherical_uhf(mol, **kwargs)
    else:
        mf = make_spherical_uks(mol, xc="HF", **kwargs)
    output = io.StringIO()
    mf.stdout = output
    mf.verbose = 3
    mf.conv_tol = 1.0e-11
    mf.max_cycle = 100

    mf.kernel()

    assert mf.converged
    text = output.getvalue()
    assert "converged SCF energy" in text
    assert "<S^2> =" not in text
    assert "fractional-occupation spherical ensemble" in text
    assert "Nalpha = 4" in text
    assert "Nbeta = 2" in text
    assert "nominal 2S+1 = 3" in text
    with pytest.raises(NotImplementedError, match="fractional-occupation spherical ensemble"):
        mf.spin_square()
    assert FRACTIONAL_OCCUPATION_SPIN_SQUARE_MESSAGE.startswith("<S^2> is not defined")


@pytest.mark.parametrize("method", ["uhf", "uks_hf"])
def test_integer_spherical_scf_retains_determinant_spin_diagnostic(method: str) -> None:
    gto = pytest.importorskip("pyscf.gto")
    mol = gto.M(
        atom="H 0 0 0",
        basis="sto-3g",
        charge=0,
        spin=1,
        cart=False,
        verbose=0,
    )
    kwargs = {
        "alpha_l_counts": {0: 1.0},
        "beta_l_counts": {},
    }
    if method == "uhf":
        mf = make_spherical_uhf(mol, **kwargs)
    else:
        mf = make_spherical_uks(mol, xc="HF", **kwargs)
    output = io.StringIO()
    mf.stdout = output
    mf.verbose = 3

    mf.kernel()

    assert mf.converged
    text = output.getvalue()
    assert "<S^2> = 0.75" in text
    assert "fractional-occupation spherical ensemble" not in text
    spin_square, multiplicity = mf.spin_square()
    assert spin_square == pytest.approx(0.75)
    assert multiplicity == pytest.approx(2.0)
