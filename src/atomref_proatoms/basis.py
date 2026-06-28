"""Frozen basis-bundle loading and offline validation utilities."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .schemas import BASIS_BUNDLE_SCHEMA_VERSION, BASIS_SET_SUMMARY_SCHEMA_VERSION

ELEMENTS = [
    "H",
    "He",
    "Li",
    "Be",
    "B",
    "C",
    "N",
    "O",
    "F",
    "Ne",
    "Na",
    "Mg",
    "Al",
    "Si",
    "P",
    "S",
    "Cl",
    "Ar",
    "K",
    "Ca",
    "Sc",
    "Ti",
    "V",
    "Cr",
    "Mn",
    "Fe",
    "Co",
    "Ni",
    "Cu",
    "Zn",
    "Ga",
    "Ge",
    "As",
    "Se",
    "Br",
    "Kr",
    "Rb",
    "Sr",
    "Y",
    "Zr",
    "Nb",
    "Mo",
    "Tc",
    "Ru",
    "Rh",
    "Pd",
    "Ag",
    "Cd",
    "In",
    "Sn",
    "Sb",
    "Te",
    "I",
    "Xe",
    "Cs",
    "Ba",
    "La",
    "Ce",
    "Pr",
    "Nd",
    "Pm",
    "Sm",
    "Eu",
    "Gd",
    "Tb",
    "Dy",
    "Ho",
    "Er",
    "Tm",
    "Yb",
    "Lu",
    "Hf",
    "Ta",
    "W",
    "Re",
    "Os",
    "Ir",
    "Pt",
    "Au",
    "Hg",
    "Tl",
    "Pb",
    "Bi",
    "Po",
    "At",
    "Rn",
    "Fr",
    "Ra",
    "Ac",
    "Th",
    "Pa",
    "U",
    "Np",
    "Pu",
    "Am",
    "Cm",
    "Bk",
    "Cf",
    "Es",
    "Fm",
    "Md",
    "No",
    "Lr",
    "Rf",
    "Db",
    "Sg",
    "Bh",
    "Hs",
    "Mt",
    "Ds",
    "Rg",
    "Cn",
    "Nh",
    "Fl",
    "Mc",
    "Lv",
    "Ts",
    "Og",
]

Z_BY_SYMBOL = {symbol: idx + 1 for idx, symbol in enumerate(ELEMENTS)}
SYMBOL_BY_Z = {idx + 1: symbol for idx, symbol in enumerate(ELEMENTS)}
EXPECTED_BASIS_IDS = ("x2c-QZVPall", "x2c-QZVPall-s", "dyall-v4z", "dyall-av4z")
EXPECTED_NWCHEM_SPHERICAL_HEADER = 'BASIS "ao basis" SPHERICAL PRINT'
SHELL_RE = re.compile(r"^([A-Z][a-z]?)\s+([SPDFGHIKLMNO])\b")
SMOKE_SYMBOLS = ("H", "C", "I", "Rn", "Lr", "Og")


@dataclass(frozen=True)
class BasisBundle:
    """A frozen basis bundle and the matching root-summary entry."""

    basis_id: str
    path: Path
    manifest: dict[str, Any]
    summary_row: dict[str, Any]

    @property
    def basis_path(self) -> Path:
        return self.path / self.manifest["files"]["basis_file"]

    @property
    def basis_sha256(self) -> str:
        return str(self.manifest["files"]["basis_sha256"])

    @property
    def coverage_intervals(self) -> list[list[int]]:
        return list(self.manifest["coverage"]["z_coverage_intervals"])


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_basis_summary(root_or_file: Path) -> dict[str, Any]:
    path = root_or_file / "basis_set_summary.json" if root_or_file.is_dir() else root_or_file
    summary = read_json(path)
    if summary.get("schema_version") != BASIS_SET_SUMMARY_SCHEMA_VERSION:
        raise ValueError(f"Unexpected basis summary schema_version in {path}")
    rows = summary.get("basis_bundles")
    if not isinstance(rows, list):
        raise ValueError(f"basis_bundles must be a list in {path}")
    return summary


def basis_summary_by_id(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = summary["basis_bundles"]
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        basis_id = row.get("basis_id")
        if not isinstance(basis_id, str):
            raise ValueError("Every basis summary row must contain string basis_id")
        if basis_id in by_id:
            raise ValueError(f"Duplicate basis_id in basis_set_summary.json: {basis_id}")
        by_id[basis_id] = row
    return by_id


def load_basis_manifest(bundle_dir: Path) -> dict[str, Any]:
    manifest = read_json(bundle_dir / "manifest.json")
    if manifest.get("schema_version") != BASIS_BUNDLE_SCHEMA_VERSION:
        raise ValueError(f"Unexpected basis manifest schema_version in {bundle_dir}")
    if manifest.get("basis_id") != bundle_dir.name:
        raise ValueError(f"Manifest basis_id does not match directory name: {bundle_dir}")
    return manifest


def list_basis_bundles(root: Path) -> list[BasisBundle]:
    summary = load_basis_summary(root)
    by_id = basis_summary_by_id(summary)
    bundles: list[BasisBundle] = []
    for basis_id in EXPECTED_BASIS_IDS:
        if basis_id not in by_id:
            raise ValueError(f"Missing {basis_id} in root basis_set_summary.json")
        bundle_dir = root / basis_id
        if not bundle_dir.is_dir():
            raise ValueError(f"Missing basis bundle directory: {bundle_dir}")
        manifest = load_basis_manifest(bundle_dir)
        bundles.append(BasisBundle(basis_id, bundle_dir, manifest, by_id[basis_id]))
    extra_dirs = sorted(
        path.name for path in root.iterdir() if path.is_dir() and path.name not in by_id
    )
    if extra_dirs:
        raise ValueError(f"Basis bundle directories missing from root summary: {extra_dirs}")
    return bundles


def verify_basis_source_url_shape(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"BSE source URL must be http(s): {url}")
    if "basissetexchange.org" not in parsed.netloc.lower():
        raise ValueError(f"BSE source URL has unexpected host: {url}")
    path = parsed.path.lower()
    if "/api/basis/" not in path or "/format/nwchem/" not in path:
        raise ValueError(f"BSE source URL must be an API NWChem URL: {url}")
    query = parse_qs(parsed.query)
    if not query.get("version") or not query.get("elements"):
        raise ValueError(f"BSE source URL must include version and elements query fields: {url}")


def verify_basis_source_metadata(summary_row: dict[str, Any], manifest: dict[str, Any]) -> None:
    for label, obj in (("manifest", manifest), ("summary", summary_row)):
        source = obj.get("source")
        if not isinstance(source, dict):
            raise ValueError(f"{manifest.get('basis_id')}: missing {label} source object")
        required = {
            "database",
            "source_api_url",
            "source_format",
            "retrieval_date",
            "bse_export_version",
            "upstream_basis_version",
            "upstream_role",
            "upstream_source_note",
        }
        missing = sorted(required - set(source))
        if missing:
            raise ValueError(f"{manifest.get('basis_id')}: missing {label} source keys {missing}")
        if source["database"] != "Basis Set Exchange":
            raise ValueError(f"{manifest.get('basis_id')}: unexpected source database")
        if source["source_format"] != "nwchem":
            raise ValueError(f"{manifest.get('basis_id')}: unexpected source format")
        verify_basis_source_url_shape(str(source["source_api_url"]))
    if manifest["source"] != summary_row["source"]:
        raise ValueError(f"{manifest['basis_id']}: manifest and summary source objects differ")


def load_basis_nw_text(bundle: BasisBundle) -> str:
    return bundle.basis_path.read_text(encoding="utf-8")


def parse_bse_header(text: str) -> dict[str, str]:
    header: dict[str, str] = {}
    for line in text.splitlines()[:80]:
        if line.startswith("# Version "):
            header["bse_export_version"] = line.removeprefix("# Version ").strip()
        elif line.startswith("#   Basis set:"):
            header["basis_name_upstream"] = line.split(":", 1)[1].strip()
        elif line.startswith("#        Role:"):
            header["upstream_role"] = line.split(":", 1)[1].strip()
        elif line.startswith("#     Version:"):
            value = line.split(":", 1)[1].strip()
            if "  (" in value and value.endswith(")"):
                version, note = value.split("  (", 1)
                header["upstream_basis_version"] = version.strip()
                header["upstream_source_note"] = note[:-1].strip()
            else:
                header["upstream_basis_version"] = value.strip()
    return header


def parse_covered_z(text: str) -> list[int]:
    symbols: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        match = SHELL_RE.match(line)
        if not match:
            continue
        symbol = match.group(1)
        if symbol in Z_BY_SYMBOL and symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)
    return sorted(Z_BY_SYMBOL[symbol] for symbol in symbols)


def intervals_from_z(z_values: list[int]) -> list[list[int]]:
    if not z_values:
        return []
    intervals: list[list[int]] = []
    start = prev = z_values[0]
    for z_value in z_values[1:]:
        if z_value == prev + 1:
            prev = z_value
            continue
        intervals.append([start, prev])
        start = prev = z_value
    intervals.append([start, prev])
    return intervals


def read_sha256sums(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, filename = line.split(None, 1)
        values[filename.strip()] = digest
    return values


def verify_basis_sha256(bundle: BasisBundle) -> None:
    actual = sha256_file(bundle.basis_path)
    if actual != bundle.basis_sha256:
        raise ValueError(
            f"{bundle.basis_id}: basis SHA mismatch: {actual} != {bundle.basis_sha256}"
        )
    summary_sha = bundle.summary_row["files"]["basis_sha256"]
    if actual != summary_sha:
        raise ValueError(f"{bundle.basis_id}: basis SHA differs between manifest and summary")
    sums = read_sha256sums(bundle.path / "sha256sums.txt")
    basis_file = bundle.manifest["files"]["basis_file"]
    if sums.get(basis_file) != actual:
        raise ValueError(f"{bundle.basis_id}: sha256sums.txt does not match basis.nw")


def basis_covers_z(bundle: BasisBundle, z_value: int) -> bool:
    return any(start <= z_value <= end for start, end in bundle.coverage_intervals)


def validate_basis_bundle(bundle: BasisBundle, *, run_pyscf_smoke: bool = False) -> list[str]:
    errors: list[str] = []
    required_files = ("basis.nw", "manifest.json", "sha256sums.txt", "references.md", "README.md")
    for filename in required_files:
        if not (bundle.path / filename).exists():
            errors.append(f"{bundle.basis_id}: missing {filename}")
    if errors:
        return errors

    try:
        verify_basis_source_metadata(bundle.summary_row, bundle.manifest)
        verify_basis_sha256(bundle)
    except Exception as exc:
        errors.append(str(exc))

    text = load_basis_nw_text(bundle)
    if EXPECTED_NWCHEM_SPHERICAL_HEADER not in text:
        errors.append(f"{bundle.basis_id}: missing NWChem SPHERICAL basis header")
    if not text.rstrip().endswith("END"):
        errors.append(f"{bundle.basis_id}: basis file does not end with END")

    header = parse_bse_header(text)
    source = bundle.manifest["source"]
    expected_header = {
        "bse_export_version": source.get("bse_export_version"),
        "upstream_basis_version": source.get("upstream_basis_version"),
        "basis_name_upstream": bundle.manifest.get("basis_name_upstream"),
        "upstream_role": source.get("upstream_role"),
        "upstream_source_note": source.get("upstream_source_note"),
    }
    for key, expected in expected_header.items():
        if key in header and expected is not None and header[key] != expected:
            errors.append(
                f"{bundle.basis_id}: header {key}={header[key]!r} "
                f"!= manifest {expected!r}"
            )

    z_values = parse_covered_z(text)
    intervals = intervals_from_z(z_values)
    coverage = bundle.manifest["coverage"]
    if intervals != coverage["z_coverage_intervals"]:
        errors.append(
            f"{bundle.basis_id}: coverage intervals {intervals} "
            f"!= manifest {coverage['z_coverage_intervals']}"
        )
    if len(z_values) != coverage["n_elements"]:
        errors.append(
            f"{bundle.basis_id}: n_elements {len(z_values)} "
            f"!= manifest {coverage['n_elements']}"
        )

    if run_pyscf_smoke:
        try:
            parse_pyscf_basis_smoke(bundle, text, z_values)
        except Exception as exc:  # pragma: no cover - optional dependency path
            errors.append(str(exc))

    return errors


def get_pyscf_basis_parser() -> tuple[Any | None, str | None, str | None]:
    try:
        import pyscf  # type: ignore[import-not-found]
        from pyscf.gto import basis as pyscf_basis  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional local dependency
        return None, None, str(exc)
    return pyscf_basis, getattr(pyscf, "__version__", "unknown"), None


def parse_pyscf_basis_smoke(
    bundle: BasisBundle,
    text: str | None = None,
    z_values: list[int] | None = None,
) -> list[str]:
    pyscf_basis, _version, error = get_pyscf_basis_parser()
    if pyscf_basis is None:
        raise RuntimeError(f"PySCF is not installed: {error}")
    basis_text = text if text is not None else load_basis_nw_text(bundle)
    covered_z = z_values if z_values is not None else parse_covered_z(basis_text)
    covered_symbols = {SYMBOL_BY_Z[z_value] for z_value in covered_z}
    parsed_cases: list[str] = []
    for symbol in SMOKE_SYMBOLS:
        if symbol not in covered_symbols:
            continue
        try:
            pyscf_basis.parse(basis_text, symb=symbol)
        except Exception as exc:  # pragma: no cover - optional local dependency
            raise RuntimeError(f"{bundle.basis_id}: PySCF failed to parse {symbol}: {exc}") from exc
        parsed_cases.append(f"{bundle.basis_id}:{symbol}")
    return parsed_cases


def validate_all_basis_bundles(root: Path, *, run_pyscf_smoke: bool = False) -> list[str]:
    errors: list[str] = []
    actual_dirs = sorted(path.name for path in root.iterdir() if path.is_dir())
    if actual_dirs != sorted(EXPECTED_BASIS_IDS):
        errors.append(
            f"Expected basis directories {sorted(EXPECTED_BASIS_IDS)}, "
            f"found {actual_dirs}"
        )
    for forbidden in root.rglob("*.mhtml"):
        errors.append(f"Forbidden acquisition snapshot under data/basis_sets: {forbidden}")
    for forbidden in root.rglob("manifest.csv"):
        errors.append(f"Forbidden basis manifest.csv under data/basis_sets: {forbidden}")
    try:
        bundles = list_basis_bundles(root)
    except Exception as exc:
        return errors + [str(exc)]
    for bundle in bundles:
        errors.extend(validate_basis_bundle(bundle, run_pyscf_smoke=run_pyscf_smoke))
    return errors
