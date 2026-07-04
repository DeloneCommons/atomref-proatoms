# atomref-proatoms

[![CI][ci-badge]][ci-workflow]
[![Pages][pages-badge]][pages-workflow]

`atomref-proatoms` provides reproducible spherical proatomic radial electron-density
profiles for isolated atoms and ions. The project is meant to supply consistent
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

The active state layer is v2. It combines NIST-derived neutral/cation states,
Ning--Lu 2022 physical/provisional monoanion states, and explicitly formal
anion references for the initial charged-state scope. The active curated state
table is `data/states/curated/atom_states_v2.json`, with its selection table in
`data/states/selection/required_states_v2.csv`. Historical v1 state files are
kept at Git tag/release/archive level, not as live source-tree functionality.

The current v2 profile-generation settings are declared in
`data/profile_datasets.yaml`. They define two primary charged-state datasets
(`x2c-QZVPall` H-Rn and `dyall-v4z` H-Lr) plus two separate anion-sensitivity
datasets (`x2c-QZVPall-s` H-Rn and `dyall-av4z` where available). Full v2
SCF/profile generation is a later step after the state/data and configuration
layers are stable.

## What is included

The active preparation layer contains:

- curated atomic-state inputs in `data/states/`;
- frozen Basis Set Exchange NWChem spherical basis exports in `data/basis_sets/`;
- the v2 profile dataset specification in `data/profile_datasets.yaml`;
- workflow scripts in `scripts/`;
- validation and loading utilities in `src/atomref_proatoms/`.

Generated v2 profile, radii, and QA tables are not committed in this preparation
snapshot. After SCF/profile generation, they will be tracked under
`data/profiles/`, `data/radii/`, and `data/qa/`. The expensive SCF checkpoints,
arrays, and logs live under ignored `local-data/scf/` directories and are used
only for regeneration.

For artifact formats and column conventions, see the [data-products guide](docs/data.md).
For state and basis provenance, see the [input-data guide](docs/inputs.md).
For scientific state-policy interpretation, see the [state-policy guide](docs/state_policy.md).
For the command-line workflow, see the [workflow guide](docs/workflow.md).

## Quick checks

Default validation does not require internet access and does not download basis
sets. From the repository root:

```bash
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/check_profile_artifacts.py
pytest
```

`check_basis_bundles.py` is fully offline by default. If PySCF is installed, it
also runs optional representative parse smoke checks for the frozen basis files.
If PySCF is absent, those smoke checks are reported as skipped.

The lightweight package layer must remain importable without PySCF:

```bash
python -c "import atomref_proatoms; print(atomref_proatoms.__version__)"
```

## Regeneration workflow

The profile-generation workflow is:

```bash
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/compute_wavefunctions.py --resume --quiet-scf-log
python scripts/extract_profiles.py --force --check
python scripts/check_profile_artifacts.py --require-generated
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
radii, and QA outputs. `check_profile_artifacts.py --require-generated` is the
release-gate consistency check for committed profile/radii/QA artifacts.

## Documentation

The documentation is organized as a MkDocs site:

- [Scientific model](docs/theory.md): spherical fractional-occupation proatoms
  and the difference from post-SCF angular averaging.
- [Data products](docs/data.md): active v2 dataset scopes and generated artifact contracts.
- [Input data](docs/inputs.md): basis bundles and atomic-state curation.
- [State policy](docs/state_policy.md): v2 state-source hierarchy, formal anion meaning, and interpretation limits.
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
runtime packages may consume compact generated snapshots from `data/profiles/`,
`data/radii/`, and `data/qa/` once v2 profiles are released, but they should not
depend on PySCF, Basis Set
Exchange tooling, external quantum-chemistry programs, or generator internals.

## License and attribution

Code in `src/`, `scripts/`, and `tests/` is released under the MIT License. The
released data tables, documentation, and notebooks are released under Creative
Commons Attribution 4.0 International unless an upstream notice states otherwise.
Frozen basis exports retain the Basis Set Exchange BSD-3-Clause notice, and the
atomic-state source layer uses compact configuration labels, ground-level labels,
parsed simple term multiplicities, a small set of manual v2-domain
multiplicity assignments, and ionization-energy provenance classes prepared
from the NIST Atomic Spectra Database, NIST Standard Reference Database 78. It
also includes a compact Ning--Lu 2022 monoanion state-status source table without
electron-affinity values and a formal-anion preparation table whose rows are
explicitly marked as formal/not-claimed references. See
[`LICENSE.md`](LICENSE.md) for the full repository license statement.

Project planning, scientific discussion, code drafting, and documentation drafting
used OpenAI models as assistance tools. The repository author is responsible for
the final scientific content, code, data, validation, and release decisions. See
[`AI_NOTE.md`](AI_NOTE.md).

[ci-badge]: https://github.com/DeloneCommons/atomref-proatoms/actions/workflows/ci.yml/badge.svg
[ci-workflow]: https://github.com/DeloneCommons/atomref-proatoms/actions/workflows/ci.yml
[pages-badge]: https://github.com/DeloneCommons/atomref-proatoms/actions/workflows/pages.yml/badge.svg
[pages-workflow]: https://github.com/DeloneCommons/atomref-proatoms/actions/workflows/pages.yml
