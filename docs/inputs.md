# Input data

The current state layer is generated from compact tracked source tables.
Frozen Gaussian basis bundles and profile-generation settings are declared
separately in `data/profile_datasets.yaml`.

## Atomic-state layer

The curated state table is:

- `data/states/curated/atom_states_v2.json`

The selection file used to build it is:

- `data/states/selection/required_states_v2.csv`

Each curated record contains the fields needed to construct a one-center PySCF
atom and assign spherical fractional occupations: element, charge, electron
count, configuration, multiplicity, spin-resolved angular-momentum counts,
state role, curation status, and occupation policy.

The current curated table contains neutral, cationic, physical/provisional
monoanion, and formal-anion reference states. Profile-generation datasets may
select a subset of these states by charge and state role.

### Source convention

Neutral and positive-ion state labels are prepared from the NIST Atomic Spectra
Database Ground States and Ionization Energies interface, NIST Standard
Reference Database 78. This repository keeps compact configuration labels needed
for generator reproducibility, NIST ground-level labels, parsed simple
LS-term multiplicities, a small set of manual domain-specific multiplicity assignments
for non-LS NIST labels, and an ionization-energy provenance class derived from
the NIST bracket syntax. It does not redistribute raw
NIST ASD pages, quantitative ionization-energy values, numerical uncertainty
records, or bibliography rows.

Most retained multiplicities are parsed automatically from simple LS-like
NIST `Ground Level` labels. For seven neutral/cation states in the intended
charge-policy domain whose NIST labels use jj or pair-coupled notation, the
project assigns LS-equivalent/Hund-consistent multiplicities manually in the
source table. Remaining non-empty labels outside this domain that are not parsed by the
simple rule are left blank. No separate review table is shipped because these
rows are outside the intended neutral/cation computation scope.

A compact monoanion source table is stored at
`data/states/source/ning2022/ning2022_monoanions.csv`. It is curated from Ning and Lu
2022 and retains only state labels plus status flags for H-U monoanions. It does
not store electron-affinity values or numerical uncertainties. Rows may be
flagged as accepted experimental/evaluated monoanions, provisional experimental
monoanions, theory-only diagnostics, or excluded/unbound/problematic cases. This
source table is part of the current state-preparation layer.

A formal-anion preparation table is stored at
`data/states/curated/formal_atoms_ions.csv`. It contains formal references for
required H-Rn monoanions without accepted physical/reference rows and for the current
p-block multianion policy. Purely formal actinide fallback monoanions are out of
the current scope. The source-backed Fr-U rows from the Ning--Lu table are
included only in the primary dyall-v4z H-Lr dataset and retain their original
physical/provisional/theory-only status. Every formal row is marked
`physical_status = not_claimed`; these records are stockholder/Hirshfeld-I-like
density references, not stable isolated atomic-anion claims.

The state-layer details are documented in `data/states/README.md`, the policy
rationale is summarized in `docs/state_policy.md`, the user-facing validation
entry point is `scripts/check_states.py`, and the regeneration entry point is
`scripts/build_atom_states.py`.

## Basis-set layer

The frozen basis bundles are stored under `data/basis_sets/`. Each bundle contains
one NWChem-format spherical basis file, a manifest, SHA256 checksum, local
reference notes, and a bundle README.

Basis branches currently declared for profile generation:

| basis ID | role | active dataset scope |
|---|---|---:|
| `x2c-QZVPall` | primary H-Rn scalar-relativistic branch | all curated states, H-Rn |
| `dyall-v4z` | primary H-Lr heavy-element branch | all curated states, H-Lr |
| `x2c-QZVPall-s` | supplemented x2c branch | anions, H-Rn |
| `dyall-av4z` | augmented dyall branch | anions where available within H-Lr |

The two primary datasets are not split into separate atom/cation/anion products.
The supplemented/augmented branches are separate anion datasets used to quantify basis-set tail sensitivity while preserving basis identity.

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
- active dataset IDs, basis IDs, element coverage, charge-class selection, and state-role selection.

This YAML file should be treated as the central machine-readable contract for
profile-generation settings.


## State-selection outputs

The state-validation command is:

```bash
python scripts/check_states.py
```

The state-preparation command is:

```bash
python scripts/build_atom_states.py
```

It produces the current selection and curated-state set:

```text
data/states/selection/required_states_v2.csv
data/states/curated/atom_states_v2.csv
data/states/curated/atom_states_v2.json
data/states/curated/atom_states_summary_v2.json
```

The output combines NIST neutral/cation rows, accepted H-Rn and source-backed Fr-U Ning--Lu monoanion
rows, and explicitly formal anion rows. The JSON uses curated ground
multiplicities and a spherical l-count occupation convention rather than the
earlier configuration-only Hund high-spin rule.
