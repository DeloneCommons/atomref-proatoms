# Data products

`data/profile_datasets.yaml` is the active machine-readable contract for v2
profile generation. It declares the profile-data version, density model,
electronic-structure settings, radial grid, QA grid, density cutoffs, selected
basis families, element coverage, charge-class selection, and state-role
selection.

No final v2 profile, radii, or QA tables are committed in this preparation
snapshot. The old neutral-only v1 generated artifacts were removed from the
active tree; v1 remains available from historical tags/releases/archives. After
SCF generation and profile extraction, the released data products will be tracked
under `data/profiles/`, `data/radii/`, and `data/qa/`.

## Planned v2 profile datasets

| dataset ID | basis | coverage | selected states |
|---|---|---:|---:|
| `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2` | `x2c-QZVPall` | H-Rn | all curated v2 states |
| `pbe0_sfx2c_dyallv4z_h-lr_spherical_v2` | `dyall-v4z` | H-Lr | all curated v2 states |
| `pbe0_sfx2c_x2cqzvpalls_h-rn_anions_spherical_v2` | `x2c-QZVPall-s` | H-Rn | anions only |
| `pbe0_sfx2c_dyallav4z_h-ba_hf-ra_anions_spherical_v2` | `dyall-av4z` | H-Ba, Hf-Ra | anions only |

The two primary datasets are deliberately not split into separate neutral,
cation, and anion products. The supplemented/augmented branches are separate
anion-sensitivity datasets. `dyall-av4z` is discontinuous and excludes the
lanthanide and actinide blocks; within the active H-Lr state range, the dataset
therefore covers H-Ba and Hf-Ra only.

The dataset ID is part of the public data identity. It encodes the method family,
basis family, element coverage, spherical density convention, and major data
version in a compact name. The full machine-readable record remains in
`data/profile_datasets.yaml` and, after generation, in each generated
`metadata.json` file.

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
spherical proatomic density described in the [scientific model](theory.md).

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

The QA layer records SCF completion, independent electron-count integration,
finite-density checks, tail coverage, cutoff-radius consistency, angular
sphericity, and linear-dependency diagnostics. Linear-dependency warnings are
reported as diagnostics; they are not release failures when the generated density
passes the numerical QA gate.

The directory-level details are documented in `data/qa/README.md`.

## Generated-artifact policy

Profile, radii, and QA tables are generated artifacts. Do not hand-edit them.
Change the source/configuration layer instead, regenerate with
`scripts/extract_profiles.py`, inspect `data/qa/qa_report.md`, optionally run
`python scripts/check_basis_sensitivity.py --force` for diffuse-basis anion sensitivity,
and run `python scripts/check_profile_artifacts.py --require-generated` before release.

The expensive local SCF material is stored under:

- `local-data/scf/<dataset_id>/<state_id>/scf.chk`
- `local-data/scf/<dataset_id>/<state_id>/scf.npz`
- `local-data/scf/<dataset_id>/<state_id>/scf.json`
- `local-data/scf/<dataset_id>/<state_id>/scf.log`

`local-data/` is ignored by Git. It is required for regeneration but is not part
of the public release tables.
