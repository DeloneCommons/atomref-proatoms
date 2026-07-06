# Atomic state input data

This directory contains the current atomic-state layer for
`atomref-proatoms`. It defines generator-ready neutral, cationic,
physical/provisional monoanion, and formal-anion reference states with
deterministic charge, electron count, configuration, spin, spherical occupation,
and state-source metadata.

This README is primarily a file and schema guide. The scientific state-policy
discussion lives in `docs/introduction.md`, `docs/methods.md`, and
`docs/state_policy.md`; the sections below describe the compact source tables,
the generated compute-state table, the charge-selection policy, and the spherical
occupation conventions used by the SCF generator.

Neutral atoms and cations are selected from compact NIST-derived ground-state
records. Physical or provisional monoanions are selected from a compact
Ning--Lu 2022 status table. Missing or deliberately nonphysical charged
references are made explicit as formal stockholder/Hirshfeld-I-like states. The
goal is not to solve a new atomic spectroscopy problem with the project-level
DFT model, but to make every proatomic density traceable to a declared source or
a declared formal rule.

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

`source/` stores compact source/status inputs. `selection/` stores the current
compute-state selection. `curated/` stores the formal-anion preparation table and
the generator-ready state products written by `scripts/build_atom_states.py`.

## Current state table

The active curated table is:

```text
data/states/curated/atom_states_v2.json
```

A review-friendly CSV subset is also written to:

```text
data/states/curated/atom_states_v2.csv
```

The current table contains 501 states:

```text
charge counts:
  -3: 6
  -2: 20
  -1: 86
   0: 103
  +1: 102
  +2: 95
  +3: 89

state categories:
  nist_reference: 389
  ning2022_monoanion_reference: 72
  formal_anion_reference: 40
```

Validate the current table without rewriting it:

```bash
python scripts/check_states.py
```

`python scripts/build_atom_states.py --check` remains available as a maintainer
compatibility path, but `check_states.py` is the clearer user-facing command.

To regenerate the selection and curated outputs from the compact source
layers:

```bash
python scripts/build_atom_states.py
```

## Neutral and cation source layer

Neutral atoms and cations are sourced from a compact table prepared from the [NIST Atomic Spectra Database Ground States and Ionization Energies interface](https://physics.nist.gov/PhysRefData/ASD/ionEnergy.html):

```text
data/states/source/nist_gsie/nist_neutral_cation_states.csv
```

The raw source snapshots were preparation material only and are not committed.

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
leading term multiplicity, for example `4S°3/2 -> 4`. Seven current-domain
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

Rows outside the current neutral/cation policy domain may retain blank multiplicities.
Future selections that reach such rows should curate the multiplicity explicitly
instead of silently guessing.

## Monoanion source layer

The compact monoanion source/status table is:

```text
data/states/source/ning2022/ning2022_monoanions.csv
```

It is curated from Ning and Lu, *Electron Affinities of Atoms and Structures of
Atomic Negative Ions*, J. Phys. Chem. Ref. Data 51, 021502 (2022),
[DOI: 10.1063/5.0080243](https://doi.org/10.1063/5.0080243). The table
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

For H-Rn, only `bound_experimental` and `bound_provisional` monoanion rows
enter the current compute table as physical/provisional monoanion references.
For the seventh-period Fr-U extension, the corresponding source-backed
Ning--Lu rows are included in the primary dyall-v4z H-Lr dataset, including
rows whose source status is `diagnostic_theory`; their `physical_status` remains
`theoretical_only` when appropriate. Other theory-only, metastable-only, unbound,
or otherwise excluded rows remain in the source table for auditing and are not
silently promoted to physical reference states.

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
fallback monoanions are outside the current compute scope.

## Charge-selection policy

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
  no +4 cations in the current dataset
  zero-electron edge cases such as H+, He2+, and He3+ are excluded

monoanions:
  -1 for H-Rn except group 18
  accepted H-Rn Ning--Lu rows are physical/provisional references
  missing or nonaccepted required H-Rn rows are explicit formal monoanions
  source-backed Ning--Lu Fr-U monoanion rows are included in the primary
    dyall-v4z H-Lr dataset, including theory-only/provisional rows with
    their original physical_status retained
  no purely formal actinide fallback monoanions in the current compute scope

multianions:
  -2 for H-Rn p-elements in groups 13-16
  -3 for C and pnictogens: C, N, P, As, Sb, Bi
  all multianions are formal references
  no d/f multianions in the current dataset
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
