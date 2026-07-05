# Quality-assurance tables

This directory is the target location for release-gate QA artifacts for the
generated spherical proatomic profile datasets. No final v2 QA tables are
committed in this preparation snapshot.

The old neutral-only v1 QA artifacts were removed from the active tree; v1
remains available from historical tags/releases/archives.

The QA layer checks that each generated density table is numerically finite,
integrates to the expected electron count within the configured tolerance,
remains sufficiently spherical on an angular test grid, and produces consistent
cutoff radii.

## Layout after generation

Generated QA artifacts live under:

```text
data/qa/<dataset_id>/
  qa.csv
  metadata.json

data/qa/qa_summary.csv
data/qa/qa_report.md
data/qa/metadata.json

data/qa/basis_sensitivity/
  basis_sensitivity.csv
  basis_sensitivity_summary.csv
  basis_sensitivity_outliers.csv
  basis_sensitivity_metric_distributions.csv
  metadata.json
  dyall-v4z/
    basis_sensitivity.csv
    basis_sensitivity_summary.csv
    basis_sensitivity_outliers.csv
    basis_sensitivity_metric_distributions.csv
  x2c-QZVPall/                         # only with --include-x2c-optional
    basis_sensitivity.csv
    basis_sensitivity_summary.csv
    basis_sensitivity_outliers.csv
    basis_sensitivity_metric_distributions.csv
```

Per-dataset `qa.csv` files contain one row per generated state. The top-level
summary and Markdown report aggregate dataset-level pass/fail status. The
optional `basis_sensitivity/` tables compare primary and diffuse anion basis
branches where both generated profile datasets are present; their warning rows
are diagnostics, not automatic release failures. Pair-specific basis-sensitivity
files are stored in subdirectories named after the base/basic basis set. The
root-level files are aggregate compatibility outputs.

## QA metrics

### SCF completion

`scf_converged` records the convergence flag stored in the local SCF metadata.
Profile extraction requires complete local SCF artifacts for every selected
state/dataset job.

### Electron-count integral

`electron_count_error_qa` is the difference between the independently integrated
density and the expected electron count of the curated state. The tolerance is
reported as `electron_count_tolerance`. The corresponding boolean field is
`electron_count_pass`.

### Finite and physical profile values

Profile generation rejects non-finite density values. Electron-density profiles
are expected to be non-negative on the stored grid.

### Radial grid and tail coverage

The radial grid is defined in `data/profile_datasets.yaml`. QA verifies that the
profile reaches the smallest configured density cutoff in the outer radial tail;
this is recorded as `tail_reaches_min_cutoff`.

### Cutoff-radius consistency

`radii_monotonic` verifies that lower density cutoffs produce radii that are not
smaller than higher density cutoffs.

### Angular/spherical consistency

`max_rel_angular_sigma` measures the largest relative angular variation observed
on the angular QA grid. The corresponding tolerance is reported as
`max_rel_angular_sigma_tolerance`, and the boolean result is `angular_sigma_pass`.

### Linear-dependency diagnostics

`linear_dependency_warning_count` and `linear_dependency_vectors_removed` are
parsed from SCF logs when PySCF reports basis-set linear-dependency handling.
These fields are diagnostics rather than automatic release failures.

### Diffuse-basis sensitivity

`basis_sensitivity/basis_sensitivity.csv` is the aggregate compatibility table.
The default pair-specific table is
`basis_sensitivity/dyall-v4z/basis_sensitivity.csv`, comparing `dyall-v4z` with
`dyall-av4z`. If `check_basis_sensitivity.py --include-x2c-optional` is used,
the secondary diagnostic pair is written to
`basis_sensitivity/x2c-QZVPall/basis_sensitivity.csv`. These tables compare
radial densities for matched states in the configured primary/diffuse anion
branches. They record integrated L1 density differences, electron-count deltas,
electron-quantile radius shifts, cutoff-radius shifts, and tail-electron
differences. Rows marked `WARN` are outliers for manual inspection; they do not
make `check_profile_artifacts.py` fail by themselves.

## Regeneration

QA tables are generated artifacts and should not be hand-edited. They are
regenerated together with profiles and radii, then checked for active-dataset
consistency, by:

```bash
python scripts/extract_profiles.py --force --check
python scripts/check_basis_sensitivity.py --force
python scripts/check_profile_artifacts.py --require-generated
```

The compact report in `qa_report.md`, together with
`check_profile_artifacts.py --require-generated`, is the primary release-gate
summary after a profile generation run.

## Related documentation

- Independent electron-count QA model: `docs/theory.md`.
- Released artifact contract: `docs/data.md`.
- Regeneration workflow: `docs/workflow.md`.
