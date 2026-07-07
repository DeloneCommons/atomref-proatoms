"""Planning and manifest helpers for Multiwfn interoperability exports."""

from __future__ import annotations

import json
import platform
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..dataio.datasets import DATASET_IDS, ProfileDatasetConfig, dataset_scope
from ..dataio.paths import repo_relative_path
from ..profiles.artifacts import write_json
from ..profiles.build_plan import ProfileBuildJob, build_jobs_for_datasets
from ..states.state_tables import AtomState
from .multiwfn_rad import multiwfn_rad_filename
from .proaim_wfn import atom_wfn_filename

MULTIWFN_ARTIFACT_MANIFEST_SCHEMA_VERSION = "atomref.proatoms.multiwfn_artifacts.v1"
ALL_MULTIWFN_ARTIFACT_DATASETS = "all"


@dataclass(frozen=True)
class MultiwfnArtifactJob:
    """One configured Multiwfn interoperability export."""

    state_id: str
    dataset_id: str
    symbol: str
    z: int
    charge: int
    electron_count: int
    multiplicity: int
    state_category: str
    basis_id: str
    rad_requested: bool
    wfn_requested: bool

    @property
    def charge_class(self) -> str:
        if self.charge == 0:
            return "neutral"
        if self.charge > 0:
            return "cation"
        return "anion"

    @property
    def rad_filename(self) -> str:
        return multiwfn_rad_filename(self.symbol, self.charge)

    @property
    def wfn_filename(self) -> str:
        return atom_wfn_filename(self.symbol)


def _job_from_profile_job(
    job: ProfileBuildJob,
    *,
    config: ProfileDatasetConfig | None = None,
    include_rad: bool = True,
    include_wfn: bool = True,
) -> MultiwfnArtifactJob | None:
    scope = dataset_scope(job.dataset_id, config=config)
    rad_requested = bool(include_rad and scope.allows_multiwfn_rad(charge=job.charge))
    wfn_requested = bool(include_wfn and scope.allows_multiwfn_wfn(charge=job.charge))
    if not rad_requested and not wfn_requested:
        return None
    return MultiwfnArtifactJob(
        state_id=job.state_id,
        dataset_id=job.dataset_id,
        symbol=job.symbol,
        z=job.z,
        charge=job.charge,
        electron_count=job.electron_count,
        multiplicity=job.multiplicity,
        state_category=job.state_category,
        basis_id=job.basis_id,
        rad_requested=rad_requested,
        wfn_requested=wfn_requested,
    )


def build_multiwfn_artifact_jobs(
    states: list[AtomState],
    dataset_ids: tuple[str, ...] = DATASET_IDS,
    *,
    config: ProfileDatasetConfig | None = None,
    include_rad: bool = True,
    include_wfn: bool = True,
) -> tuple[MultiwfnArtifactJob, ...]:
    """Return ordered Multiwfn export jobs from the active dataset policy."""

    jobs: list[MultiwfnArtifactJob] = []
    for profile_job in build_jobs_for_datasets(states, dataset_ids=dataset_ids, config=config):
        job = _job_from_profile_job(
            profile_job,
            config=config,
            include_rad=include_rad,
            include_wfn=include_wfn,
        )
        if job is not None:
            jobs.append(job)
    return tuple(jobs)


def filter_multiwfn_artifact_jobs(
    jobs: tuple[MultiwfnArtifactJob, ...], *, only_state_ids: set[str] | None = None
) -> tuple[MultiwfnArtifactJob, ...]:
    """Filter export jobs by state ID while preserving order."""

    if not only_state_ids:
        return jobs
    selected = tuple(job for job in jobs if job.state_id in only_state_ids)
    present = {job.state_id for job in jobs}
    missing = sorted(only_state_ids - present)
    if missing:
        raise ValueError(
            f"Requested states are not in the selected Multiwfn export plan: {missing}"
        )
    return selected


def multiwfn_artifact_plan_summary(jobs: Sequence[MultiwfnArtifactJob]) -> dict[str, Any]:
    """Return compact counts for a Multiwfn export plan."""

    by_dataset: dict[str, dict[str, int]] = {}
    by_charge_class: dict[str, int] = {"neutral": 0, "cation": 0, "anion": 0}
    for job in jobs:
        rec = by_dataset.setdefault(job.dataset_id, {"rad": 0, "wfn": 0, "total": 0})
        rec["total"] += 1
        if job.rad_requested:
            rec["rad"] += 1
        if job.wfn_requested:
            rec["wfn"] += 1
        by_charge_class[job.charge_class] += 1
    return {
        "job_count": len(jobs),
        "rad_file_count": sum(1 for job in jobs if job.rad_requested),
        "wfn_file_count": sum(1 for job in jobs if job.wfn_requested),
        "by_dataset": dict(sorted(by_dataset.items())),
        "by_charge_class": by_charge_class,
    }


def format_multiwfn_artifact_plan(
    jobs: Sequence[MultiwfnArtifactJob],
    *,
    show_jobs: bool = False,
    config: ProfileDatasetConfig | None = None,
) -> str:
    """Format a deterministic export-plan summary."""

    summary = multiwfn_artifact_plan_summary(jobs)
    lines = [
        f"Multiwfn export jobs: {summary['job_count']}",
        f".rad files: {summary['rad_file_count']}",
        f".wfn files: {summary['wfn_file_count']}",
        "Datasets:",
    ]
    by_dataset = summary["by_dataset"]
    assert isinstance(by_dataset, dict)
    for dataset_id, counts in by_dataset.items():
        scope = dataset_scope(str(dataset_id), config=config)
        lines.append(
            f"  {dataset_id}: rad={counts['rad']}, wfn={counts['wfn']}  "
            f"# {scope.basis_id}; rad={scope.multiwfn_rad}, wfn={scope.multiwfn_wfn}"
        )
    charge_counts = summary["by_charge_class"]
    assert isinstance(charge_counts, dict)
    lines.append(
        "Charge classes: "
        + ", ".join(f"{name}={charge_counts[name]}" for name in ("neutral", "cation", "anion"))
    )
    if show_jobs:
        lines.append("Jobs:")
        for job in jobs:
            outputs = []
            if job.rad_requested:
                outputs.append(job.rad_filename)
            if job.wfn_requested:
                outputs.append(job.wfn_filename)
            lines.append(
                f"  {job.dataset_id}: {job.state_id} "
                f"({job.symbol}, Z={job.z}, charge={job.charge}, mult={job.multiplicity}) "
                f"-> {', '.join(outputs)}"
            )
    return "\n".join(lines)


def manifest_payload(
    *,
    output_root: Path,
    profile_data_version: str,
    config_path: Path,
    jobs: Sequence[MultiwfnArtifactJob],
    files: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a manifest payload for one local Multiwfn export run."""

    summary = multiwfn_artifact_plan_summary(jobs)
    return {
        "schema_version": MULTIWFN_ARTIFACT_MANIFEST_SCHEMA_VERSION,
        "profile_data_version": profile_data_version,
        "config": repo_relative_path(config_path),
        "output_root": repo_relative_path(output_root),
        "generated_by": "scripts/export_multiwfn_artifacts.py",
        "python_version": platform.python_version(),
        "summary": summary,
        "files": list(files),
        "notes": {
            "rad": "Density-only Multiwfn .rad files interpolated from released profiles.",
            "wfn": "PROAIM WFN interoperability files generated from local SCF arrays/checkpoints.",
            "internal_data_path": (
                "Project-native NPZ and profile artifacts remain the efficient package "
                "data path."
            ),
        },
    }


def write_multiwfn_manifest(
    path: Path,
    *,
    output_root: Path,
    profile_data_version: str,
    config_path: Path,
    jobs: Sequence[MultiwfnArtifactJob],
    files: Sequence[Mapping[str, Any]],
) -> Path:
    """Write a strict JSON manifest for generated Multiwfn interoperability files."""

    write_json(
        path,
        manifest_payload(
            output_root=output_root,
            profile_data_version=profile_data_version,
            config_path=config_path,
            jobs=jobs,
            files=files,
        ),
    )
    return path


def read_multiwfn_manifest(path: Path | str) -> dict[str, Any]:
    """Read a Multiwfn artifact manifest."""

    return json.loads(Path(path).read_text(encoding="utf-8"))
