# Data products

The released data products are tracked under `data/profiles/`, `data/radii/`, and
`data/qa/`. They are generated from the same dataset specification and should be
read together: profiles give the radial density, radii give compact density-cutoff
size descriptors, and QA records whether the generated objects passed the release
checks.

The active dataset specification is `data/profile_datasets.yaml`. It declares the
profile-data version, density model, electronic-structure settings, radial grid,
QA grid, density cutoffs, selected basis families, and selected neutral states.

## Active v1 datasets

| dataset ID | basis | coverage | selected states |
|---|---|---:|---:|
| `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v1` | `x2c-QZVPall` | H-Rn | neutral recommended states |
| `pbe0_sfx2c_dyallv4z_h-lr_spherical_v1` | `dyall-v4z` | H-Lr | neutral recommended states |

The dataset ID is part of the public data identity. It encodes the method family,
basis family, element coverage, spherical density convention, and major data
version in a compact name. The full machine-readable record remains in
`data/profile_datasets.yaml` and in each generated `metadata.json` file.

## Radial profile tables

Each generated profile dataset contains:

- `data/profiles/<dataset_id>/profiles.csv`
- `data/profiles/<dataset_id>/metadata.json`

`profiles.csv` is a wide table. It has one shared radial column, `r_bohr`, and
one density column for each selected atomic state. Density columns use deterministic
curated state IDs:

```text
rho_e_bohr3__<state_id>
```

The density unit is electrons/bohr³. The tabulated density is the spin-summed
spherical proatomic density described in the [scientific model](theory.md).

`metadata.json` records the dataset identity, profile-data version, basis ID and
basis checksum, density model, method settings, radial grid, QA grid, density
cutoffs, state list, column map, related artifact paths, and generator provenance.
The local SCF artifact paths recorded in metadata are regeneration provenance;
those files are intentionally ignored by Git.

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

The QA layer records SCF completion, independent electron-count integration,
finite-density checks, tail coverage, cutoff-radius consistency, angular
sphericity, and linear-dependency diagnostics. Linear-dependency warnings are
reported as diagnostics; they are not release failures when the generated density
passes the numerical QA gate.

The directory-level details are documented in `data/qa/README.md`.

## Generated-artifact policy

Profile, radii, and QA tables are generated artifacts. Do not hand-edit them.
Change the source/configuration layer instead, regenerate with
`scripts/extract_profiles.py`, and inspect `data/qa/qa_report.md`.

The expensive local SCF material is stored under:

- `local-data/scf/<dataset_id>/<state_id>/scf.chk`
- `local-data/scf/<dataset_id>/<state_id>/scf.npz`
- `local-data/scf/<dataset_id>/<state_id>/scf.json`
- `local-data/scf/<dataset_id>/<state_id>/scf.log`

`local-data/` is ignored by Git. It is required for regeneration but is not part
of the public release tables.
