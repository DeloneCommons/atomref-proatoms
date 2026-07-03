# Atomic state input data

This directory contains the compact atomic-state input layer for
`atomref-proatoms`. Its purpose is to define generator-ready free-atom reference
states with deterministic charge, electron-count, configuration, spin, and
spherical occupation metadata.

The active v1 profile datasets select neutral states from this table. The state
layer also contains curated charged reference records because the state curation
step is independent of the active profile-dataset selection. A charged state
record is not a generated v1 profile unless it is selected by
`data/profile_datasets.yaml`.

The data stored here are intentionally minimal. For each NIST-derived atom or
positive ion, the project keeps only the element, charge, electron count, a clean
electronic-configuration label, the NIST ground-level label, a parsed simple
LS-term multiplicity when the level label permits it, and a compact provenance
class derived from the syntax of the NIST ionization-energy value.
Raw HTML pages, quantitative ionization energies, numerical uncertainties, and
bibliography rows from the NIST Atomic Spectra Database are not redistributed in
this package. The current v1 density generator still uses the configuration
column and a documented free-ion Hund high-spin convention for spin-resolved
occupations; the retained NIST ground-level labels and parsed multiplicities are
a preparation layer for v2 spin/multiplicity curation.

## Directory layout

```text
data/states/
  README.md

  source/
    atom_config_summary.json
    atom_configs_nist_source.csv
    atom_configs_nist_ground_level_review.csv
    atom_configs_formal_anions.csv

  selection/
    required_states_v1.csv

  curated/
    atom_states_v1.json
    atom_states_summary.json

scripts/
  build_atom_states.py
```

`source/` stores compact configuration inputs. `selection/` stores the versioned
list of `(element, charge)` pairs to build. `curated/` stores generator-ready JSON
records produced by `scripts/build_atom_states.py`.

The `selection/` directory is a selection layer rather than a complete
configuration layer. The NIST source table now includes parsed simple
ground-level multiplicities for v2 curation, but the current v1 curated JSON is
still built with the documented Hund high-spin convention in
`scripts/build_atom_states.py`.

## Source-data preparation

The positive-charge and neutral-atom source table was prepared from the NIST ASD
Ground States and Ionization Energies (GSIE) interface. The raw working snapshots
were used only as preparation material and are not part of this data layer.

Example query shape used during preparation:

```text
https://physics.nist.gov/cgi-bin/ASD/ie.pl?spectra=Na+Mg&submit=Retrieve+Data&units=1&format=0&order=0&at_num_out=on&sp_name_out=on&ion_charge_out=on&el_name_out=on&seq_out=on&shells_out=on&conf_out=on&level_out=on&ion_conf_out=on&e_out=0&unc_out=on&biblio=on
```

The configuration column is the compact shell-occupation label prepared from the
NIST GSIE state fields and normalized to plain text forms suitable for a small
CSV table. The `ground_level` column stores the corresponding NIST `Ground
Level` label in compact text form, such as `2S1/2`, `3P2`, or `4S°3/2`. The
`ground_multiplicity` column is parsed only for simple LS-like labels with a
leading term multiplicity, for example `4S°3/2 -> 4`. Rows with missing
`ground_level` values or non-LS/intermediate-coupling labels have blank
`ground_multiplicity` values; non-empty unparsed labels are listed in
`atom_configs_nist_ground_level_review.csv` for later v2 manual curation. The
current v1 builder does not yet use these parsed multiplicities.

The `nist_ie_provenance` column is derived only from the bracket syntax of the
NIST `Ionization Energy (eV)` field:

```text
evaluated      plain numeric value
semiempirical  square-bracketed value: [ ... ]
theoretical    parenthesized value: ( ... )
missing        empty value, if present
```

This is a provenance class for the ionization-energy entry, not a stored
ionization energy and not a complete confidence score for the state label. Some
high-charge rows in the compact source table have blank NIST ground-level labels,
and some heavy-atom or high-charge rows use jj/intermediate-coupling labels that
are intentionally not converted into LS multiplicities. Those rows are retained
because the table mirrors the compact source preparation scope, while v2
production selections will use only policy-selected and reviewed states.

One practical caveat of the GSIE spectra input is that element symbols such as
`V` and `I` can also be interpreted in Roman-numeral ion-stage notation in some
combined queries. During preparation, returned spectrum labels and charges were
checked against the intended element-charge rows before compaction.

After compaction, the NIST-derived source table contains 5352 complete rows and
no duplicate `(symbol, charge)` keys. The simple ground-level parser assigns
4885 `ground_multiplicity` values, leaves 138 rows blank because no NIST
ground-level label was retained, and writes 329 non-empty non-LS labels to the
review file. One incomplete high-charge nobelium row from the raw snapshot was
excluded; it is outside the selected state scope.

## Formal anions

NIST GSIE is used here for neutral atoms and positive ions. The small table
`source/atom_configs_formal_anions.csv` adds closed-shell anion and formal-anion
reference configurations:

```text
F-, Cl-, Br-, I-
O2-, S2-, Se2-, Te2-
N3-, P3-, As3-, Sb3-, Bi3-
```

Halides are marked as `curated_common_ion`. Chalcogenide and pnictide anions are
marked as `formal_crystal_ion_reference`; this is a crystal-chemistry reference
convention and not a claim that such species are stable isolated free atomic
anions.

## State selection

`selection/required_states_v1.csv` lists the states selected for the curated
state table. The selection policy is conservative:

- all neutral atoms H-Lr are included;
- no actinide cations are included;
- group-1 +1 and group-2 +2 cations are included, including Fr+ and Ra2+;
- lanthanides are included as +3, with selected +2 and +4 exceptions;
- d-block cations are limited mainly to low-to-moderate, mostly ionic +1/+2/+3
  states;
- p-block cations are limited to conservative inert-pair-like cases such as
  Tl+, Sn2+, and Pb2+;
- formal multi-charged anions are included only through the explicit formal-anion
  source table.

The current selection contains 173 states: 103 neutral atoms, 57 cations, and 13
anions/formal anions.

## Curated JSON generation

Run from the repository root:

```bash
python scripts/build_atom_states.py
```

The script reads:

```text
data/states/source/atom_configs_nist_source.csv
data/states/source/atom_configs_formal_anions.csv
data/states/selection/required_states_v1.csv
```

and writes:

```text
data/states/curated/atom_states_v1.json
data/states/curated/atom_states_summary.json
```

The curated state records are generator inputs. Each record includes a
deterministic state ID, charge, electron count, configuration, spin multiplicity,
`alpha_l_counts`, `beta_l_counts`, state category, and curation status.

The default spin model is:

```text
free_ion_hund_high_spin
```

with occupation policy:

```text
free_ion_hund_high_spin_from_configuration_v1
```

This is the recommended convention for spherical free-ion proatoms. It should not
be interpreted as a ligand-field spin-state model.

## Licensing and attribution note

The source used for neutral and positive-ion configuration labels is the NIST
Atomic Spectra Database, NIST Standard Reference Database 78:

```text
https://www.nist.gov/pml/atomic-spectra-database
https://physics.nist.gov/PhysRefData/ASD/Html/iehelp.html
```

This project does not redistribute the raw ASD pages or quantitative SRD tables.
The compact source table keeps only common electronic-configuration labels, NIST
ground-level labels, parsed simple term multiplicities, and ionization-energy
provenance classes needed for reproducible proatom-density generation and v2
state curation. Redistribution
terms for NIST Standard Reference Data should be reviewed before adding larger
ASD extracts or quantitative energy tables.

## Related documentation

- Spherical occupation model: `docs/theory.md`.
- Input-data summary: `docs/inputs.md`.
- State build workflow: `docs/workflow.md` and `scripts/README.md`.
