"""Basis-source parsing and lightweight generator checks."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ..dataio.basis import SYMBOL_BY_Z, Z_BY_SYMBOL, parse_covered_z

BasisSourceKind = Literal["pyscf", "bse", "file"]
FullElectronStatus = Literal["no_ecp_detected", "ecp_detected", "unknown"]

_ECP_HINT_RE = re.compile(r"(^|\s)(ecp|potential|nelec)($|\s)", re.IGNORECASE)
_ECP_NELEC_RE = re.compile(r"^\s*([A-Za-z]{1,2})\s+nelec\s+\d+\b", re.IGNORECASE)


@dataclass(frozen=True)
class BasisSpec:
    """Normalized basis-source request."""

    source: BasisSourceKind
    name: str
    label: str
    path: Path | None = None
    original: str | None = None

    @property
    def basis_key(self) -> str:
        return f"{self.source}:{self.label}"

    def as_dict(self) -> dict[str, str | None]:
        return {
            "source": self.source,
            "name": self.name,
            "label": self.label,
            "path": self.path.as_posix() if self.path is not None else None,
            "original": self.original,
            "basis_key": self.basis_key,
        }


@dataclass(frozen=True)
class BasisCheckResult:
    """JSON-friendly result of a non-SCF basis-source check."""

    spec: BasisSpec
    requested_symbols: tuple[str, ...]
    status: str
    full_electron_status: FullElectronStatus
    coverage_checked: bool
    covered_symbols: tuple[str, ...] = ()
    missing_symbols: tuple[str, ...] = ()
    ecp_detected: bool = False
    ecp_symbols: tuple[str, ...] = ()
    check_method: str = "not_performed"
    messages: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    basis_sha256: str | None = None
    rendered_nwchem: str | None = field(default=None, repr=False)

    def as_dict(self, *, include_rendered_basis: bool = False) -> dict[str, object]:
        data: dict[str, object] = {
            "basis_source": self.spec.as_dict(),
            "requested_symbols": list(self.requested_symbols),
            "status": self.status,
            "full_electron_status": self.full_electron_status,
            "coverage_checked": self.coverage_checked,
            "covered_symbols": list(self.covered_symbols),
            "missing_symbols": list(self.missing_symbols),
            "ecp_detected": self.ecp_detected,
            "ecp_symbols": list(self.ecp_symbols),
            "check_method": self.check_method,
            "messages": list(self.messages),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "basis_sha256": self.basis_sha256,
        }
        if include_rendered_basis:
            data["rendered_nwchem"] = self.rendered_nwchem
        return data


@dataclass(frozen=True)
class BasisPolicy:
    """Default safety policy for ECP and unverified basis sources."""

    allow_ecp: bool = False
    allow_unverified_basis: bool = False
    artifact_requires_wfn: bool = False


@dataclass(frozen=True)
class BasisPolicyDecision:
    status: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _normalize_symbol(symbol: str) -> str:
    value = str(symbol).strip()
    if not value:
        raise ValueError("empty element symbol")
    normalized = value[0].upper() + value[1:].lower()
    if normalized not in Z_BY_SYMBOL:
        raise ValueError(f"unknown element symbol {symbol!r}")
    return normalized


def normalize_symbols(symbols: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Normalize and de-duplicate symbols while preserving first occurrence order."""

    result: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = _normalize_symbol(symbol)
        if normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return tuple(result)


def parse_basis_spec(
    *,
    basis: str | None = None,
    basis_file: str | Path | None = None,
    basis_name: str | None = None,
) -> BasisSpec:
    """Parse the public basis-source grammar."""

    if basis_file is not None and basis is not None:
        raise ValueError("Use either --basis or --basis-file, not both")
    if basis_file is not None:
        path = Path(basis_file).expanduser()
        name = str(basis_name).strip() if basis_name else path.stem
        if not name:
            raise ValueError("basis name must be non-empty")
        return BasisSpec(source="file", name=name, label=name, path=path, original=path.as_posix())
    value = str(basis).strip() if basis is not None else ""
    if not value:
        raise ValueError("basis must be non-empty")
    if value.lower().startswith("pyscf:"):
        name = value.split(":", 1)[1].strip()
        if not name:
            raise ValueError("pyscf: basis name must be non-empty")
        return BasisSpec(source="pyscf", name=name, label=name, original=value)
    if value.lower().startswith("bse:"):
        name = value.split(":", 1)[1].strip()
        if not name:
            raise ValueError("bse: basis name must be non-empty")
        return BasisSpec(source="bse", name=name, label=name, original=value)
    return BasisSpec(source="pyscf", name=value, label=value, original=value)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def detect_ecp_in_nwchem_text(text: str) -> bool:
    """Return True when an NWChem-like basis file contains obvious ECP markers."""

    return bool(detect_ecp_symbols_in_nwchem_text(text)) or any(
        _ECP_HINT_RE.search(line.strip())
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def detect_ecp_symbols_in_nwchem_text(text: str) -> tuple[str, ...]:
    """Return symbols with explicit ``nelec`` ECP records in NWChem text."""

    symbols: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        match = _ECP_NELEC_RE.match(raw_line)
        if match is None:
            continue
        try:
            symbol = _normalize_symbol(match.group(1))
        except ValueError:
            continue
        if symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)
    return tuple(symbols)


def _covered_symbols_from_nwchem(text: str) -> tuple[str, ...]:
    return tuple(SYMBOL_BY_Z[z_value] for z_value in parse_covered_z(text))


def check_basis_source(spec: BasisSpec, symbols: tuple[str, ...] | list[str]) -> BasisCheckResult:
    """Perform a lightweight basis-source check without running SCF."""

    requested = normalize_symbols(tuple(symbols))
    if spec.source == "file":
        return _check_file_basis(spec, requested)
    if spec.source == "pyscf":
        return _check_pyscf_basis(spec, requested)
    if spec.source == "bse":
        return _check_bse_basis(spec, requested)
    raise ValueError(f"unknown basis source: {spec.source!r}")


def _check_file_basis(spec: BasisSpec, symbols: tuple[str, ...]) -> BasisCheckResult:
    assert spec.path is not None
    path = spec.path.expanduser()
    if not path.is_file():
        return BasisCheckResult(
            spec=spec,
            requested_symbols=symbols,
            status="error",
            full_electron_status="unknown",
            coverage_checked=False,
            errors=(f"basis file not found: {path}",),
        )
    text = path.read_text(encoding="utf-8")
    covered = _covered_symbols_from_nwchem(text)
    missing = tuple(symbol for symbol in symbols if symbol not in set(covered))
    ecp_symbols = detect_ecp_symbols_in_nwchem_text(text)
    ecp_detected = bool(ecp_symbols) or detect_ecp_in_nwchem_text(text)
    errors = tuple(f"basis file has no shell data for {symbol}" for symbol in missing)
    warnings: tuple[str, ...] = ()
    if not ecp_detected:
        warnings = ("No obvious ECP marker was found; full-electron status is still unverified.",)
    return BasisCheckResult(
        spec=spec,
        requested_symbols=symbols,
        status="error" if errors else "ok",
        full_electron_status="ecp_detected" if ecp_detected else "unknown",
        coverage_checked=True,
        covered_symbols=covered,
        missing_symbols=missing,
        ecp_detected=ecp_detected,
        ecp_symbols=ecp_symbols,
        check_method="nwchem_text_scan",
        errors=errors,
        warnings=warnings,
        basis_sha256=sha256_text(text),
        rendered_nwchem=text,
    )


def _check_pyscf_basis(spec: BasisSpec, symbols: tuple[str, ...]) -> BasisCheckResult:
    try:
        import pyscf  # type: ignore[import-not-found]
        from pyscf import gto  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency path
        return BasisCheckResult(
            spec=spec,
            requested_symbols=symbols,
            status="not_performed_pyscf_missing",
            full_electron_status="unknown",
            coverage_checked=False,
            messages=(f"PySCF is not installed: {exc}",),
        )

    missing: list[str] = []
    ecp_symbols: list[str] = []
    messages = [f"PySCF version: {getattr(pyscf, '__version__', 'unknown')}"]
    for symbol in symbols:
        try:
            gto.basis.load(spec.name, symbol)
        except Exception:
            missing.append(symbol)
            continue
        try:
            ecp = gto.basis.load_ecp(spec.name, symbol)
        except Exception:
            ecp = None
        if ecp:
            ecp_symbols.append(symbol)
    status = "error" if missing else "ok"
    full_status: FullElectronStatus = "ecp_detected" if ecp_symbols else "no_ecp_detected"
    errors = tuple(f"PySCF basis {spec.name!r} is not available for {symbol}" for symbol in missing)
    warnings = tuple(f"PySCF ECP data detected for {symbol}" for symbol in ecp_symbols)
    return BasisCheckResult(
        spec=spec,
        requested_symbols=symbols,
        status=status,
        full_electron_status=full_status,
        coverage_checked=True,
        covered_symbols=tuple(symbol for symbol in symbols if symbol not in missing),
        missing_symbols=tuple(missing),
        ecp_detected=bool(ecp_symbols),
        ecp_symbols=tuple(ecp_symbols),
        check_method="pyscf_basis_load",
        messages=tuple(messages),
        errors=errors,
        warnings=warnings,
    )


def _check_bse_basis(spec: BasisSpec, symbols: tuple[str, ...]) -> BasisCheckResult:
    try:
        import basis_set_exchange as bse  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency path
        return BasisCheckResult(
            spec=spec,
            requested_symbols=symbols,
            status="not_performed_bse_missing",
            full_electron_status="unknown",
            coverage_checked=False,
            messages=(f"basis-set-exchange is not installed: {exc}",),
        )

    elements = [Z_BY_SYMBOL[symbol] for symbol in symbols]
    try:
        data = bse.get_basis(spec.name, elements=elements, uncontract_general=True)
        nwchem_text = bse.get_basis(
            spec.name,
            elements=elements,
            fmt="nwchem",
            uncontract_general=True,
        )
    except Exception as exc:  # pragma: no cover - optional dependency path
        return BasisCheckResult(
            spec=spec,
            requested_symbols=symbols,
            status="error",
            full_electron_status="unknown",
            coverage_checked=False,
            errors=(f"BSE failed to resolve {spec.name!r}: {exc}",),
        )

    element_data = data.get("elements", {}) if isinstance(data, dict) else {}
    covered = tuple(
        SYMBOL_BY_Z[int(z_value)] for z_value in sorted(int(key) for key in element_data)
    )
    missing = tuple(symbol for symbol in symbols if symbol not in set(covered))
    ecp_symbols = []
    for z_text, record in element_data.items():
        if isinstance(record, dict) and record.get("ecp_potentials"):
            ecp_symbols.append(SYMBOL_BY_Z[int(z_text)])
    ecp_detected = bool(ecp_symbols) or detect_ecp_in_nwchem_text(str(nwchem_text))
    errors = tuple(f"BSE basis {spec.name!r} has no shell data for {symbol}" for symbol in missing)
    warnings = tuple(f"BSE ECP data detected for {symbol}" for symbol in ecp_symbols)
    return BasisCheckResult(
        spec=spec,
        requested_symbols=symbols,
        status="error" if errors else "ok",
        full_electron_status="ecp_detected" if ecp_detected else "no_ecp_detected",
        coverage_checked=True,
        covered_symbols=covered,
        missing_symbols=missing,
        ecp_detected=ecp_detected,
        ecp_symbols=tuple(ecp_symbols),
        check_method="basis_set_exchange_json",
        errors=errors,
        warnings=warnings,
        basis_sha256=sha256_text(str(nwchem_text)),
        rendered_nwchem=str(nwchem_text),
    )


def apply_basis_policy(check: BasisCheckResult, policy: BasisPolicy) -> BasisPolicyDecision:
    """Convert a basis check into release-facing pass/fail policy."""

    errors = list(check.errors)
    warnings = list(check.warnings)
    if check.full_electron_status == "ecp_detected" and not policy.allow_ecp:
        errors.append(
            "ECP/effective-core basis data were detected; "
            "rerun with --allow-ecp to allow it."
        )
    if policy.artifact_requires_wfn and check.full_electron_status == "ecp_detected":
        errors.append(
            "WFN export requires all-electron basis data; ECP/effective-core sources "
            "can generate profiles and .rad files with --allow-ecp, but not .wfn files."
        )
    if (
        policy.artifact_requires_wfn
        and check.full_electron_status == "unknown"
        and not policy.allow_unverified_basis
    ):
        errors.append(
            "WFN export requires verified all-electron basis data; rerun with "
            "--allow-unverified-basis to override."
        )
    elif check.full_electron_status == "unknown":
        warnings.append("Full-electron status is unknown for this basis source.")
    if check.status.startswith("not_performed"):
        warnings.append(check.status)
    return BasisPolicyDecision(
        status="error" if errors else "ok",
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
