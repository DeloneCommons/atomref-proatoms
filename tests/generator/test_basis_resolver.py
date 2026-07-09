from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from atomref_proatoms.generator.basis_resolver import (
    BasisPolicy,
    apply_basis_policy,
    check_basis_source,
    detect_ecp_in_nwchem_text,
    parse_basis_spec,
)


def test_parse_basis_spec_variants(tmp_path: Path) -> None:
    assert parse_basis_spec(basis="def2-TZVPP").source == "pyscf"
    assert parse_basis_spec(basis="pyscf:def2-TZVPP").name == "def2-TZVPP"
    assert parse_basis_spec(basis="bse:x2c-QZVPall").source == "bse"
    basis_file = tmp_path / "basis.nw"
    spec = parse_basis_spec(basis_file=basis_file)
    assert spec.source == "file"
    assert spec.name == "basis"
    with pytest.raises(ValueError):
        parse_basis_spec(basis="def2", basis_file=basis_file)


def test_file_basis_text_scan_detects_coverage_and_ecp(tmp_path: Path) -> None:
    path = tmp_path / "mini.nw"
    path.write_text(
        'BASIS "ao basis" SPHERICAL PRINT\n'
        "H S\n"
        "  1.0 1.0\n"
        "END\n",
        encoding="utf-8",
    )
    result = check_basis_source(parse_basis_spec(basis_file=path), ("H", "C"))
    assert result.status == "error"
    assert result.covered_symbols == ("H",)
    assert result.missing_symbols == ("C",)
    assert result.full_electron_status == "unknown"

    ecp_text = "ECP\nC nelec 2\n"
    assert detect_ecp_in_nwchem_text(ecp_text)


def test_apply_basis_policy_rejects_ecp_without_override(tmp_path: Path) -> None:
    path = tmp_path / "ecp.nw"
    path.write_text(
        'BASIS "ao basis" SPHERICAL PRINT\n'
        "C S\n"
        "  1.0 1.0\n"
        "END\n"
        "ECP\n"
        "C nelec 2\n",
        encoding="utf-8",
    )
    result = check_basis_source(parse_basis_spec(basis_file=path), ("C",))
    decision = apply_basis_policy(result, BasisPolicy())
    assert decision.status == "error"
    assert any("ECP" in error for error in decision.errors)


def test_pyscf_basis_check_is_lazy_when_missing() -> None:
    result = check_basis_source(parse_basis_spec(basis="def2-SVP"), ("H",))
    if importlib.util.find_spec("pyscf") is None:
        assert result.status == "not_performed_pyscf_missing"
    else:
        assert result.status in {"ok", "error"}
