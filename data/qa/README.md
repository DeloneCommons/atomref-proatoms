# Quality-assurance tables

This directory contains release-gate QA artifacts for the generated spherical
proatomic profile datasets. The QA layer checks that each generated density table
is numerically finite, integrates to the expected electron count within the
configured tolerance, remains sufficiently spherical on an angular test grid, and
produces consistent cutoff radii.

## Layout

Generated QA artifacts live under:

```text
data/qa/<dataset_id>/
  qa.csv
  metadata.json

data/qa/qa_summary.csv
data/qa/qa_report.md
data/qa/metadata.json
```

Per-dataset `qa.csv` files contain one row per generated state. The top-level
summary and Markdown report aggregate dataset-level pass/fail status.

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

This check verifies that the radial profile and the independent QA grid represent
the intended number of electrons and that no large density normalization error was
introduced during extraction.

### Finite and physical profile values

Profile generation rejects non-finite density values. Electron-density profiles
are expected to be non-negative on the stored grid. These checks protect the
released CSV tables from invalid floating-point payloads and numerical failures.

### Radial grid and tail coverage

The radial grid is defined in `data/profile_datasets.yaml`. QA verifies that the
profile reaches the smallest configured density cutoff in the outer radial tail;
this is recorded as `tail_reaches_min_cutoff`. The check ensures that cutoff
radii are not extrapolated beyond the stored grid.

### Cutoff-radius consistency

`radii_monotonic` verifies that lower density cutoffs produce radii that are not
smaller than higher density cutoffs. This is a compact consistency check for the
reported radius table and the outer profile tail.

### Angular/spherical consistency

`max_rel_angular_sigma` measures the largest relative angular variation observed
on the angular QA grid. The corresponding tolerance is reported as
`max_rel_angular_sigma_tolerance`, and the boolean result is
`angular_sigma_pass`.

This check is included because the released objects are spherical proatomic
reference densities. It detects accidental anisotropy or orbital-occupation
problems that would be hidden by a purely radial table.

### Linear-dependency diagnostics

`linear_dependency_warning_count` and `linear_dependency_vectors_removed` are
parsed from SCF logs when PySCF reports basis-set linear-dependency handling.
These fields are diagnostics rather than automatic release failures. They are
reported because near-linear dependencies may affect numerical stability,
especially in large heavy-element basis sets.

A dataset may still pass release QA with linear-dependency warnings if the SCF
artifacts are complete and the extracted density profiles pass electron-count,
finite-density, angular-sphericity, tail-coverage, and cutoff-radius checks.

## Regeneration

QA tables are generated artifacts and should not be hand-edited. They are
regenerated together with profiles and radii by:

```bash
python scripts/extract_profiles.py --force --check
```

The compact report in `qa_report.md` is the primary release-gate summary.

## Related documentation

- Independent electron-count QA model: `docs/theory.md`.
- Released artifact contract: `docs/data.md`.
- Regeneration workflow: `docs/workflow.md`.
