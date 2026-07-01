"""Profile build plans derived from curated states and the active dataset YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .datasets import DATASET_IDS, ProfileDatasetConfig, dataset_scope
from .states import AtomState, load_atom_states

ALL_PROFILE_DATASETS = "all"
ALL_V1_BUILD_PLAN = "all_v1"


@dataclass(frozen=True)
class ProfileBuildJob:
    """One state/dataset pair configured for profile generation."""

    state_id: str
    dataset_id: str
    symbol: str
    z: int
    charge: int
    electron_count: int
    multiplicity: int
    state_category: str
    basis_id: str
    dataset_role: str
    dataset_coverage_label: str

    @property
    def charge_class(self) -> str:
        if self.charge == 0:
            return "neutral"
        if self.charge > 0:
            return "cation"
        return "anion"


def build_jobs_for_dataset(
    states: list[AtomState], dataset_id: str, *, config: ProfileDatasetConfig | None = None
) -> tuple[ProfileBuildJob, ...]:
    """Return ordered build jobs for one configured dataset.

    Membership is derived from the current curated state selection plus the
    dataset scope table.  This keeps basis coverage, charge class, and
    sensitivity datasets explicit instead of allowing runtime fallback.
    """

    scope = dataset_scope(dataset_id, config=config)
    jobs: list[ProfileBuildJob] = []
    for state in states:
        if not (
            scope.covers_z(state.z)
            and scope.allows_charge(state.charge)
            and str(state.record["state_role"]) in scope.include_state_roles
        ):
            continue
        jobs.append(
            ProfileBuildJob(
                state_id=state.state_id,
                dataset_id=dataset_id,
                symbol=state.symbol,
                z=state.z,
                charge=state.charge,
                electron_count=state.electron_count,
                multiplicity=state.multiplicity,
                state_category=state.state_category,
                basis_id=scope.basis_id,
                dataset_role=scope.role,
                dataset_coverage_label=scope.coverage_label,
            )
        )
    return tuple(jobs)


def build_jobs_for_datasets(
    states: list[AtomState],
    dataset_ids: tuple[str, ...] = DATASET_IDS,
    *,
    config: ProfileDatasetConfig | None = None,
) -> tuple[ProfileBuildJob, ...]:
    """Return ordered build jobs for multiple datasets."""

    jobs: list[ProfileBuildJob] = []
    for dataset_id in dataset_ids:
        jobs.extend(build_jobs_for_dataset(states, dataset_id, config=config))
    return tuple(jobs)


def load_build_jobs(
    states_file: Path,
    *,
    dataset_ids: tuple[str, ...] = DATASET_IDS,
    config: ProfileDatasetConfig | None = None,
) -> tuple[ProfileBuildJob, ...]:
    """Load curated states and return planned build jobs."""

    return build_jobs_for_datasets(
        load_atom_states(states_file), dataset_ids=dataset_ids, config=config
    )


def filter_build_jobs(
    jobs: tuple[ProfileBuildJob, ...], *, only_state_ids: set[str] | None = None
) -> tuple[ProfileBuildJob, ...]:
    """Filter jobs by state ID while preserving original order."""

    if not only_state_ids:
        return jobs
    selected = tuple(job for job in jobs if job.state_id in only_state_ids)
    present = {job.state_id for job in jobs}
    missing = sorted(only_state_ids - present)
    if missing:
        raise ValueError(f"Requested states are not in the selected build plan: {missing}")
    return selected


def build_plan_summary(jobs: tuple[ProfileBuildJob, ...]) -> dict[str, object]:
    """Return compact counts for a set of build jobs."""

    by_dataset: dict[str, int] = {}
    by_charge_class: dict[str, int] = {"neutral": 0, "cation": 0, "anion": 0}
    for job in jobs:
        by_dataset[job.dataset_id] = by_dataset.get(job.dataset_id, 0) + 1
        by_charge_class[job.charge_class] += 1
    return {
        "job_count": len(jobs),
        "by_dataset": dict(sorted(by_dataset.items())),
        "by_charge_class": by_charge_class,
    }


def format_build_plan(
    jobs: tuple[ProfileBuildJob, ...],
    *,
    show_jobs: bool = False,
    config: ProfileDatasetConfig | None = None,
) -> str:
    """Format a build plan as deterministic text."""

    summary = build_plan_summary(jobs)
    lines = [
        f"Build jobs: {summary['job_count']}",
        "Datasets:",
    ]
    by_dataset = summary["by_dataset"]
    assert isinstance(by_dataset, dict)
    for dataset_id, count in by_dataset.items():
        scope = dataset_scope(str(dataset_id), config=config)
        lines.append(f"  {dataset_id}: {count}  # {scope.role}, {scope.coverage_label}")
    charge_counts = summary["by_charge_class"]
    assert isinstance(charge_counts, dict)
    lines.append(
        "Charge classes: "
        + ", ".join(f"{name}={charge_counts[name]}" for name in ("neutral", "cation", "anion"))
    )
    if show_jobs:
        lines.append("Jobs:")
        for job in jobs:
            lines.append(
                f"  {job.dataset_id}: {job.state_id} "
                f"({job.symbol}, Z={job.z}, charge={job.charge}, mult={job.multiplicity})"
            )
    return "\n".join(lines)
