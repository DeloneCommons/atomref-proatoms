# Quality-assurance tables

This directory stores the quality-assurance layer for the generated spherical
proatomic profile datasets. The QA layer is the release Methods record for the
numerical density product: it explains how the profiles were checked after SCF,
how density-derived radii were validated, how basis-set linear-dependency
handling was recorded, and how supplemented/diffuse anion branches were compared
with their primary-basis counterparts.

The QA goal is not to prove that one basis set is universally correct. It is to
verify that the committed spherical profiles are internally consistent generated
artifacts, and to quantify where anion densities are sensitive to basis-set tail
flexibility.

## What is being checked

The production density model is a self-consistent spherical fractional-occupation
UKS calculation. Sphericity is imposed during SCF by equal occupation of complete
angular-momentum manifolds; the profile is not merely an angular average of an
ordinary anisotropic open-shell atom. The companion notebook
`docs/notebooks/spherical_vs_post_average_demo.ipynb` gives a small neutral-carbon
example of why that distinction matters: ordinary UKS plus post-SCF angular
averaging and the spherical fractional-occupation model can integrate to the same
electron count while giving visibly different valence/tail density curves and
cutoff radii.

After profile extraction, each generated density is checked on an angular grid.
The profile generator evaluates the density at each stored radius over an angular
quadrature, stores the angular mean as `rho_e_bohr3`, and records the angular
standard deviation. The QA column `max_rel_angular_sigma` reports the largest
`std_ang(rho) / rho` above the low-density floor. Values near `1e-14` in the
current data show that the stored profiles are spherical to numerical precision.

Electron-count QA uses a separate quadrature from the release profile grid. The
independent check integrates the angularly averaged density using a
Gauss-Legendre grid in `log(r)` from `1e-7` to `120` bohr with 400 radial points
and 110 angular points. Thus the electron-count gate is not a self-check on the
same 1200-point profile mesh.

The SCF settings used for the current generation pass are deliberately tolerant
of difficult diffuse anions:

```text
max_cycle = 300
diis_space = 12
diis_start_cycle = 1
```

All selected SCF jobs in the committed data layer converged and all profile rows
passed the numerical QA gates.

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
  x2c-QZVPall/
    basis_sensitivity.csv
    basis_sensitivity_summary.csv
    basis_sensitivity_outliers.csv
    basis_sensitivity_metric_distributions.csv
```

Per-dataset `qa.csv` files contain one row per generated state. The top-level
summary and `qa_report.md` aggregate dataset-level pass/fail status. The
basis-sensitivity tables compare matched neutral and anion states in primary and
supplemented/augmented branches. Pair-specific files are stored in subdirectories
named after the base basis set; root-level files are aggregate compatibility
outputs. `check_basis_sensitivity.py` emits every configured dyall and x2c
comparison by default when the corresponding generated profile datasets are
present.

## Expected generated status after regenerating unified supplemented branches

| dataset ID | rows | failed rows | linear-dependency warning count |
|---|---:|---:|---:|
| `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2` | 430 | 0 | 0 |
| `pbe0_sfx2c_dyallv4z_h-lr_spherical_v2` | 501 | 0 | 266 |
| `pbe0_sfx2c_x2cqzvpalls_h-rn_spherical_v2` | 192 | 0 expected | to be regenerated |
| `pbe0_sfx2c_dyallav4z_h-ba_hf-ra_spherical_v2` | 164 | 0 expected | to be regenerated |

After regenerating the unified supplemented/augmented branches, the top-level QA
metadata should record four generated datasets, 1287 dataset-state rows, and zero
release-gate failures.

Linear-dependency warnings are expected for some large or supplemented atomic
basis calculations. In the present data they concentrate in the dyall branches
and in supplemented/augmented anion branches. They are retained as diagnostics
because the corresponding SCF jobs converged and the extracted densities passed
electron-count, angular-sphericity, tail-coverage, and radius-consistency gates.

## Per-profile QA columns

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
smaller than higher density cutoffs. The radii themselves are computed from the
logarithmic profile grid by interpolation in `log(rho)` when neighboring density
values are positive.

### Angular/spherical consistency

`max_rel_angular_sigma` measures the largest relative angular variation observed
on the angular QA grid. The corresponding tolerance is reported as
`max_rel_angular_sigma_tolerance`, and the boolean result is `angular_sigma_pass`.

### Linear-dependency diagnostics

`linear_dependency_warning_count` and `linear_dependency_vectors_removed` are
parsed from SCF logs when PySCF reports basis-set linear-dependency handling.
These fields are diagnostics rather than automatic release failures.

## Basis-sensitivity QA

The basis-sensitivity layer asks how much a matched anion radial density changes
when a supplemented or augmented basis branch is used. It compares exact matched
states by state ID and state-record digest; missing or mismatched rows are not
silently hidden.

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

The tables record integrated L1 radial-distribution differences,
electron-count deltas, cumulative electron-count distribution shifts,
electron-quantile radius shifts, density-cutoff radius shifts, tail-electron
differences, and pointwise density diagnostics. The most interpretable release
summary is in `docs/data_layer_report.md`.

The dyall augmented comparison shows a clear chemical pattern: accepted physical
monoanions are mostly low-sensitivity, while formal multianions and all q = -3
formal rows are highly tail-sensitive. This is expected and useful information,
not a release blocker. The x2c supplemented-basis comparison is much smaller for
the committed H-Rn neutral/anion set.

## Recommended interpretation

Use QA failures as release blockers only for corruption-like problems: missing
profiles, mismatched metadata, failed SCF, impossible electron counts, invalid
grids, non-finite densities, or inconsistent radii. Use basis-sensitivity
warnings as scientific guidance. Large diffuse sensitivity means that the tail of
that reference density depends strongly on basis flexibility; it does not mean the
row is unusable, especially for explicitly formal anions.

Do not silently replace primary-branch rows with supplemented/augmented values.
If tail sensitivity matters, report the primary and supplemented/augmented basis
branches separately or construct a separate explicitly named branch.

## Regeneration

QA tables are generated artifacts and should not be hand-edited. They are
regenerated together with profiles and radii, then checked for active-dataset
consistency, by:

```bash
python scripts/extract_profiles.py --force --check
python scripts/check_basis_sensitivity.py --force
python scripts/check_profile_artifacts.py --require-generated
python scripts/build_data_layer_report.py
```

The compact `qa_report.md`, together with
`check_profile_artifacts.py --require-generated`, is the primary release-gate
summary after a profile generation run. The generated `docs/data_layer_report.md`
is the narrative scientific report.

## Related documentation

- Scientific data-layer report: `docs/data_layer_report.md`.
- Independent electron-count QA model: `docs/theory.md`.
- Released artifact contract: `docs/data.md`.
- Regeneration workflow: `docs/workflow.md`.
