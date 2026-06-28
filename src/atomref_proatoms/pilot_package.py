"""Package generated local pilot outputs for external review."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .pilot_outputs import expected_state_ids_by_dataset
from .pilots import FULL_PILOT_SUITE


@dataclass(frozen=True)
class PilotOutputPackageResult:
    """Result of creating a ZIP archive from local pilot outputs."""

    output_dir: Path
    archive_path: Path
    group_names: tuple[str, ...]
    dataset_ids: tuple[str, ...]
    file_count: int
    warnings: tuple[str, ...]


def default_pilot_archive_path(output_dir: Path, group_names: tuple[str, ...]) -> Path:
    """Return a default archive path outside the pilot-output root."""

    group_label = "_".join(group_names) if group_names else FULL_PILOT_SUITE
    return output_dir.parent / f"{output_dir.name}-{group_label}.zip"


def _iter_dataset_files(dataset_dir: Path) -> tuple[Path, ...]:
    files = [path for path in dataset_dir.rglob("*") if path.is_file()]
    return tuple(sorted(files, key=lambda path: path.relative_to(dataset_dir).as_posix()))


def package_pilot_outputs(
    output_dir: Path,
    archive_path: Path,
    *,
    group_names: tuple[str, ...],
    allow_missing: bool = False,
) -> PilotOutputPackageResult:
    """Write a ZIP archive containing selected pilot-output dataset directories.

    Only dataset directories expected from the selected pilot groups are included.  The
    archive layout is rooted at dataset IDs, for example
    ``pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0/metadata/H_q0_mult2_hund.json``.
    """

    output_dir = output_dir.resolve()
    archive_path = archive_path.resolve()
    expected = expected_state_ids_by_dataset(group_names)
    warnings: list[str] = []
    dataset_ids: list[str] = []
    file_count = 0

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as zip_handle:
        for dataset_id in sorted(expected):
            dataset_dir = output_dir / dataset_id
            if not dataset_dir.is_dir():
                message = f"missing selected pilot dataset directory: {dataset_dir}"
                if allow_missing:
                    warnings.append(message)
                    continue
                raise FileNotFoundError(message)
            dataset_files = _iter_dataset_files(dataset_dir)
            if not dataset_files:
                message = f"selected pilot dataset directory is empty: {dataset_dir}"
                if allow_missing:
                    warnings.append(message)
                    continue
                raise FileNotFoundError(message)
            dataset_ids.append(dataset_id)
            for file_path in dataset_files:
                if file_path.resolve() == archive_path:
                    continue
                arcname = Path(dataset_id) / file_path.relative_to(dataset_dir)
                zip_handle.write(file_path, arcname.as_posix())
                file_count += 1

    return PilotOutputPackageResult(
        output_dir=output_dir,
        archive_path=archive_path,
        group_names=group_names,
        dataset_ids=tuple(dataset_ids),
        file_count=file_count,
        warnings=tuple(warnings),
    )


def format_pilot_output_package(result: PilotOutputPackageResult) -> str:
    """Format a packaging result as deterministic text."""

    lines = [
        f"Pilot output root: {result.output_dir}",
        f"Archive: {result.archive_path}",
        f"Groups: {', '.join(result.group_names)}",
        f"Datasets: {', '.join(result.dataset_ids) if result.dataset_ids else '<none>'}",
        f"Files packaged: {result.file_count}",
    ]
    if result.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {item}" for item in result.warnings)
    return "\n".join(lines)
