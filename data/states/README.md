# Atomic state input data

This directory contains the compact atomic-state input layer for
`atomref-proatoms`. Its purpose is to define generator-ready free-atom reference
states with deterministic charge, electron-count, configuration, spin, and
spherical occupation metadata.

The active v2 state layer contains neutral, cationic, physical/provisional
monoanion, and formal-anion reference states. Profile-generation datasets may
select a subset of these states by charge and state role through
`data/profile_datasets.yaml`.

The data stored here are intentionally minimal. For each NIST-derived atom or
positive ion, the project keeps only the element, charge, electron count, a clean
electronic-configuration label, the NIST ground-level label, a compact
ground-state multiplicity field, and a compact provenance class derived from the
syntax of the NIST ionization-energy value.
Raw HTML pages, quantitative ionization energies, numerical uncertainties, and
bibliography rows from the NIST Atomic Spectra Database are not redistributed in
this package. The active v2 builder uses the retained NIST ground-level labels
and curated multiplicities as the spin source for generator-ready spherical
occupations.

## Directory layout

```text
data/states/
  README.md

  source/
    atom_config_summary.json
    atom_configs_nist_source.csv
    atom_configs_formal_anions.csv
    ning2022_monoanions.csv

  selection/
    required_states_v1.csv
    required_states_v2.csv

  curated/
    atom_states_v1.json
    atom_states_summary.json
    atom_states_v2.csv
    atom_states_v2.json
    atom_states_summary_v2.json
    formal_atoms_ions.csv

scripts/
  build_atom_states.py
```

`source/` stores compact configuration and state-status inputs. `selection/` stores
the versioned list of `(element, charge)` pairs to build. `curated/` stores
generator-ready JSON records produced by `scripts/build_atom_states.py`.

The `selection/` directory is a selection layer rather than a complete
configuration layer. The NIST source table includes ground-level multiplicities
for v2 curation. Most were parsed from simple LS-like NIST labels, and a small
number of intended v2 neutral/cation states were assigned manually from non-LS
NIST labels.

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
`ground_multiplicity` column is populated conservatively. Most values are parsed
from simple LS-like labels with a leading term multiplicity, for example
`4S°3/2 -> 4`. For seven neutral/cation states required by the intended v2
charge policy whose NIST labels use jj or pair-coupled notation, the project
assigns LS-equivalent/Hund-consistent multiplicities manually in the same column:
Pr+, Tb+, Dy+, Ho+, Er+, Tm+, and neutral Pb. No extra per-row method column is
used because this table is a compact source layer; the manual assignments are
documented here and in the summary JSON. Rows with missing `ground_level` values
or remaining non-LS/intermediate-coupling labels outside the v2 neutral/cation
policy domain have blank `ground_multiplicity` values. No separate review table is shipped because those
rows are outside the intended v2 neutral/cation computation scope; any future
selection that reaches them should curate the multiplicity explicitly.

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
4885 `ground_multiplicity` values, seven additional intended v2 neutral/cation
rows are manually assigned, 138 rows remain blank because no NIST ground-level
label was retained, and 322 non-empty non-LS labels outside the current v2
neutral/cation policy domain remain blank. One incomplete high-charge nobelium row from the raw
snapshot was excluded; it is outside the selected state scope.


## Ning--Lu monoanion source table

The table `source/ning2022_monoanions.csv` is a compact monoanion
state-status layer prepared from Ning and Lu, *Electron Affinities of Atoms and
Structures of Atomic Negative Ions*, J. Phys. Chem. Ref. Data 51, 021502
(2022). It uses the recommended atomic-anion state rows from Table 3 as the
main source for H-U monoanions.

The table intentionally does not store electron-affinity values or their
uncertainties. At this stage, atomref-proatoms needs the state labels and
source-level status flags only; quantitative affinity data can be added later if
a future workflow needs them. The retained fields are:

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

`configuration`, `ground_level`, and `ground_multiplicity` describe the
recommended negative-ion state where Ning--Lu provides one. Rows that the review
treats as unbound, metastable-only, or not accepted as stable negative ions keep
blank state fields and are flagged as `state_role = excluded`. Theory-only or
upper-limit cases that should not be used as physical/reference monoanions by
default are flagged as `state_role = diagnostic_theory`. Very weak or otherwise
provisional experimental rows are flagged as `bound_provisional`.

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

This table is a source layer, not the final v2 compute-state table. The v2 state
builder will decide which rows become physical/reference monoanions and which
required monoanions instead fall through to formal references.

## Formal anions

The v2 preparation layer adds a distinct curated table:

```text
data/states/curated/formal_atoms_ions.csv
```

This table contains formal anion references required by the v2 charge policy when
there is no accepted physical/reference monoanion, or when the requested charge is
intentionally formal. It is not an experimental negative-ion table. Every row has
`physical_status = not_claimed`. The retained fields are:

```text
z
symbol
charge
electron_count
configuration
ground_multiplicity
state_role
physical_status
state_source
rule_reason
notes
```

Current coverage is:

```text
formal monoanions:
  required -1 systems not covered by accepted Ning--Lu bound/provisional rows,
  excluding group 18 and excluding purely formal actinide fallback rows in the
  initial v2 scope

formal multianions:
  -2 for p-block groups 13-16
  -3 for carbon and pnictogens
```

The formal-monoanion construction rule is evidence-aware but deliberately
non-physical. Ning--Lu `bound_experimental` and `bound_provisional` monoanions
are treated as the accepted source rows and are not duplicated here. Required
monoanions that Ning--Lu treats as unbound, metastable-only, or otherwise not
accepted are included only as formal references, using neutral-isoelectronic
filling for the extra electron count. Ning--Lu theory-only or limit-based rows
are copied as manually curated formal monoanions, not as physical/reference
monoanions.

Purely formal actinide fallback monoanions are intentionally out of the initial
v2 formal table. Source-backed actinide monoanion rows may still enter through
the Ning--Lu source table when accepted by the later state builder, but Ac-, Pa-,
and beyond-U actinide monoanions are not generated by isoelectronic or neighbor
analogy in this initial dataset because the corresponding isolated-ion quantum
chemistry would be too fragile for the intended stockholder-reference layer.

For p-block multianions, configuration and multiplicity are generated by formal
isoelectronic filling. These rows are included only for the explicitly selected
formal-policy domains: group-13--16 dianions and carbon/pnictogen trianions.
Halogen dianions are out of the initial v2 formal-anion scope.

The older v1 table `source/atom_configs_formal_anions.csv` remains as a legacy
source artifact from the v1 release line. It added the small closed-shell/common-ion
set used by v1:

```text
F-, Cl-, Br-, I-
O2-, S2-, Se2-, Te2-
N3-, P3-, As3-, Sb3-, Bi3-
```

Halides are marked as `curated_common_ion`. Chalcogenide and pnictide anions are
marked as `formal_crystal_ion_reference`; this is a crystal-chemistry reference
convention and not a claim that such species are stable isolated free atomic
anions.

## Legacy v1 state files

Some v1 state files are still present in this source tree because they were part
of the existing released-data baseline. They are not regenerated by the active
v2 state-build command. v1 data products remain available through release tags
and archived artifacts; the active state-preparation command now writes the v2
selection and curated-state files.

## v2 combined state table

The active v2 preparation layer combines the compact NIST neutral/cation table, the
Ning--Lu monoanion status table, and the curated formal-anion table into a
separate generator-ready state list. Run:

```bash
python scripts/build_atom_states.py
```

The command writes:

```text
data/states/selection/required_states_v2.csv
data/states/curated/atom_states_v2.csv
data/states/curated/atom_states_v2.json
data/states/curated/atom_states_summary_v2.json
```

`required_states_v2.csv` is the compact compute-selection table. It records the
selected element, charge, electron count, state source, source table, role,
physical status, and inclusion reason. `atom_states_v2.csv` is a review-friendly
flat table for the same selected states. `atom_states_v2.json` is the
generator-ready table with spherical alpha/beta angular-momentum occupation
counts.

The v2 neutral/cation selection applies the current charge policy over H-Lr:

```text
neutral atoms: all H-Lr
group 1: +1
group 2: +1, +2
all other elements: +1, +2, +3
no +4 cations
```

Only electron-bearing rows present in the compact NIST source table are emitted.
Consequently, H+, He2+, and He3+ are not included in the v2 compute table: the
first two are zero-electron bare-nucleus cases in this context, and He3+ would
be non-physical. The exclusion is recorded in
`atom_states_summary_v2.json`.

The v2 monoanion selection uses Ning--Lu `bound_experimental` and
`bound_provisional` rows as accepted physical/provisional monoanion references
only within the initial H-Rn anion scope, excluding group 18 as required by the
v2 anion policy. Monoanion rows marked as `diagnostic_theory` or `excluded` do
not enter the physical/reference layer; required non-actinide fallback cases
enter only through `formal_atoms_ions.csv` as `physical_status = not_claimed`.
Source-backed Fr-, Ra-, Th-, U-, and heavier monoanion rows are retained in the
source-status layer for future extension, but they do not enter the initial v2
compute-state table.

The v2 JSON records use:

```text
schema_version = atomref.proatoms.state.v2
spin_model = curated_ground_multiplicity
spin_variant = curated_multiplicity
occupation_policy = spherical_l_counts_from_curated_multiplicity_v2
```

For most selected states, the curated multiplicity is the same as the
maximum-spin spherical occupation implied by the configuration. A small number
of states, such as neutral Ce, require a lower curated multiplicity than the
configuration-only high-spin rule would give. In these cases the builder keeps
the total spherical electron count per angular momentum and distributes the
spin imbalance fractionally over the open angular-momentum channels. This is a
deterministic spherical occupation convention for density generation; it is not
a reconstruction of a full term-resolved atomic wavefunction.

## Licensing and attribution note

The source used for neutral and positive-ion configuration labels is the NIST
Atomic Spectra Database, NIST Standard Reference Database 78:

```text
https://www.nist.gov/pml/atomic-spectra-database
https://physics.nist.gov/PhysRefData/ASD/Html/iehelp.html
```

This project does not redistribute the raw ASD pages or quantitative SRD tables.
The compact source table keeps only common electronic-configuration labels, NIST
ground-level labels, parsed simple term multiplicities, a small set of manual
v2-domain multiplicity assignments, and ionization-energy provenance classes
needed for reproducible proatom-density generation and v2 state curation. Redistribution
terms for NIST Standard Reference Data should be reviewed before adding larger
ASD extracts or quantitative energy tables.

## Related documentation

- Spherical occupation model: `docs/theory.md`.
- Input-data summary: `docs/inputs.md`.
- State build workflow: `docs/workflow.md` and `scripts/README.md`.
