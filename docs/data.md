# Data products

`data/profile_datasets.yaml` is the machine-readable contract for profile
generation. It declares the profile-data version, density model,
electronic-structure settings, radial grid, QA grid, density cutoffs, selected
basis families, element coverage, charge-class selection, and state-role
selection.

The generated release artifacts live under `data/profiles/`, `data/radii/`, and
`data/qa/`. Profile, radii, and QA tables are generated artifacts: do not
hand-edit them. Change the source/configuration layer instead, regenerate the
artifacts, and run the release-gate checks.

## Profile datasets

| dataset ID | basis | coverage | selected rows | selected states |
|---|---|---:|---:|---|
| `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2` | `x2c-QZVPall` | H-Rn | 430 | all curated states in range |
| `pbe0_sfx2c_dyallv4z_h-lr_spherical_v2` | `dyall-v4z` | H-Lr | 501 | all curated states in range |
| `pbe0_sfx2c_x2cqzvpalls_h-rn_anions_spherical_v2` | `x2c-QZVPall-s` | H-Rn | 106 | anions only |
| `pbe0_sfx2c_dyallav4z_h-ba_hf-ra_anions_spherical_v2` | `dyall-av4z` | H-Ba and Hf-At selected anions | 91 | anions only |

The two primary datasets are deliberately not split into separate neutral,
cation, and anion products. The supplemented/augmented branches are separate
anion-sensitivity datasets. `dyall-av4z` has discontinuous coverage and no
lanthanide/actinide augmented branch in the current release configuration; the
selected rows are the available anion states in H-Ba and Hf-At.

The dataset ID is part of the public data identity. It encodes the method family,
basis family, element coverage, spherical density convention, and major data
version in a compact name. The full machine-readable record remains in
`data/profile_datasets.yaml` and in each generated `metadata.json` file.

## Radial profile tables

Each generated profile dataset contains:

- `data/profiles/<dataset_id>/profiles.csv`
- `data/profiles/<dataset_id>/metadata.json`

`profiles.csv` is a wide table. It has one shared radial column, `r_bohr`, and
one density column for each selected atomic state. Density columns use
deterministic curated state IDs:

```text
rho_e_bohr3__<state_id>
```

The density unit is electrons/bohr³. The tabulated density is the spin-summed
spherical proatomic density described in the [scientific model](theory.md). The
stored release grid has 1200 logarithmic radial points from `1e-6` to `60` bohr.

`metadata.json` records the dataset identity, profile-data version, basis ID and
basis checksum, density model, method settings, radial grid, QA grid, density
cutoffs, state list, column map, related artifact paths, and generator
provenance. The local SCF artifact paths recorded in metadata are regeneration
provenance; those files are intentionally ignored by Git.

The directory-level details are documented in `data/profiles/README.md`.

## Density-cutoff radii

Each generated radii dataset contains:

- `data/radii/<dataset_id>/radii.csv`
- `data/radii/<dataset_id>/metadata.json`

`radii.csv` stores one row per selected state. For each declared density cutoff,
radii are reported in bohr and ångström:

- `r_iso_0.003_e_bohr3_bohr` and `r_iso_0.003_e_bohr3_angstrom`
- `r_iso_0.001_e_bohr3_bohr` and `r_iso_0.001_e_bohr3_angstrom`
- `r_iso_0.0001_e_bohr3_bohr` and `r_iso_0.0001_e_bohr3_angstrom`

The `0.003` and `0.001` electrons/bohr³ radii are the primary practical size
descriptors. The `0.0001` electrons/bohr³ radius is retained mainly as a tail and
interpolation diagnostic.

The directory-level details are documented in `data/radii/README.md`.

## QA artifacts

Each generated QA dataset contains:

- `data/qa/<dataset_id>/qa.csv`
- `data/qa/<dataset_id>/metadata.json`

The aggregate QA layer contains:

- `data/qa/qa_summary.csv`
- `data/qa/qa_report.md`
- `data/qa/metadata.json`

The current generated QA summary contains four datasets, 1128 dataset-state rows,
and zero release-gate failures. The QA layer records SCF completion, independent
electron-count integration, finite-density checks, tail coverage, cutoff-radius
consistency, angular sphericity, and linear-dependency diagnostics.
Linear-dependency warnings are reported as diagnostics; they are not release
failures when the generated density passes the numerical QA gate.

The directory-level details are documented in `data/qa/README.md`.

## Diffuse-basis sensitivity QA

Diffuse-basis sensitivity QA is stored below:

```text
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

The `dyall-v4z/` subdirectory is the primary scientific comparison: `dyall-v4z`
versus `dyall-av4z` for matched anion states. The `x2c-QZVPall/` subdirectory is
an optional diagnostic comparison: `x2c-QZVPall` versus `x2c-QZVPall-s`. The
root-level CSV files are aggregate compatibility outputs.

Current generated counts are:

| comparison | rows | high-sensitivity outliers | release-gate failures |
|---|---:|---:|---:|
| `dyall-v4z` vs `dyall-av4z` | 91 | 14 | 0 |
| `x2c-QZVPall` vs `x2c-QZVPall-s` | 106 | 0 | 0 |
| aggregate | 197 | 14 | 0 |

The sensitivity metrics classify how much the radial density distribution changes
when the diffuse/supplemented basis branch is used. Large sensitivity can be
scientifically expected for some formal or highly charged anions and is not, by
itself, a release blocker.

## Generated-artifact policy

Regenerate profiles, radii, QA, and the current basis-sensitivity QA with:

```bash
python scripts/extract_profiles.py --force --check
python scripts/check_basis_sensitivity.py --include-x2c-optional --force
python scripts/check_profile_artifacts.py --require-generated
```

The expensive local SCF material is stored under:

- `local-data/scf/<dataset_id>/<state_id>/scf.chk`
- `local-data/scf/<dataset_id>/<state_id>/scf.npz`
- `local-data/scf/<dataset_id>/<state_id>/scf.json`
- `local-data/scf/<dataset_id>/<state_id>/scf.log`

`local-data/` is ignored by Git. It is required for regeneration but is not part
of the public release tables.
