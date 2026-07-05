# atomref-proatoms

`atomref-proatoms` is a reproducible scientific data package for spherical
proatomic radial electron densities. It publishes named profile datasets,
density-cutoff radii, and QA tables generated from declared atomic states, frozen
basis files, mean-field settings, radial grids, and validation criteria.

The package addresses a common ambiguity in proatom data. Open-shell atoms are
not generally spherical in an ordinary determinant calculation: the SCF procedure
can occupy particular magnetic components and optimize an anisotropic density.
Post-SCF angular averaging converts that density into a radial curve, but it does
not make the underlying self-consistent reference spherical. Here the spherical
constraint is imposed inside the atomic SCF model through fractional occupations
and angular-momentum block averaging. The tabulated density is therefore the
self-consistent spherical proatom density intended by the dataset definition.

The current state layer contains neutral, cationic, accepted monoanion, and
explicitly formal anion references. Profile-generation settings are declared in
`data/profile_datasets.yaml`, and the generated release artifacts are checked by
`python scripts/check_profile_artifacts.py --require-generated`.

## Documentation sections

- [Scientific model](theory.md) explains the density definition, spherical SCF
  construction, radial grids, cutoff radii, and QA model.
- [Data products](data.md) describes the released profile, radii, and QA files.
- [Scientific data-layer report](data_layer_report.md) summarizes generated QA,
  primary-basis comparisons, supplemented/diffuse anion sensitivity, and pending
  analyses.
- [Input data](inputs.md) describes the basis-set bundles and atomic-state table.
- [State policy](state_policy.md) explains the state-source hierarchy, formal anion labels, and interpretation limits.
- [Workflow](workflow.md) documents the scripts and regeneration commands.
- [Notebooks](notebooks/README.md) collect practical reports and method demos.
- [License](license.md) and [AI assistance note](ai_note.md) record repository
  attribution and responsibility statements.

## Minimal validation

```bash
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/check_profile_artifacts.py
pytest
```

The generator itself is optional for users who only need released data tables.
SCF regeneration requires the `generator` dependency extra.
