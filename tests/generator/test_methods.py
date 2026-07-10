from __future__ import annotations

import importlib.util

import pytest

from atomref_proatoms.generator.methods import (
    check_method_with_pyscf,
    parse_method,
    parse_relativity,
)


def test_parse_method_accepts_hf_special_case() -> None:
    spec = parse_method("hf")
    assert spec.method_kind == "hf"
    assert spec.scf_type == "UHF"
    assert spec.xc is None


def test_parse_method_passes_dft_string_through() -> None:
    spec = parse_method("dft:PBE0")
    assert spec.method_kind == "dft"
    assert spec.scf_type == "UKS"
    assert spec.xc == "PBE0"


def test_parse_relativity_normalizes_labels() -> None:
    assert parse_relativity("x2c").engine_label == "sf-X2C-1e"
    assert parse_relativity("none").engine_label == "none"
    with pytest.raises(ValueError, match="relativity"):
        parse_relativity("soc")


def test_check_method_without_pyscf_is_non_fatal_when_missing() -> None:
    result = check_method_with_pyscf(parse_method("PBE0"))
    if importlib.util.find_spec("pyscf") is None:
        assert result.status == "not_performed_pyscf_missing"
    else:
        assert result.status in {"ok", "error"}
