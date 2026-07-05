# State policy and interpretation

This page records the atomic-state policy used by the tracked state
layer. It is a scientific and data-curation policy, not a claim that the project
can determine the unique lowest-energy isolated atom or ion for every method,
basis, and molecular environment.

The central convention is:

```text
atomref-proatoms provides reproducible spherical reference proatoms from
explicitly documented state policies.
```

A proatom used in stockholder, Hirshfeld-like, deformation-density, or
promolecular workflows is a reference gauge. It should be described as a
source-traceable or explicitly formal reference density generated under the
stated policy.

## Current state scope

The current state table is `data/states/curated/atom_states_v2.json`. It is
built from compact source/status tables and contains 501 states:

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


## Source hierarchy

The source hierarchy is deliberately conservative:

| Situation | Active source policy | Active category |
|---|---|---|
| Neutral atoms | NIST GSIE compact source table | `nist_reference` |
| Cations | NIST GSIE compact source table | `nist_reference` |
| Accepted/provisional H-Rn monoanions | Ning--Lu 2022 compact source/status table | `ning2022_monoanion_reference` |
| Source-backed Fr-U monoanions | Ning--Lu 2022 compact source/status table, with original physical/theory status retained | `ning2022_monoanion_reference` |
| Required H-Rn monoanions without an accepted physical/provisional row | Explicit formal table | `formal_anion_reference` |
| Multianions | Explicit formal table | `formal_anion_reference` |
| Other theory-only, unbound, metastable-only, or otherwise problematic anion rows | Retained as source/status rows only unless intentionally formalized | not silently promoted |

NIST is used for neutral atoms and positive ions because it provides curated
atomic/ionic ground-state configuration and level information. The active table
stores compact configuration, ground-level, parsed/curated multiplicity, and a
small ionization-energy provenance class; it does not redistribute raw NIST pages
or numerical ionization-energy values.

Ning and Lu 2022 is used as the current monoanion status/reference layer. The
active source table keeps configuration, term/level, multiplicity, state role,
physical status, and notes. It intentionally does not store electron-affinity
numeric values because those are not needed by the current generator state layer.

## Charge policy

The current state selection is:

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

## Formal anions

Formal anions are intentionally visible in the data:

```text
physical_status = not_claimed
state_role = formal_monoanion or formal_multianion
```

These rows are stockholder/Hirshfeld-I-like reference densities. They are not
claims of stable isolated atomic anions, experimental negative-ion ground states,
or recommended electron affinities. This distinction is especially important for
all q < -1 rows and for monoanion rows required by the charge policy despite
missing, theory-only, metastable-only, or unbound status in the review layer.

## Why not use automatic method-energy state selection by default?

A method-energy-selected free atom or ion can be useful for a deliberately
method-internal reference convention. It is not automatically more correct for
general proatomic density work.

The production policy avoids automatic energy-minimized state selection
because:

- the isolated free atom is not the atom in a molecule or crystal;
- ligand fields, covalency, charge transfer, relativistic effects, and
  polarization can favor different effective occupations in different systems;
- atomic anions are sensitive to self-interaction, asymptotic-potential failures,
  diffuse-basis choices, and finite-basis artifacts;
- a method-selected free-atom state is another reference convention, not a
  universal ground-truth label;
- silently choosing states by an approximate method risks implying a level of
  authority that the calculation may not support.

The clean expert path for non-default states is explicit user/state input:
configuration, spin or multiplicity, and later occupation details. Research
state scans may be added as diagnostics, but not as a default released-data state
selector.

## Why not use Hund-like rules everywhere?

Hund-like filling is acceptable for clearly labeled formal references, especially
formal p-block multianions. It is not a universal physical ground-state authority
across the periodic table. Transition metals, lanthanides, actinides, heavy
p-block elements, and many anions can have competing s/p/d/f occupations,
intermediate coupling, near degeneracy, and substantial relativistic effects.

The active policy therefore uses Hund/formal rules only as labeled formal
references or explicit fallbacks, not as a replacement for source-traceable
NIST/Ning/reference states.

## Density-difference interpretation

For a fixed molecular density,

\[
\Delta\rho = \rho_\mathrm{molecule} - \sum_A \rho_{A,\mathrm{reference}}.
\]

Changing between two spherical proatom reference schemes changes the result by a
sum of atom-centered spherical radial functions:

\[
\Delta\rho_1 - \Delta\rho_2 =
\sum_A \left(\rho_{A,2} - \rho_{A,1}\right).
\]

This means that changing the spherical atomic reference mainly changes the
atom-centered radial background: shells, tails, and monopole-like density around
nuclei. It does not by itself create directional bond accumulation or anisotropic
interfragment features.

Usually robust:

- qualitative anisotropic or interatomic redistribution;
- bond-centered accumulation/depletion patterns;
- features that are not merely concentric shells around atoms.

Requires caution or sensitivity checks:

- atom-centered radial shells;
- absolute deformation-density integrals;
- charge-transfer magnitudes;
- subtle heavy-atom tail features;
- conclusions that change when the proatom reference state changes.

## Publication-safe wording

Recommended wording:

```text
We used spherical reference proatoms generated under the documented
atomref-proatoms state policy. Neutral and cationic states are NIST-derived;
accepted monoanions use the Ning--Lu 2022 anion-status layer; formal anions are
explicitly labeled stockholder-reference states and are not claimed as stable
isolated atomic anions.
```

Avoid wording that says every proatom is the lowest-energy isolated atom or ion
at the user's method/basis, or that formal multianions are stable isolated atomic
ground states.

## Validation

Validate the active state layer without regenerating it:

```bash
python scripts/check_states.py
```

Regenerate the selection and curated outputs only after compact source tables
change:

```bash
python scripts/build_atom_states.py
```
