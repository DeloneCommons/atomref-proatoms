# Data products

`data/profile_datasets.yaml` is the machine-readable contract for profile
generation. It declares the profile-data version, density model,
electronic-structure settings, radial grid, QA grid, density cutoffs, selected
basis families, element coverage, charge-class selection, and state-role
selection.

The generated data files live under `data/profiles/`, `data/radii/`, and
`data/qa/`. Profile, radii, and QA tables are generated data products: do not
hand-edit them. Change the source/configuration layer instead, regenerate the
tables, and run the validation checks.

## Profile datasets

| dataset ID | basis | coverage | selected rows | selected states |
|---|---|---|---:|---|
| `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2` | `x2c-QZVPall` | H-Rn | 430 | all curated states in range |
| `pbe0_sfx2c_dyallv4z_h-lr_spherical_v2` | `dyall-v4z` | H-Lr | 501 | all curated states in range |
| `pbe0_sfx2c_x2cqzvpalls_h-rn_spherical_v2` | `x2c-QZVPall-s` | H-Rn | 192 | neutrals and anions; cations excluded |
| `pbe0_sfx2c_dyallav4z_h-ba_hf-ra_spherical_v2` | `dyall-av4z` | H-Ba/Hf-Ra neutrals plus selected anions in the same intervals | 166 | neutrals and anions; cations excluded |

The primary datasets are deliberately not split into separate neutral, cation,
and anion products. The supplemented/augmented branches follow the same rule for
the states they support: each branch groups its neutral and anion rows under one
basis identity, while cations are excluded because they are compact and less
relevant to tail-sensitivity comparisons. `x2c-QZVPall-s` is an
NMR-shielding-oriented supplemented branch rather than a generic diffuse basis.
`dyall-av4z` has discontinuous coverage; its generated branch contains
H-Ba/Hf-Ra neutrals plus selected anions in the same available intervals,
including Fr and Ra monoanions.

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
cutoffs, state list, column map, related data paths, and generator
provenance. The local SCF paths recorded in metadata are regeneration
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

## QA data

Each generated QA dataset contains:

- `data/qa/<dataset_id>/qa.csv`
- `data/qa/<dataset_id>/metadata.json`

The aggregate QA layer contains:

- `data/qa/qa_summary.csv`
- `data/qa/qa_report.md`
- `data/qa/metadata.json`

The current generated QA summary contains four datasets, 1289 dataset-state rows,
and zero validation failures. The QA layer records SCF completion, independent
electron-count integration, finite-density checks, tail coverage, cutoff-radius
consistency, angular sphericity, and linear-dependency diagnostics.
Linear-dependency warnings are reported as diagnostics; they are not validation
failures when the generated density passes the numerical QA gate.

The directory-level details are documented in `data/qa/README.md`.

## Basis-sensitivity QA

Supplemented/augmented basis-sensitivity QA is stored below:

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

The `dyall-v4z/` subdirectory compares `dyall-v4z` with `dyall-av4z` for matched
neutral and anion states. The `x2c-QZVPall/` subdirectory compares `x2c-QZVPall`
with `x2c-QZVPall-s` for matched H-Rn neutral and anion states. The root-level
CSV files are aggregate compatibility outputs. `check_basis_sensitivity.py` emits
every configured supplemented/augmented comparison by default when the
corresponding generated profile datasets are present.

Current generated basis-sensitivity counts are:

| comparison | rows | low | moderate | high-sensitivity outliers | validation failures |
|---|---:|---:|---:|---:|---:|
| `dyall-v4z` vs `dyall-av4z` | 166 | 132 | 20 | 14 | 0 |
| `x2c-QZVPall` vs `x2c-QZVPall-s` | 192 | 192 | 0 | 0 | 0 |
| aggregate | 358 | 324 | 20 | 14 | 0 |

The sensitivity metrics classify how much the radial density distribution changes
when the supporting basis branch is used. Large sensitivity can be scientifically
expected for some formal or highly charged anions and is not, by itself, a
validation blocker. The narrative interpretation and recommended next
analyses are summarized in the [Results](results.md).

## Primary basis-family comparison QA

The primary basis-family comparison is stored below:

```text
data/qa/basis_comparisons/
  metadata.json
  x2c-QZVPall__dyall-v4z/
    basis_comparison.csv
    basis_comparison_summary.csv
    basis_comparison_outliers.csv
    basis_comparison_metric_distributions.csv
```

This comparison is not a diffuse-basis sensitivity test. It compares the primary
`x2c-QZVPall` and `dyall-v4z` branches over their H-Rn overlap, matching exact
`state_id` values and state-record digests. The current data product contains 430
matched rows, zero integrity failures, and one high-difference formal multianion
outlier. Signed deltas are `dyall-v4z` minus `x2c-QZVPall`.

## Regeneration policy

Regenerate profiles, radii, QA, basis-sensitivity QA, primary-basis-comparison QA, and documentation-derived outputs with:

```bash
python scripts/extract_profiles.py --force --check
python scripts/check_basis_sensitivity.py --force
python scripts/check_basis_comparisons.py --force
python scripts/check_profile_artifacts.py --require-generated
python scripts/prepare_docs.py --write
```

The expensive local SCF material is stored under:

- `local-data/scf/<dataset_id>/<state_id>/scf.chk`
- `local-data/scf/<dataset_id>/<state_id>/scf.npz`
- `local-data/scf/<dataset_id>/<state_id>/scf.json`
- `local-data/scf/<dataset_id>/<state_id>/scf.log`

`local-data/` is ignored by Git. It is required for regeneration but is not part
of the public release tables.

## Multiwfn interoperability files

The configured Multiwfn interoperability root is `data/multiwfn_artifacts/`.
It contains generated density-only `.rad` files and neutral-atom PROAIM `.wfn`
files derived from the same local SCF checkpoint, NPZ, and metadata artifacts
used to produce the release profile layer. These files are committed derived
products for Multiwfn-facing workflows; they do not replace the project-native
profile, radii, QA, or comparison tables.

Current generated contents are:

| format | count | basis branches | intended role |
|---|---:|---|---|
| `.rad` | 931 | `x2c-QZVPall` H--Rn and `dyall-v4z` H--Lr primary branches | density-only atomic radial references for stockholder/Hirshfeld-like use |
| `.wfn` | 86 | neutral `x2c-QZVPall` H--Rn atoms | atomwfn-style wavefunction containers for workflows that need GTF and spin-orbital information |

The `.rad` files are evaluated on the fixed Multiwfn `atmrad` grid from SCF
density matrices; they are not generated by interpolating the committed
`profiles.csv` tables. The `.wfn` files use the validated atomref spin-orbital
convention: alpha orbitals first, beta orbitals second, occupations at or below
one, and explicit `$MOSPIN` labels `1` and `2`.

These files are useful when the atomref-proatoms reference gauge should be used
inside Multiwfn workflows involving promolecular and deformation-density maps,
Hirshfeld/Hirshfeld-I-like charges and populations, VDD and ADCH-style charge
analyses, fuzzy atomic-space integrations, orbital composition with Hirshfeld
partitioning, real-space density and spin-density maps, topology/basin/domain
analyses, molecular-surface analyses, weak-interaction visualizations such as
RDG/NCI, IGM/IGMH/mIGM/aIGM, IRI and DORI, and density-difference or
charge-transfer inspection.

The main scientific advantage over relying on ad hoc Multiwfn atom generation is
that the atomref densities are spherical at the SCF-model level. They are not
ordinary anisotropic open-shell atom calculations that were sphericalized only
after SCF convergence. The product also provides a broader, versioned coverage
contract: `.rad` files for all configured primary-branch states over H--Rn and
H--Lr, and neutral H--Rn `.wfn` files where the chosen WFN basis-format boundary
is safe.

The manifest uses repository-relative paths. The optional `file` field is kept
only as a compatibility alias for older diagnostics and is required to match the
canonical `path` field. One-letter neutral WFN filenames intentionally retain
Multiwfn's atomwfn spacing convention, for example `H .wfn` and `O .wfn`.

The folder-level contract and regeneration commands are documented in
`data/multiwfn_artifacts/README.md`.
