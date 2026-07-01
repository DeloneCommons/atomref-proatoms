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
positive ion, the project keeps only the element, charge, electron count, and a
clean electronic-configuration label. Ionization energies, uncertainties, raw
HTML pages, and bibliography rows from the NIST Atomic Spectra Database are not
redistributed in this package. They are not needed for the density generator: the
spin-resolved occupations are generated from configurations by a documented
free-ion Hund high-spin convention.

## Directory layout

```text
data/states/
  README.md

  source/
    atom_config_summary.json
    atom_configs_nist_source.csv
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
configuration layer. Spin multiplicities and alpha/beta angular-momentum
occupation counts are assigned by the builder script and are stored only in the
curated JSON output.

## Source-data preparation

The positive-charge and neutral-atom source table was prepared from the NIST ASD
Ground States and Ionization Energies (GSIE) interface. The raw working snapshots
were used only as preparation material and are not part of this data layer.

Example query shape used during preparation:

```text
https://physics.nist.gov/cgi-bin/ASD/ie.pl?spectra=Na+Mg&submit=Retrieve+Data&units=1&format=0&order=0&at_num_out=on&sp_name_out=on&ion_charge_out=on&el_name_out=on&seq_out=on&shells_out=on&conf_out=on&level_out=on&ion_conf_out=on&e_out=0&unc_out=on&biblio=on
```

The important NIST output field for this project is `Ground Shells`, because it
provides a compact shell-occupation label such as `[Ar] 3d6`. These labels were
normalized to plain text forms suitable for a small CSV table. The NIST `Ground
Configuration` and `Ground Level` fields were inspected during preparation but
are not retained here, because the project does not reconstruct spectroscopic
terms from NIST data.

One practical caveat of the GSIE spectra input is that element symbols such as
`V` and `I` can also be interpreted in Roman-numeral ion-stage notation in some
combined queries. During preparation, returned spectrum labels and charges were
checked against the intended element-charge rows before compaction.

After compaction, the NIST-derived source table contains 5352 complete rows and
no duplicate `(symbol, charge)` keys. One incomplete high-charge nobelium row
from the raw snapshot was excluded; it is outside the selected state scope.

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
The compact source table keeps only common electronic-configuration labels needed
for reproducible proatom-density generation. Redistribution terms for NIST
Standard Reference Data should be reviewed before adding larger ASD extracts.
