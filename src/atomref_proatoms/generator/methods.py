"""Method and relativity parsing for generator planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MethodKind = Literal["hf", "dft"]
RelativityKind = Literal["none", "x2c"]


@dataclass(frozen=True)
class MethodSpec:
    """Normalized generator method request."""

    input_method: str
    method_kind: MethodKind
    xc: str | None
    scf_type: str

    @property
    def method_id(self) -> str:
        if self.method_kind == "hf":
            return "hf"
        assert self.xc is not None
        return self.xc

    def as_dict(self) -> dict[str, str | None]:
        return {
            "input_method": self.input_method,
            "method_kind": self.method_kind,
            "xc": self.xc,
            "scf_type": self.scf_type,
        }


@dataclass(frozen=True)
class RelativitySpec:
    """Normalized scalar-relativity request."""

    input_relativity: str
    relativity: RelativityKind
    engine_label: str

    def as_dict(self) -> dict[str, str]:
        return {
            "input_relativity": self.input_relativity,
            "relativity": self.relativity,
            "engine_label": self.engine_label,
        }


@dataclass(frozen=True)
class MethodCheck:
    """Result of optional PySCF/libxc method validation."""

    status: str
    message: str
    pyscf_version: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "status": self.status,
            "message": self.message,
            "pyscf_version": self.pyscf_version,
        }


def parse_method(method: str) -> MethodSpec:
    """Parse ``--method`` without maintaining a registry of DFT functionals."""

    value = str(method).strip()
    if not value:
        raise ValueError("method must be non-empty")
    if value.lower() == "hf":
        return MethodSpec(input_method=value, method_kind="hf", xc=None, scf_type="UHF")
    if value.lower().startswith("dft:"):
        value = value.split(":", 1)[1].strip()
        if not value:
            raise ValueError("dft: method must contain a PySCF XC string")
    return MethodSpec(input_method=str(method).strip(), method_kind="dft", xc=value, scf_type="UKS")


def parse_relativity(relativity: str) -> RelativitySpec:
    """Parse ``--relativity`` into the engine metadata label."""

    value = str(relativity).strip().lower()
    if value in {"none", "non", "no", "false", "0"}:
        return RelativitySpec(
            input_relativity=str(relativity).strip(), relativity="none", engine_label="none"
        )
    if value in {"x2c", "sfx2c", "sf-x2c", "sf-x2c-1e"}:
        return RelativitySpec(
            input_relativity=str(relativity).strip(), relativity="x2c", engine_label="sf-X2C-1e"
        )
    raise ValueError("relativity must be one of: x2c, none")


def check_method_with_pyscf(spec: MethodSpec) -> MethodCheck:
    """Validate a method against the installed PySCF version when available."""

    try:
        import pyscf  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency path
        return MethodCheck(
            status="not_performed_pyscf_missing",
            message=f"PySCF is not installed: {exc}",
            pyscf_version=None,
        )

    pyscf_version = getattr(pyscf, "__version__", "unknown")
    if spec.method_kind == "hf":
        return MethodCheck(
            status="ok",
            message="HF is handled as a special generator method.",
            pyscf_version=pyscf_version,
        )

    assert spec.xc is not None
    try:
        from pyscf.dft import libxc  # type: ignore[import-not-found]

        libxc.parse_xc(spec.xc)
    except Exception as exc:  # pragma: no cover - optional dependency path
        return MethodCheck(
            status="error",
            message=f"PySCF rejected XC string {spec.xc!r}: {exc}",
            pyscf_version=pyscf_version,
        )
    return MethodCheck(
        status="ok",
        message=f"PySCF accepted XC string {spec.xc!r}.",
        pyscf_version=pyscf_version,
    )
