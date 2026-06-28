"""Release-candidate ZIP packages for generated profile datasets."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import json_safe
from .basis import sha256_file
from .build_plan import load_build_jobs
from .datasets import DATASET_IDS
from .profile_checks import _reject_json_constant

RELEASE_PACKAGE_SCHEMA_VERSION = "atomref.proatoms.release_package.v0"
RELEASE_MANIFEST_NAME = "release_manifest.json"
DEFAULT_ARCHIVE_ROOT = "data/profiles"
_FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)
_INDEX_FILE_NAMES = ("dataset_manifest.json", "profile_index.csv", "derived_radii.csv")


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
class ReleaseDatasetReport:
    """Dataset-level summary extracted from a release package."""

    dataset_id: str
    expected_profile_count: int | None
    manifest_profile_count: int | None
    profile_index_rows: int
    derived_radii_rows: int
    metadata_file_count: int
    profile_file_count: int
    charge_counts: dict[str, int]
    state_category_counts: dict[str, int]
    qa_profile_count: int
    max_abs_electron_count_error: float | None
    max_rel_angular_sigma: float | None
    linear_dependency_warning_count: int
    max_linear_dependency_vectors_removed: int | None


@dataclass(frozen=True)
class ReleasePackageCheckResult:
    """Result of validating a release-candidate ZIP archive."""

    archive_path: Path
    dataset_ids: tuple[str, ...]
    file_count: int
    total_size_bytes: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    dataset_reports: tuple[ReleaseDatasetReport, ...] = ()

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


def expected_profile_counts_from_states(
    states_file: Path, *, dataset_ids: tuple[str, ...] = DATASET_IDS
) -> dict[str, int]:
    """Return expected profile counts from the curated-state build plan."""

    jobs = load_build_jobs(states_file, dataset_ids=dataset_ids)
    counts: dict[str, int] = {dataset_id: 0 for dataset_id in dataset_ids}
    for job in jobs:
        counts[job.dataset_id] = counts.get(job.dataset_id, 0) + 1
    return counts


def _iter_dataset_files(dataset_dir: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (path for path in dataset_dir.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(dataset_dir).as_posix(),
        )
    )


def _required_dataset_files(dataset_dir: Path) -> tuple[Path, ...]:
    return tuple(dataset_dir / name for name in _INDEX_FILE_NAMES)


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


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except ValueError as exc:
        raise ValueError(f"{path}: invalid strict JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return data


def _dataset_summary_from_directory(dataset_id: str, dataset_dir: Path) -> dict[str, Any]:
    manifest_path = dataset_dir / "dataset_manifest.json"
    profile_index_path = dataset_dir / "profile_index.csv"
    derived_radii_path = dataset_dir / "derived_radii.csv"
    manifest = _read_json_file(manifest_path)
    profile_rows = _read_csv_rows(profile_index_path.read_text(encoding="utf-8"))
    derived_rows = _read_csv_rows(derived_radii_path.read_text(encoding="utf-8"))
    profile_files = tuple(sorted((dataset_dir / "profiles").glob("*.csv.zip")))
    metadata_files = tuple(sorted((dataset_dir / "metadata").glob("*.json")))
    return {
        "dataset_id": dataset_id,
        "profile_count": manifest.get("profile_count"),
        "profile_index_rows": len(profile_rows),
        "derived_radii_rows": len(derived_rows),
        "profile_archive_count": len(profile_files),
        "metadata_count": len(metadata_files),
    }


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
    dataset_summaries: list[dict[str, Any]] = []

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
        dataset_summaries.append(_dataset_summary_from_directory(dataset_id, dataset_dir))
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
        "datasets": dataset_summaries,
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


def _read_csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def _float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _archive_path_join(root: str, dataset_id: str, relpath: str) -> str:
    return f"{root.strip('/')}/{dataset_id}/{relpath}"


def _read_archive_json(
    zip_handle: zipfile.ZipFile, names: set[str], arcname: str, errors: list[str]
) -> dict[str, Any] | None:
    if arcname not in names:
        errors.append(f"missing dataset index file: {arcname}")
        return None
    try:
        data = _read_strict_json_bytes(zip_handle.read(arcname), label=arcname)
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if not isinstance(data, dict):
        errors.append(f"{arcname}: JSON root must be an object")
        return None
    return data


def _read_archive_csv(
    zip_handle: zipfile.ZipFile, names: set[str], arcname: str, errors: list[str]
) -> list[dict[str, str]] | None:
    if arcname not in names:
        errors.append(f"missing dataset index file: {arcname}")
        return None
    try:
        return _read_csv_rows(zip_handle.read(arcname).decode("utf-8"))
    except UnicodeDecodeError as exc:
        errors.append(f"{arcname}: invalid UTF-8 CSV: {exc}")
        return None


def _dataset_report_from_archive(
    zip_handle: zipfile.ZipFile,
    *,
    names: set[str],
    archive_root: str,
    dataset_id: str,
    expected_profile_count: int | None,
    errors: list[str],
    warnings: list[str],
) -> ReleaseDatasetReport:
    prefix = f"{archive_root.rstrip('/')}/{dataset_id}/"
    dataset_manifest_name = prefix + "dataset_manifest.json"
    profile_index_name = prefix + "profile_index.csv"
    derived_radii_name = prefix + "derived_radii.csv"

    dataset_manifest = _read_archive_json(zip_handle, names, dataset_manifest_name, errors)
    profile_rows = _read_archive_csv(zip_handle, names, profile_index_name, errors)
    derived_rows = _read_archive_csv(zip_handle, names, derived_radii_name, errors)

    manifest_profile_count = None
    if dataset_manifest is not None:
        if dataset_manifest.get("dataset_id") != dataset_id:
            errors.append(
                f"{dataset_manifest_name}: dataset_id {dataset_manifest.get('dataset_id')!r} "
                f"!= {dataset_id!r}"
            )
        manifest_profile_count = _int_or_none(dataset_manifest.get("profile_count"))
        if manifest_profile_count is None:
            errors.append(f"{dataset_manifest_name}: missing/integer profile_count")

    profile_rows = profile_rows or []
    derived_rows = derived_rows or []
    profile_file_count = len(
        [name for name in names if name.startswith(prefix + "profiles/") and name.endswith(".csv.zip")]
    )
    metadata_file_count = len(
        [name for name in names if name.startswith(prefix + "metadata/") and name.endswith(".json")]
    )
    profile_index_rows = len(profile_rows)
    derived_radii_rows = len(derived_rows)

    count_values = {
        "dataset_manifest.profile_count": manifest_profile_count,
        "profile_index rows": profile_index_rows,
        "derived_radii rows": derived_radii_rows,
        "profile archive files": profile_file_count,
        "metadata files": metadata_file_count,
    }
    observed_counts = {label: value for label, value in count_values.items() if value is not None}
    if observed_counts:
        unique_counts = set(observed_counts.values())
        if len(unique_counts) > 1:
            errors.append(
                f"{dataset_id}: inconsistent dataset counts: "
                + ", ".join(f"{label}={value}" for label, value in observed_counts.items())
            )
    if expected_profile_count is not None:
        actual = manifest_profile_count if manifest_profile_count is not None else profile_index_rows
        if actual != expected_profile_count:
            errors.append(
                f"{dataset_id}: profile_count {actual} != expected build-plan count "
                f"{expected_profile_count}"
            )

    profile_row_state_ids = [row.get("state_id", "") for row in profile_rows]
    if len(profile_row_state_ids) != len(set(profile_row_state_ids)):
        errors.append(f"{dataset_id}: duplicate state_id values in profile_index.csv")
    derived_state_ids = [row.get("state_id", "") for row in derived_rows]
    if set(profile_row_state_ids) != set(derived_state_ids):
        errors.append(f"{dataset_id}: profile_index.csv and derived_radii.csv state sets differ")

    for row in profile_rows:
        state_id = row.get("state_id", "<missing>")
        if row.get("dataset_id") != dataset_id:
            errors.append(f"{dataset_id}: {state_id}: profile_index dataset_id mismatch")
        profile_archive = row.get("profile_archive", "")
        metadata_json = row.get("metadata_json", "")
        if profile_archive:
            arcname = _archive_path_join(archive_root, dataset_id, profile_archive)
            if arcname not in names:
                errors.append(f"{dataset_id}: {state_id}: missing profile archive {arcname}")
        if metadata_json:
            arcname = _archive_path_join(archive_root, dataset_id, metadata_json)
            if arcname not in names:
                errors.append(f"{dataset_id}: {state_id}: missing metadata JSON {arcname}")

    charge_counts = Counter(str(row.get("charge", "")) for row in profile_rows)
    state_category_counts = Counter(str(row.get("state_category", "")) for row in profile_rows)
    qa_profile_count = 0
    electron_errors: list[float] = []
    angular_sigmas: list[float] = []
    linear_warning_count = 0
    linear_vectors: list[int] = []
    for row in profile_rows:
        err = _float_or_none(row.get("electron_count_error_qa"))
        sigma = _float_or_none(row.get("max_rel_angular_sigma"))
        if err is not None:
            electron_errors.append(abs(err))
        if sigma is not None:
            angular_sigmas.append(sigma)
        if err is not None and sigma is not None:
            qa_profile_count += 1
        linear_warning_count += _int_or_none(row.get("linear_dependency_warning_count")) or 0
        vectors = _int_or_none(row.get("linear_dependency_vectors_removed"))
        if vectors is not None:
            linear_vectors.append(vectors)

    if profile_index_rows and qa_profile_count < profile_index_rows:
        warnings.append(
            f"{dataset_id}: only {qa_profile_count}/{profile_index_rows} profiles have full QA fields"
        )

    return ReleaseDatasetReport(
        dataset_id=dataset_id,
        expected_profile_count=expected_profile_count,
        manifest_profile_count=manifest_profile_count,
        profile_index_rows=profile_index_rows,
        derived_radii_rows=derived_radii_rows,
        metadata_file_count=metadata_file_count,
        profile_file_count=profile_file_count,
        charge_counts=dict(sorted(charge_counts.items())),
        state_category_counts=dict(sorted(state_category_counts.items())),
        qa_profile_count=qa_profile_count,
        max_abs_electron_count_error=max(electron_errors) if electron_errors else None,
        max_rel_angular_sigma=max(angular_sigmas) if angular_sigmas else None,
        linear_dependency_warning_count=linear_warning_count,
        max_linear_dependency_vectors_removed=max(linear_vectors) if linear_vectors else None,
    )


def check_release_package(
    archive_path: Path,
    *,
    expected_dataset_ids: tuple[str, ...] = (),
    require_hashes: bool = True,
    require_dataset_indexes: bool = False,
    expected_profile_counts: dict[str, int] | None = None,
) -> ReleasePackageCheckResult:
    """Validate a release-candidate ZIP archive manifest and dataset indexes."""

    errors: list[str] = []
    warnings: list[str] = []
    dataset_ids: tuple[str, ...] = ()
    file_count = 0
    total_size_bytes = 0
    dataset_reports: list[ReleaseDatasetReport] = []
    expected_profile_counts = expected_profile_counts or {}

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
                    tuple(dataset_reports),
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
                    tuple(dataset_reports),
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
                    tuple(dataset_reports),
                )
            if manifest.get("schema_version") != RELEASE_PACKAGE_SCHEMA_VERSION:
                errors.append(
                    f"manifest schema_version={manifest.get('schema_version')!r} "
                    f"!= {RELEASE_PACKAGE_SCHEMA_VERSION!r}"
                )
            archive_root = str(manifest.get("archive_root") or DEFAULT_ARCHIVE_ROOT).strip("/")
            dataset_ids = tuple(str(item) for item in manifest.get("dataset_ids", ()))
            expected_set = set(expected_dataset_ids)
            if expected_set and set(dataset_ids) != expected_set:
                errors.append(
                    f"manifest dataset_ids {sorted(dataset_ids)} != expected "
                    f"{sorted(expected_dataset_ids)}"
                )
            datasets_summary = manifest.get("datasets")
            if datasets_summary is not None and not isinstance(datasets_summary, list):
                errors.append("manifest.datasets must be a list when present")
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
                    actual_sha = hashlib.sha256(payload).hexdigest()
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

            if require_dataset_indexes or expected_profile_counts:
                for dataset_id in dataset_ids:
                    dataset_reports.append(
                        _dataset_report_from_archive(
                            zip_handle,
                            names=names,
                            archive_root=archive_root,
                            dataset_id=dataset_id,
                            expected_profile_count=expected_profile_counts.get(dataset_id),
                            errors=errors,
                            warnings=warnings,
                        )
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
        dataset_reports=tuple(dataset_reports),
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


def _format_optional_float(value: float | None) -> str:
    return "<none>" if value is None else f"{value:.6g}"


def format_release_package_check(result: ReleasePackageCheckResult, *, summary: bool = False) -> str:
    """Format a release package check result as deterministic text."""

    status = "OK" if result.ok else "FAILED"
    lines = [
        f"Status: {status}",
        f"Archive: {result.archive_path}",
        f"Datasets: {', '.join(result.dataset_ids) if result.dataset_ids else '<none>'}",
        f"Files checked: {result.file_count}",
        f"Total payload size: {result.total_size_bytes} bytes",
    ]
    if summary and result.dataset_reports:
        lines.append("Dataset summaries:")
        for report in result.dataset_reports:
            expected = (
                "<not checked>"
                if report.expected_profile_count is None
                else str(report.expected_profile_count)
            )
            lines.append(
                f"  {report.dataset_id}: profiles={report.manifest_profile_count}, "
                f"expected={expected}, index_rows={report.profile_index_rows}, "
                f"derived_rows={report.derived_radii_rows}"
            )
            lines.append(
                "    files: "
                f"profiles={report.profile_file_count}, metadata={report.metadata_file_count}; "
                f"QA={report.qa_profile_count}/{report.profile_index_rows}"
            )
            lines.append(
                "    max QA: "
                f"|electron_count_error|={_format_optional_float(report.max_abs_electron_count_error)}, "
                f"angular_sigma={_format_optional_float(report.max_rel_angular_sigma)}"
            )
            lines.append(
                "    linear dependency: "
                f"warnings={report.linear_dependency_warning_count}, "
                f"max_removed={report.max_linear_dependency_vectors_removed}"
            )
            lines.append(
                "    charges: "
                + ", ".join(
                    f"{charge}={count}" for charge, count in report.charge_counts.items()
                )
            )
            lines.append(
                "    categories: "
                + ", ".join(
                    f"{category}={count}"
                    for category, count in report.state_category_counts.items()
                )
            )
    if result.errors:
        lines.append("Errors:")
        lines.extend(f"  - {item}" for item in result.errors)
    if result.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {item}" for item in result.warnings)
    return "\n".join(lines)
