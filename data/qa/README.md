# Quality-assurance tables

This directory stores release-gate QA artifacts for the generated spherical
proatomic profile datasets.

The QA layer checks that each generated density table is numerically finite,
integrates to the expected electron count within the configured tolerance,
remains sufficiently spherical on an angular test grid, and produces consistent
cutoff radii.

## Layout

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
  x2c-QZVPall/                         # emitted with --include-x2c-optional
    basis_sensitivity.csv
    basis_sensitivity_summary.csv
    basis_sensitivity_outliers.csv
    basis_sensitivity_metric_distributions.csv
```

Per-dataset `qa.csv` files contain one row per generated state. The top-level
summary and Markdown report aggregate dataset-level pass/fail status. The
`basis_sensitivity/` tables compare primary and diffuse/supplemented anion basis
branches where both generated profile datasets are present; their warning rows
are diagnostics, not automatic release failures. Pair-specific basis-sensitivity
files are stored in subdirectories named after the base/basic basis set. The
root-level files are aggregate compatibility outputs.

## Current generated status

| dataset ID | rows | failed rows | linear-dependency warning count |
|---|---:|---:|---:|
| `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2` | 430 | 0 | 0 |
| `pbe0_sfx2c_dyallv4z_h-lr_spherical_v2` | 501 | 0 | 266 |
| `pbe0_sfx2c_x2cqzvpalls_h-rn_anions_spherical_v2` | 106 | 0 | 19 |
| `pbe0_sfx2c_dyallav4z_h-ba_hf-ra_anions_spherical_v2` | 91 | 0 | 36 |

The top-level QA metadata records four generated datasets, 1128 dataset-state
rows, and zero release-gate failures.

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
The primary pair-specific table is
`basis_sensitivity/dyall-v4z/basis_sensitivity.csv`, comparing `dyall-v4z` with
`dyall-av4z`. If `check_basis_sensitivity.py --include-x2c-optional` is used,
the secondary diagnostic pair is written to
`basis_sensitivity/x2c-QZVPall/basis_sensitivity.csv`. The current generated
basis-sensitivity layer includes both comparisons.

These tables compare radial densities for matched states in the configured
primary/diffuse anion branches. They record integrated L1 density differences,
electron-count deltas, electron-quantile radius shifts, cutoff-radius shifts,
tail-electron differences, and cumulative electron-count distribution metrics.
Rows marked with high sensitivity are outliers for manual inspection; they do
not make `check_profile_artifacts.py` fail by themselves.

Current basis-sensitivity counts:

```text
dyall-v4z vs dyall-av4z:
  rows: 91
  high-sensitivity outliers: 14
  release-gate failures: 0

x2c-QZVPall vs x2c-QZVPall-s:
  rows: 106
  high-sensitivity outliers: 0
  release-gate failures: 0
```

## Regeneration

QA tables are generated artifacts and should not be hand-edited. They are
regenerated together with profiles and radii, then checked for active-dataset
consistency, by:

```bash
python scripts/extract_profiles.py --force --check
python scripts/check_basis_sensitivity.py --include-x2c-optional --force
python scripts/check_profile_artifacts.py --require-generated
```

The compact report in `qa_report.md`, together with
`check_profile_artifacts.py --require-generated`, is the primary release-gate
summary after a profile generation run.

## Related documentation

- Independent electron-count QA model: `docs/theory.md`.
- Released artifact contract: `docs/data.md`.
- Regeneration workflow: `docs/workflow.md`.
