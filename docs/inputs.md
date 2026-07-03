# Input data

The v1 datasets are generated from two compact tracked input layers: atomic-state
records and frozen Gaussian basis bundles. The active selection and numerical
settings are combined in `data/profile_datasets.yaml`.

## Atomic-state layer

The curated state table is:

- `data/states/curated/atom_states_v1.json`

The selection file used to build it is:

- `data/states/selection/required_states_v1.csv`

Each curated record contains the fields needed to construct a one-center PySCF
atom and assign spherical fractional occupations: element, charge, electron
count, configuration, multiplicity, spin-resolved angular-momentum counts,
state role, curation status, and occupation policy.

The active v1 profile datasets select neutral recommended states from this table.
A charged record may exist in the curated state layer without being part of any
v1 generated profile dataset.

### Source convention

Neutral and positive-ion state labels are prepared from the NIST Atomic Spectra
Database Ground States and Ionization Energies interface, NIST Standard
Reference Database 78. This repository keeps compact configuration labels needed
for generator reproducibility, NIST ground-level labels, parsed simple
LS-term multiplicities for later v2 spin curation, and an ionization-energy
provenance class derived from the NIST bracket syntax. It does not redistribute raw
NIST ASD pages, quantitative ionization-energy values, numerical uncertainty
records, or bibliography rows.

Rows whose non-empty NIST `Ground Level` labels are not simple LS-like terms are
listed in `data/states/source/atom_configs_nist_ground_level_review.csv`. The
current v1 builder still uses its documented Hund high-spin occupation model;
the parsed NIST multiplicities are retained for the v2 state-curation layer.

Small formal-anion configuration records are stored separately under
`data/states/source/`. They are part of the state curation layer, not active v1
profile outputs unless selected by the active profile-dataset configuration.

The state-layer details are documented in `data/states/README.md`, and the build
entry point is `scripts/build_atom_states.py`.

## Basis-set layer

The frozen basis bundles are stored under `data/basis_sets/`. Each bundle contains
one NWChem-format spherical basis file, a manifest, SHA256 checksum, local
reference notes, and a bundle README.

Active v1 branches:

| basis ID | role | active coverage |
|---|---|---:|
| `x2c-QZVPall` | primary H-Rn scalar-relativistic branch | H-Rn |
| `dyall-v4z` | primary H-Lr heavy-element branch | H-Lr |

Auxiliary frozen bundles may be present for sensitivity checks. They are not
active profile datasets unless explicitly selected in `data/profile_datasets.yaml`.

The basis text checksum is the basis-data identity. Ordinary validation is
offline and checks required files, checksums, NWChem spherical headers, manifest
consistency, and declared element coverage. If PySCF is installed, representative
basis-parse smoke checks are also run.

The basis-layer details are documented in `data/basis_sets/README.md`, and the
validation entry point is `scripts/check_basis_bundles.py`.

## Dataset specification

`data/profile_datasets.yaml` connects the input layers to the generated data
products. It declares:

- the profile-data version;
- PySCF version expected for release generation;
- PBE0, UKS, sf-X2C-1e, and pure/spherical basis settings;
- SCF convergence and DFT grid settings;
- the stored radial profile grid;
- the independent QA grid;
- density cutoffs used for radii;
- active dataset IDs, basis IDs, element coverage, and neutral-only selection.

This YAML file should be treated as the central machine-readable contract for the
v1 release configuration.
