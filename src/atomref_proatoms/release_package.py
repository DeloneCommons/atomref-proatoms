"""Release-candidate ZIP packages for generated profile datasets."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import json_safe
from .basis import sha256_file
from .datasets import DATASET_IDS
from .profile_checks import _reject_json_constant

RELEASE_PACKAGE_SCHEMA_VERSION = "atomref.proatoms.release_package.v0"
RELEASE_MANIFEST_NAME = "release_manifest.json"
DEFAULT_ARCHIVE_ROOT = "data/profiles"
_FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class ReleasePackageResult:
    """Result of writing a release-candidate ZIP archive."""

    output_dir: Path
    archive_path: Path
    archive_root: str
    dataset_ids: tuple[str, ...]
    file_count: int
    total_size_bytes: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ReleasePackageCheckResult:
    """Result of validating a release-candidate ZIP archive."""

    archive_path: Path
    dataset_ids: tuple[str, ...]
    file_count: int
    total_size_bytes: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def default_release_archive_path(output_dir: Path, dataset_ids: tuple[str, ...] = ()) -> Path:
    """Return the default release-candidate archive path for a generated output root."""

    label = "all_v0" if not dataset_ids or set(dataset_ids) == set(DATASET_IDS) else "selected"
    return output_dir.parent / f"{output_dir.name}-{label}-release.zip"


def discover_indexed_dataset_ids(output_dir: Path) -> tuple[str, ...]:
    """Return dataset IDs under ``output_dir`` that already have dataset indexes."""

    if not output_dir.exists():
        return ()
    dataset_ids = [
        path.name
        for path in output_dir.iterdir()
        if path.is_dir() and (path / "dataset_manifest.json").is_file()
    ]
    return tuple(sorted(dataset_ids))


def selected_release_dataset_ids(values: tuple[str, ...], output_dir: Path) -> tuple[str, ...]:
    """Resolve CLI-style dataset selections for release packaging."""

    if not values:
        return discover_indexed_dataset_ids(output_dir)
    expanded: list[str] = []
    for value in values:
        if value in {"all", "all_v0"}:
            expanded.extend(DATASET_IDS)
        elif value in DATASET_IDS:
            expanded.append(value)
        else:
            choices = ", ".join((*DATASET_IDS, "all", "all_v0"))
            raise ValueError(f"unknown dataset-id {value!r}; choices: {choices}")
    deduped: list[str] = []
    seen: set[str] = set()
    for dataset_id in expanded:
        if dataset_id in seen:
            continue
        seen.add(dataset_id)
        deduped.append(dataset_id)
    return tuple(deduped)


def _iter_dataset_files(dataset_dir: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (path for path in dataset_dir.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(dataset_dir).as_posix(),
        )
    )


def _required_dataset_files(dataset_dir: Path) -> tuple[Path, ...]:
    return (
        dataset_dir / "dataset_manifest.json",
        dataset_dir / "profile_index.csv",
        dataset_dir / "derived_radii.csv",
    )


def _zip_writestr(zip_handle: zipfile.ZipFile, arcname: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(arcname)
    info.date_time = _FIXED_ZIP_DATE
    info.compress_type = zipfile.ZIP_DEFLATED
    zip_handle.writestr(info, payload)


def _json_bytes(data: Any) -> bytes:
    safe = json_safe(data)
    return (json.dumps(safe, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode(
        "utf-8"
    )


def _normalize_archive_root(archive_root: str) -> str:
    root = archive_root.strip("/")
    if not root or root.startswith("..") or "/../" in f"/{root}/":
        raise ValueError(f"unsafe archive root: {archive_root!r}")
    return root


def package_dataset_outputs(
    output_dir: Path,
    archive_path: Path,
    *,
    dataset_ids: tuple[str, ...],
    archive_root: str = DEFAULT_ARCHIVE_ROOT,
    allow_missing: bool = False,
) -> ReleasePackageResult:
    """Write a release-candidate ZIP archive for selected generated datasets."""

    output_dir = output_dir.resolve()
    archive_path = archive_path.resolve()
    archive_root = _normalize_archive_root(archive_root)
    warnings: list[str] = []
    packaged_dataset_ids: list[str] = []
    packaged_files: list[dict[str, Any]] = []

    if not dataset_ids:
        raise ValueError("no dataset IDs selected for release packaging")

    for dataset_id in dataset_ids:
        dataset_dir = output_dir / dataset_id
        if not dataset_dir.is_dir():
            message = f"missing selected dataset directory: {dataset_dir}"
            if allow_missing:
                warnings.append(message)
                continue
            raise FileNotFoundError(message)
        missing_required = [
            path.name for path in _required_dataset_files(dataset_dir) if not path.is_file()
        ]
        if missing_required:
            message = f"{dataset_id}: missing dataset index files: {', '.join(missing_required)}"
            if allow_missing:
                warnings.append(message)
                continue
            raise FileNotFoundError(message)
        dataset_files = _iter_dataset_files(dataset_dir)
        if not dataset_files:
            message = f"selected dataset directory is empty: {dataset_dir}"
            if allow_missing:
                warnings.append(message)
                continue
            raise FileNotFoundError(message)
        packaged_dataset_ids.append(dataset_id)
        for file_path in dataset_files:
            if file_path.resolve() == archive_path:
                continue
            relpath = file_path.relative_to(dataset_dir).as_posix()
            arcname = f"{archive_root}/{dataset_id}/{relpath}"
            packaged_files.append(
                {
                    "dataset_id": dataset_id,
                    "archive_path": arcname,
                    "dataset_relative_path": relpath,
                    "size_bytes": file_path.stat().st_size,
                    "sha256": sha256_file(file_path),
                    "source_path": file_path,
                }
            )

    manifest_files = [
        {key: value for key, value in item.items() if key != "source_path"}
        for item in packaged_files
    ]
    manifest = {
        "schema_version": RELEASE_PACKAGE_SCHEMA_VERSION,
        "archive_root": archive_root,
        "dataset_ids": packaged_dataset_ids,
        "dataset_count": len(packaged_dataset_ids),
        "file_count": len(packaged_files),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in packaged_files),
        "files": manifest_files,
        "notes": [
            "Release-candidate package assembled from generated profile dataset directories.",
            "File hashes are SHA256 over the exact archived payload files before zipping.",
        ],
    }

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w") as zip_handle:
        _zip_writestr(zip_handle, RELEASE_MANIFEST_NAME, _json_bytes(manifest))
        for item in packaged_files:
            source_path = item["source_path"]
            assert isinstance(source_path, Path)
            _zip_writestr(zip_handle, str(item["archive_path"]), source_path.read_bytes())

    return ReleasePackageResult(
        output_dir=output_dir,
        archive_path=archive_path,
        archive_root=archive_root,
        dataset_ids=tuple(packaged_dataset_ids),
        file_count=len(packaged_files),
        total_size_bytes=int(manifest["total_size_bytes"]),
        warnings=tuple(warnings),
    )


def _read_strict_json_bytes(payload: bytes, *, label: str) -> Any:
    try:
        return json.loads(payload.decode("utf-8"), parse_constant=_reject_json_constant)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid strict JSON: {exc}") from exc


def check_release_package(
    archive_path: Path,
    *,
    expected_dataset_ids: tuple[str, ...] = (),
    require_hashes: bool = True,
) -> ReleasePackageCheckResult:
    """Validate a release-candidate ZIP archive manifest and file hashes."""

    errors: list[str] = []
    warnings: list[str] = []
    dataset_ids: tuple[str, ...] = ()
    file_count = 0
    total_size_bytes = 0

    if not archive_path.is_file():
        return ReleasePackageCheckResult(
            archive_path,
            dataset_ids,
            file_count,
            total_size_bytes,
            (f"missing archive: {archive_path}",),
            (),
        )

    try:
        with zipfile.ZipFile(archive_path) as zip_handle:
            names = set(zip_handle.namelist())
            if RELEASE_MANIFEST_NAME not in names:
                errors.append(f"missing {RELEASE_MANIFEST_NAME}")
                return ReleasePackageCheckResult(
                    archive_path,
                    dataset_ids,
                    file_count,
                    total_size_bytes,
                    tuple(errors),
                    tuple(warnings),
                )
            try:
                manifest = _read_strict_json_bytes(
                    zip_handle.read(RELEASE_MANIFEST_NAME), label=RELEASE_MANIFEST_NAME
                )
            except ValueError as exc:
                errors.append(str(exc))
                return ReleasePackageCheckResult(
                    archive_path,
                    dataset_ids,
                    file_count,
                    total_size_bytes,
                    tuple(errors),
                    tuple(warnings),
                )
            if not isinstance(manifest, dict):
                errors.append(f"{RELEASE_MANIFEST_NAME}: manifest root must be an object")
                return ReleasePackageCheckResult(
                    archive_path,
                    dataset_ids,
                    file_count,
                    total_size_bytes,
                    tuple(errors),
                    tuple(warnings),
                )
            if manifest.get("schema_version") != RELEASE_PACKAGE_SCHEMA_VERSION:
                errors.append(
                    f"manifest schema_version={manifest.get('schema_version')!r} "
                    f"!= {RELEASE_PACKAGE_SCHEMA_VERSION!r}"
                )
            dataset_ids = tuple(str(item) for item in manifest.get("dataset_ids", ()))
            expected_set = set(expected_dataset_ids)
            if expected_set and set(dataset_ids) != expected_set:
                errors.append(
                    f"manifest dataset_ids {sorted(dataset_ids)} != expected "
                    f"{sorted(expected_dataset_ids)}"
                )
            files = manifest.get("files")
            if not isinstance(files, list):
                errors.append("manifest.files must be a list")
                files = []
            file_count = len(files)
            for index, item in enumerate(files):
                if not isinstance(item, dict):
                    errors.append(f"manifest.files[{index}] must be an object")
                    continue
                arcname = str(item.get("archive_path", ""))
                if not arcname or arcname not in names:
                    errors.append(f"manifest file entry missing from archive: {arcname!r}")
                    continue
                payload = zip_handle.read(arcname)
                total_size_bytes += len(payload)
                expected_size = item.get("size_bytes")
                if expected_size != len(payload):
                    errors.append(
                        f"{arcname}: size_bytes {expected_size!r} != archived {len(payload)}"
                    )
                if require_hashes:
                    expected_sha = item.get("sha256")
                    actual_sha = __import__("hashlib").sha256(payload).hexdigest()
                    if expected_sha != actual_sha:
                        errors.append(f"{arcname}: sha256 mismatch")
            listed = {
                str(item.get("archive_path", "")) for item in files if isinstance(item, dict)
            }
            unlisted = sorted(names - {RELEASE_MANIFEST_NAME} - listed)
            if unlisted:
                warnings.append(f"archive contains {len(unlisted)} unlisted file(s)")
            if manifest.get("file_count") != file_count:
                errors.append(f"manifest.file_count {manifest.get('file_count')!r} != {file_count}")
            if manifest.get("total_size_bytes") != total_size_bytes:
                errors.append(
                    f"manifest.total_size_bytes {manifest.get('total_size_bytes')!r} "
                    f"!= {total_size_bytes}"
                )
    except zipfile.BadZipFile:
        errors.append(f"invalid ZIP archive: {archive_path}")

    return ReleasePackageCheckResult(
        archive_path=archive_path,
        dataset_ids=dataset_ids,
        file_count=file_count,
        total_size_bytes=total_size_bytes,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def format_release_package_result(result: ReleasePackageResult) -> str:
    """Format a release packaging result as deterministic text."""

    lines = [
        f"Generated output root: {result.output_dir}",
        f"Archive: {result.archive_path}",
        f"Archive root: {result.archive_root}",
        f"Datasets: {', '.join(result.dataset_ids) if result.dataset_ids else '<none>'}",
        f"Files packaged: {result.file_count}",
        f"Total payload size: {result.total_size_bytes} bytes",
    ]
    if result.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {item}" for item in result.warnings)
    return "\n".join(lines)


def format_release_package_check(result: ReleasePackageCheckResult) -> str:
    """Format a release package check result as deterministic text."""

    status = "OK" if result.ok else "FAILED"
    lines = [
        f"Status: {status}",
        f"Archive: {result.archive_path}",
        f"Datasets: {', '.join(result.dataset_ids) if result.dataset_ids else '<none>'}",
        f"Files checked: {result.file_count}",
        f"Total payload size: {result.total_size_bytes} bytes",
    ]
    if result.errors:
        lines.append("Errors:")
        lines.extend(f"  - {item}" for item in result.errors)
    if result.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {item}" for item in result.warnings)
    return "\n".join(lines)
