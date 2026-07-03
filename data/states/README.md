# Atomic state input data

This directory contains the active v2 atomic-state layer for
`atomref-proatoms`. It defines generator-ready neutral, cationic,
physical/provisional monoanion, and formal-anion reference states with
deterministic charge, electron count, configuration, spin, spherical occupation,
and state-source metadata.

v1 state files are not retained in the active data tree. Historical v1 states and
artifacts are available from the v1 Git tags, releases, and archives.

## Directory layout

```text
data/states/
  README.md

  source/
    state_source_summary_v2.json

    nist_gsie/
      README.md
      nist_neutral_cation_states.csv

    ning2022/
      README.md
      ning2022_monoanions.csv

  selection/
    required_states_v2.csv

  curated/
    formal_atoms_ions.csv
    atom_states_v2.csv
    atom_states_v2.json
    atom_states_summary_v2.json
```

`source/` stores compact source/status inputs. `selection/` stores the active v2
compute-state selection. `curated/` stores the formal-anion preparation table and
the generator-ready v2 state products written by `scripts/build_atom_states.py`.

## Active v2 state table

The active curated table is:

```text
data/states/curated/atom_states_v2.json
```

A review-friendly CSV subset is also written to:

```text
data/states/curated/atom_states_v2.csv
```

The active v2 table contains 495 states:

```text
charge counts:
  -3: 6
  -2: 20
  -1: 80
   0: 103
  +1: 102
  +2: 95
  +3: 89

state categories:
  nist_reference: 389
  ning2022_monoanion_reference: 66
  formal_anion_reference: 40
```

The state builder can validate the current table without rewriting it:

```bash
python scripts/build_atom_states.py --check
```

To regenerate the v2 selection and curated outputs from the compact source
layers:

```bash
python scripts/build_atom_states.py
```

## Neutral and cation source layer

Neutral atoms and cations are sourced from the compact NIST GSIE table:

```text
data/states/source/nist_gsie/nist_neutral_cation_states.csv
```

The table was prepared from the NIST Atomic Spectra Database Ground States and
Ionization Energies interface. The raw source snapshots were preparation
material only and are not committed.

Retained fields are:

```text
z
symbol
charge
electron_count
configuration
ground_level
ground_multiplicity
nist_ie_provenance
```

The active source layer intentionally does not store raw HTML/MHTML snippets,
NIST URLs, bibliography rows, numerical ionization energies, or numerical
uncertainties. The `nist_ie_provenance` field is a compact class derived only
from NIST ionization-energy syntax:

```text
evaluated      plain numeric value
semiempirical  square-bracketed value: [ ... ]
theoretical    parenthesized value: ( ... )
missing        empty value, if present
```

`ground_level` is the retained NIST label used for spin curation. Most
`ground_multiplicity` values were parsed from simple LS-like labels with a
leading term multiplicity, for example `4S°3/2 -> 4`. Seven v2-domain
neutral/cation rows with non-LS or jj-style labels were assigned manually from
LS-equivalent/Hund-consistent multiplicities:

```text
Pr+  (9/2,1/2)°4  -> 5
Tb+  (15/2,1/2)°8 -> 7
Dy+  (8,1/2)17/2  -> 6
Ho+  (15/2,1/2)°8 -> 5
Er+  (6,1/2)13/2  -> 4
Tm+  (7/2,1/2)°4  -> 3
Pb   (1/2,1/2)0   -> 3
```

Rows outside the v2 neutral/cation policy domain may retain blank multiplicities.
Future selections that reach such rows should curate the multiplicity explicitly
instead of silently guessing.

## Monoanion source layer

The compact monoanion source/status table is:

```text
data/states/source/ning2022/ning2022_monoanions.csv
```

It is curated from Ning and Lu, *Electron Affinities of Atoms and Structures of
Atomic Negative Ions*, J. Phys. Chem. Ref. Data 51, 021502 (2022). The table
keeps state labels and status flags, not electron-affinity values.

Retained fields are:

```text
z
symbol
charge = -1
electron_count
configuration
ground_level
ground_multiplicity
state_role
physical_status
notes
```

Current source-status vocabulary:

```text
state_role:
  bound_experimental
  bound_provisional
  diagnostic_theory
  excluded

physical_status:
  experimental_or_evaluated
  provisional_experimental
  theoretical_only
  unbound_or_metastable
```

Only `bound_experimental` and `bound_provisional` monoanion rows enter the active
v2 compute table as physical/provisional monoanion references. Theory-only,
metastable-only, unbound, or otherwise excluded rows remain in the source table
for auditing and are not silently promoted to physical reference states.

## Formal anions

The active formal-anion preparation table is:

```text
data/states/curated/formal_atoms_ions.csv
```

It contains required anion references that are intentionally formal or that lack
an accepted physical/provisional monoanion row. Every row has:

```text
physical_status = not_claimed
```

Formal rows are stockholder/Hirshfeld-I-like reference densities. They are not
claims of stable isolated atomic anions or experimental atomic ground states.

Current formal coverage is:

```text
formal monoanions:
  required H-Rn -1 rows not covered by accepted Ning--Lu bound/provisional rows,
  excluding group 18 and excluding purely formal actinide fallback rows

formal dianions:
  groups 13-16 within H-Rn

formal trianions:
  C, N, P, As, Sb, Bi
```

Halogen dianions, group-18 anions, d/f multianions, and purely formal actinide
fallback monoanions are outside the initial v2 compute scope.

## v2 charge-selection policy

The active state selection is stored in:

```text
data/states/selection/required_states_v2.csv
```

The current policy is:

```text
neutral atoms:
  all H-Lr neutrals

cations:
  group 1: +1
  group 2: +1, +2
  all other elements H-Lr: +1, +2, +3
  no +4 cations in the initial v2 dataset
  zero-electron edge cases such as H+, He2+, and He3+ are excluded

monoanions:
  -1 for H-Rn except group 18
  accepted Ning--Lu rows are physical/provisional references
  missing or nonaccepted required rows are explicit formal monoanions
  no purely formal actinide fallback monoanions in the initial compute scope

multianions:
  -2 for H-Rn p-elements in groups 13-16
  -3 for C and pnictogens: C, N, P, As, Sb, Bi
  all multianions are formal references
  no d/f multianions in the initial v2 dataset
```

## Generated-state conventions

The generated JSON uses:

```text
schema_version = atomref.proatoms.state.v2
spin_model = curated_ground_multiplicity
spin_variant = curated_multiplicity
occupation_policy = spherical_l_counts_from_curated_multiplicity_v2
```

The builder derives spin-resolved spherical angular-momentum counts from the
curated multiplicity. For formal anions, this is a deterministic formal
occupation convention, not a spectroscopic assertion.

`source_table` values in generated rows are repository-relative paths within the
state layer, such as:

```text
source/nist_gsie/nist_neutral_cation_states.csv
source/ning2022/ning2022_monoanions.csv
curated/formal_atoms_ions.csv
```

`data/states/source/state_source_summary_v2.json` records compact row counts,
columns, checksums, source-status counts, and state-output checksums for auditing.
