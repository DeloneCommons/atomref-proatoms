# atomref-proatoms

`atomref-proatoms` is a reproducible data package for spherical neutral proatomic
radial electron densities. It publishes named profile datasets, cutoff radii, and
QA tables generated from declared atomic states, frozen basis files, mean-field
settings, radial grids, and validation criteria.

The package addresses a common ambiguity in proatom data. Open-shell atoms are
not generally spherical in an ordinary determinant calculation: the SCF procedure
can occupy particular magnetic components and optimize an anisotropic density.
Post-SCF angular averaging converts that density into a radial curve, but it does
not make the underlying self-consistent reference spherical. Here the spherical
constraint is imposed inside the atomic SCF model through fractional occupations
and angular-momentum block averaging. The tabulated density is therefore the
self-consistent spherical proatom density intended by the dataset definition.

The current v1 datasets are neutral-only:

- `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v1`, covering H-Rn with `x2c-QZVPall`.
- `pbe0_sfx2c_dyallv4z_h-lr_spherical_v1`, covering H-Lr with `dyall-v4z`.

Both use unrestricted PBE0 with PySCF `2.13.1`, spin-free one-electron X2C, and
pure/spherical Gaussian basis functions.

## Documentation sections

- [Scientific model](theory.md) explains the density definition, spherical SCF
  construction, radial grids, cutoff radii, and QA model.
- [Data products](data.md) describes the released profile, radii, and QA files.
- [Input data](inputs.md) describes the basis-set bundles and atomic-state table.
- [Workflow](workflow.md) documents the scripts and regeneration commands.
- [Notebooks](notebooks/README.md) collect practical reports and method demos.
- [License](license.md) and [AI assistance note](ai_note.md) record repository
  attribution and responsibility statements.

## Minimal validation

```bash
python scripts/check_basis_bundles.py
python scripts/build_atom_states.py --check
pytest
```

The generator itself is optional for users who only need released data tables.
SCF regeneration requires the `generator` dependency extra.
