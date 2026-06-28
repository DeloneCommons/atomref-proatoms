"""Checks and summaries for local pilot-output roots."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .dataset_index import check_profile_dataset_with_indexes
from .dataset_summary import format_dataset_summary, summarize_dataset_indexes
from .datasets import dataset_scope
from .pilots import PilotProfile, get_pilot_group, pilot_group_names
from .qa import ELECTRON_COUNT_ABS_TOL, ELECTRON_COUNT_REL_TOL


@dataclass(frozen=True)
class PilotOutputCheckResult:
    """Result of checking one local pilot-output root."""

    output_dir: Path
    group_names: tuple[str, ...]
    expected_state_ids_by_dataset: dict[str, tuple[str, ...]]
    checked_dataset_ids: tuple[str, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    summaries: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def pilots_for_groups(group_names: tuple[str, ...]) -> tuple[PilotProfile, ...]:
    """Return pilots from one or more groups, preserving group/order."""

    pilots: list[PilotProfile] = []
    seen: set[tuple[str, str]] = set()
    for group_name in group_names:
        for pilot in get_pilot_group(group_name):
            key = (pilot.state_id, pilot.dataset_id)
            if key in seen:
                continue
            seen.add(key)
            pilots.append(pilot)
    return tuple(pilots)


def expected_state_ids_by_dataset(group_names: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """Return expected pilot state IDs grouped by target dataset ID."""

    grouped: dict[str, list[str]] = {}
    for pilot in pilots_for_groups(group_names):
        grouped.setdefault(pilot.dataset_id, []).append(pilot.state_id)
    return {dataset_id: tuple(state_ids) for dataset_id, state_ids in sorted(grouped.items())}


def _dataset_state_ids_from_metadata(dataset_dir: Path) -> set[str]:
    metadata_dir = dataset_dir / "metadata"
    if not metadata_dir.is_dir():
        return set()
    return {path.stem for path in metadata_dir.glob("*.json")}


def _unexpected_dataset_dirs(output_dir: Path, expected_dataset_ids: set[str]) -> tuple[str, ...]:
    if not output_dir.exists():
        return ()
    unexpected: list[str] = []
    for path in sorted(output_dir.iterdir()):
        if not path.is_dir() or path.name in expected_dataset_ids:
            continue
        if (path / "metadata").exists() or (path / "profiles").exists():
            unexpected.append(path.name)
    return tuple(unexpected)


def check_pilot_output_root(
    output_dir: Path,
    *,
    group_names: tuple[str, ...],
    states_file: Path | None = None,
    basis_root: Path | None = None,
    require_profile_qa: bool = False,
    angular_sigma_tol: float = 1.0e-8,
    electron_count_abs_tol: float = ELECTRON_COUNT_ABS_TOL,
    electron_count_rel_tol: float = ELECTRON_COUNT_REL_TOL,
    require_indexes: bool = True,
    allow_missing: bool = False,
    include_summaries: bool = False,
) -> PilotOutputCheckResult:
    """Check generated pilot outputs for the selected pilot groups.

    The check is intentionally stricter than a blind directory scan: it verifies
    that each selected pilot state appears in the expected dataset directory.
    This helps keep the primary non-diffuse and diffuse anion/sensitivity pilot
    outputs separate.
    """

    if not group_names:
        group_names = pilot_group_names()
    expected = expected_state_ids_by_dataset(group_names)
    expected_dataset_ids = set(expected)
    errors: list[str] = []
    warnings: list[str] = []
    summaries: list[str] = []
    checked: list[str] = []

    for dataset_id, expected_state_ids in expected.items():
        dataset_dir = output_dir / dataset_id
        scope = dataset_scope(dataset_id)
        if not dataset_dir.exists():
            message = (
                f"missing dataset directory for {dataset_id} "
                f"({scope.role}, {scope.coverage_label}): {dataset_dir}"
            )
            if allow_missing:
                warnings.append(message)
                continue
            errors.append(message)
            continue

        present_state_ids = _dataset_state_ids_from_metadata(dataset_dir)
        missing_state_ids = sorted(set(expected_state_ids) - present_state_ids)
        if missing_state_ids:
            errors.append(
                f"{dataset_id}: missing expected pilot states {missing_state_ids}; "
                f"present={sorted(present_state_ids)}"
            )

        profile_result, index_result = check_profile_dataset_with_indexes(
            dataset_dir,
            states_file=states_file,
            basis_root=basis_root,
            require_profile_qa=require_profile_qa,
            angular_sigma_tol=angular_sigma_tol,
            electron_count_abs_tol=electron_count_abs_tol,
            electron_count_rel_tol=electron_count_rel_tol,
            require_indexes=require_indexes,
        )
        checked.append(dataset_id)
        errors.extend(f"{dataset_id}: {item}" for item in profile_result.errors)
        warnings.extend(f"{dataset_id}: {item}" for item in profile_result.warnings)
        if index_result is not None:
            errors.extend(f"{dataset_id}: {item}" for item in index_result.errors)
            warnings.extend(f"{dataset_id}: {item}" for item in index_result.warnings)
        index_errors = index_result.errors if index_result is not None else ()
        if include_summaries and not profile_result.errors and not index_errors:
            try:
                summaries.append(format_dataset_summary(summarize_dataset_indexes(dataset_dir)))
            except Exception as exc:  # pragma: no cover - defensive reporting path
                warnings.append(f"{dataset_id}: could not summarize dataset indexes: {exc}")

    unexpected = _unexpected_dataset_dirs(output_dir, expected_dataset_ids)
    for dataset_id in unexpected:
        warnings.append(
            f"unexpected generated dataset directory not selected by requested pilot groups: "
            f"{dataset_id}"
        )

    return PilotOutputCheckResult(
        output_dir=output_dir,
        group_names=group_names,
        expected_state_ids_by_dataset=expected,
        checked_dataset_ids=tuple(sorted(checked)),
        errors=tuple(errors),
        warnings=tuple(warnings),
        summaries=tuple(summaries),
    )


def format_pilot_output_check(result: PilotOutputCheckResult) -> str:
    """Format a pilot-output-root check result as deterministic text."""

    lines = [
        f"Pilot output root: {result.output_dir}",
        f"Groups: {', '.join(result.group_names)}",
        "Expected pilot states:",
    ]
    for dataset_id, state_ids in result.expected_state_ids_by_dataset.items():
        scope = dataset_scope(dataset_id)
        lines.append(
            f"  {dataset_id} ({scope.role}, {scope.coverage_label}): "
            f"{', '.join(state_ids)}"
        )
    lines.append(
        "Checked datasets: "
        f"{', '.join(result.checked_dataset_ids) if result.checked_dataset_ids else '<none>'}"
    )
    if result.errors:
        lines.append("Errors:")
        lines.extend(f"  - {item}" for item in result.errors)
    if result.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {item}" for item in result.warnings)
    if result.summaries:
        lines.append("Dataset summaries:")
        for summary in result.summaries:
            lines.append(summary)
    lines.append("Status: OK" if result.ok else "Status: FAILED")
    return "\n".join(lines)
