# Atomic state curation

The atomic-state layer defines generator-ready free-atom records. It converts
compact configuration inputs and a versioned selection file into a curated JSON
table used by the profile-generation workflow.

The active curated state table is:

```text
data/states/curated/atom_states_v1.json
```

The corresponding selection file is:

```text
data/states/selection/required_states_v1.csv
```

## Role in v1 profile generation

The curated state table may contain more records than a particular profile
dataset selects. The active v1 profile datasets select neutral recommended states
through `data/profile_datasets.yaml`. A record's presence in the curated state
JSON is therefore not, by itself, a claim that a v1 radial profile was generated
for that state.

## Curated record contents

Each curated state record contains the fields needed to build a one-center PySCF
atom and to assign spherical fractional occupations:

```text
state_id
symbol
z
charge
electron_count
configuration
multiplicity
spin_2s
alpha_l_counts
beta_l_counts
state_category
state_role
curation_status
occupation_policy
```

`state_id` is deterministic and is used in SCF artifact paths and generated CSV
column names. For example:

```text
C_q0_mult3_hund
```

The `alpha_l_counts` and `beta_l_counts` mappings store the number of alpha and
beta electrons assigned to each angular momentum `l`. During SCF setup, each
count is distributed over the complete `2l + 1` magnetic subspace for that spin
channel.

## State source convention

Neutral and positive-charge compact configuration labels are prepared from the
NIST ASD Ground States and Ionization Energies interface. The project does not
redistribute raw ASD pages, ionization energies, uncertainty tables, or
bibliography rows. It keeps only compact configuration labels needed to reproduce
the proatom generator inputs.

Small explicitly curated formal-anion configuration records are stored in a
separate source file under `data/states/source/`. These records are input records
for the state layer, not active v1 profile outputs unless selected by the active
profile-dataset configuration.

## Build and validation

Run from the repository root:

```bash
python scripts/build_atom_states.py
python scripts/build_atom_states.py --check
```

The builder reads the compact source tables and selection CSV, writes the curated
JSON table, and validates deterministic IDs, electron counts, multiplicities,
charge conventions, and angular-momentum occupation counts.

Per-record source fields are intentionally not included in the generator schema.
Attribution and preparation notes are documented at the source-table and README
level in `data/states/README.md`.
