# atomref-proatoms

[![CI][ci-badge]][ci-workflow]
[![Pages][pages-badge]][pages-workflow]

`atomref-proatoms` provides reproducible spherical proatomic radial electron-density
profiles for isolated neutral atoms. The project is meant to supply consistent
quantum-chemical reference data for atom-centered theoretical-chemistry,
crystallographic, empirical density/radius, and promolecular-density models. It
is not an atomic-spectroscopy benchmark and does not try to turn one set of
atomic references into a universal replacement for method-specific calculations.

Atomic reference densities are often used as if a free atom were naturally a
single radial object. For many open-shell atoms, an ordinary single-determinant
SCF calculation instead selects particular magnetic components and gives an
anisotropic density. Angularly averaging that density after convergence produces
a radial table, but the SCF potential was still optimized for the anisotropic
state. This project uses a stricter construction: the atomic SCF problem is
solved with spherical fractional occupations and angular-momentum block averaging
built into the mean-field model. The radial density is therefore the
self-consistent spherical proatom density, not a post-processed average of a
broken-symmetry atom.

The current project version uses PySCF `2.13.1` and computes all active v1
profiles at the unrestricted PBE0 / spin-free one-electron X2C level with
pure/spherical Gaussian basis functions. The two released neutral branches are:

- `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v1`: H-Rn, `x2c-QZVPall`.
- `pbe0_sfx2c_dyallv4z_h-lr_spherical_v1`: H-Lr, `dyall-v4z`.

The machine-readable dataset specification is `data/profile_datasets.yaml`.

## What is included

The release data layer contains:

- radial density profiles in `data/profiles/<dataset_id>/profiles.csv`;
- density-cutoff radii in `data/radii/<dataset_id>/radii.csv`;
- per-state and aggregate QA tables in `data/qa/`;
- curated atomic-state inputs in `data/states/`;
- frozen Basis Set Exchange NWChem spherical basis exports in `data/basis_sets/`;
- workflow scripts in `scripts/`;
- validation and loading utilities in `src/atomref_proatoms/`.

The generated profile, radii, and QA tables are tracked release artifacts. The
expensive SCF checkpoints, arrays, and logs live under ignored `local-data/scf/`
directories and are used only for regeneration.

For artifact formats and column conventions, see the [data-products guide](docs/data.md).
For state and basis provenance, see the [input-data guide](docs/inputs.md).
For the command-line workflow, see the [workflow guide](docs/workflow.md).

## Quick checks

Default validation does not require internet access and does not download basis
sets. From the repository root:

```bash
python scripts/check_basis_bundles.py
python scripts/build_atom_states.py --check
pytest
```

`check_basis_bundles.py` is fully offline by default. If PySCF is installed, it
also runs optional representative parse smoke checks for the frozen basis files.
If PySCF is absent, those smoke checks are reported as skipped.

The lightweight package layer must remain importable without PySCF:

```bash
python -c "import atomref_proatoms; print(atomref_proatoms.__version__)"
```

## Regenerating the v1 artifacts

The production workflow is:

```bash
python scripts/build_atom_states.py --check
python scripts/check_basis_bundles.py
python scripts/compute_wavefunctions.py --resume --quiet-scf-log
python scripts/extract_profiles.py --force --check
```

`compute_wavefunctions.py --list`, `compute_wavefunctions.py --dry-run`, and
`extract_profiles.py --list` inspect the active build plan without running SCF.
Actual SCF generation requires the optional generator dependencies:

```bash
python -m pip install -e ".[generator,test,dev]"
```

`compute_wavefunctions.py` writes local artifacts such as `scf.chk`, `scf.npz`,
`scf.json`, and `scf.log` under `local-data/scf/<dataset_id>/<state_id>/`.
`extract_profiles.py` reads those local artifacts and writes the tracked profile,
radii, and QA outputs.

## Documentation

The documentation is organized as a MkDocs site:

- [Scientific model](docs/theory.md): spherical fractional-occupation proatoms
  and the difference from post-SCF angular averaging.
- [Data products](docs/data.md): released profile, radii, and QA artifacts.
- [Input data](docs/inputs.md): basis bundles and atomic-state curation.
- [Workflow](docs/workflow.md): scripts, package layout, and regeneration steps.
- [Notebooks](docs/notebooks/README.md): executable reports for inspecting the
  generated data and illustrating the method.
- [License](docs/license.md) and [AI assistance note](docs/ai_note.md).

Build the local documentation site with:

```bash
python -m pip install -e ".[docs]"
NO_MKDOCS_2_WARNING=1 mkdocs serve
```

## Lightweight consumers

This repository is the data-generation and release-artifact project. Lightweight
runtime packages may consume compact snapshots from `data/profiles/`,
`data/radii/`, and `data/qa/`, but they should not depend on PySCF, Basis Set
Exchange tooling, external quantum-chemistry programs, or generator internals.

## License and attribution

Code in `src/`, `scripts/`, and `tests/` is released under the MIT License. The
released data tables, documentation, and notebooks are released under Creative
Commons Attribution 4.0 International unless an upstream notice states otherwise.
Frozen basis exports retain the Basis Set Exchange BSD-3-Clause notice, and the
atomic-state source layer uses compact configuration labels, ground-level labels,
parsed simple term multiplicities, and ionization-energy provenance classes
prepared from the NIST Atomic Spectra Database, NIST Standard Reference Database
78. See
[`LICENSE.md`](LICENSE.md) for the full repository license statement.

Project planning, scientific discussion, code drafting, and documentation drafting
used OpenAI models as assistance tools. The repository author is responsible for
the final scientific content, code, data, validation, and release decisions. See
[`AI_NOTE.md`](AI_NOTE.md).

[ci-badge]: https://github.com/DeloneCommons/atomref-proatoms/actions/workflows/ci.yml/badge.svg
[ci-workflow]: https://github.com/DeloneCommons/atomref-proatoms/actions/workflows/ci.yml
[pages-badge]: https://github.com/DeloneCommons/atomref-proatoms/actions/workflows/pages.yml/badge.svg
[pages-workflow]: https://github.com/DeloneCommons/atomref-proatoms/actions/workflows/pages.yml
