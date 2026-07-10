# atomref-proatoms

[![CI][ci-badge]][ci-workflow]
[![Pages][pages-badge]][pages-workflow]

`atomref-proatoms` publishes versioned spherical proatomic radial electron-density
profiles for isolated atoms and ions. It is meant for users who need a documented
atom-centered reference convention instead of an implicit mixture of states,
bases, grids, and validation rules. The data support stockholder and
Hirshfeld-like analyses, promolecular density construction, deformation-density
inspection, empirical radius models, and related cheminformatics or
crystallographic workflows. The repository also includes a committed Multiwfn
interoperability product: SCF-derived `.rad` atomic radial-density files for the
two primary basis branches and neutral-atom PROAIM `.wfn` files for the primary
`x2c-QZVPall` branch. These files make the same state and spherical-density
conventions available to Multiwfn workflows that use atomic densities or
atomwfn-style inputs.

## Quick orientation

Reading this on PyPI? The PyPI package installs the Python package, packaged
state/preset resources, and the `atomref-proatoms` CLI. It is the right route
for planning and generating new local profiles, but it is not the complete
published dataset archive.

- New to the project: start with the documentation map below and the
  [Workflow](docs/workflow.md) guide.
- Need the published atomic profiles, cutoff radii, and QA tables: use the
  `data/` folder from the GitHub or Zenodo release snapshot.
- Need Multiwfn `.rad` or `.wfn` files: see `data/multiwfn_artifacts/` for the
  released files and `examples/` for small reproducible generator runs.
- Need to generate new local profiles or Multiwfn artifacts: install the
  generator extra and use `atomref-proatoms generate`.

## Installation

For the published command-line tool from PyPI:

```bash
python -m pip install atomref-proatoms
python -m pip install "atomref-proatoms[generator]"
```

The base install is enough to import the package, inspect packaged resources,
and run lightweight CLI help/dry-run paths. The `generator` extra adds PySCF and
Basis Set Exchange for local SCF-backed generation and `bse:` basis sources.

For a source checkout, use editable installs from the repository root:

```bash
python -m pip install -e .
python -m pip install -e ".[generator]"
```

## Python scripting API

Reusable scripting objects are available directly from the package:

```python
from atomref_proatoms import select_packaged_states

selection = select_packaged_states(
    elements=["C", "Ni"],
    policy="stockholder",
    charges=[-1, 0, 1],
)
print(selection.state_ids)
```

The base installation supports packaged-state selection and lightweight profile
operations. Spherical SCF calculations and SCF-derived exports require the
`generator` extra. See the [Python API](docs/api.md) and the
[custom-state scripting guide](docs/generator/scripting.md) for the supported
package-level interface.

## Scientific approach

The central scientific choice is to define the proatom as a **self-consistent
spherical density**, not as an angular average applied after an ordinary
broken-symmetry open-shell calculation. In the generator, open-shell occupations
are distributed over complete angular-momentum manifolds during the SCF cycle,
and the atomic Fock problem is solved in angular-momentum-averaged radial blocks.
The tabulated radial density is therefore the density of the spherical ensemble
used in the mean-field model itself.

The current data layer combines NIST-derived neutral/cation states, a compact
Ning--Lu 2022 monoanion status layer, and explicitly formal anion references.
Formal anions are included for stockholder/Hirshfeld-I-like reference-density
coverage; they are not claims of stable isolated atomic anions. The state table is
`data/states/curated/atom_states_v2.json`, and the selected generation scope is
`data/states/selection/required_states_v2.csv`.

The profile-generation protocol is declared in `data/profile_datasets.yaml`:
PBE0, spin-free one-electron X2C, self-consistent spherical fractional-occupation
UKS, pure all-electron Gaussian basis functions, a logarithmic release grid, and
an independent log-radius QA quadrature. The profile data version is `2.0.0`.

## Scientific contents

The data layer contains four profile/radii/QA datasets and 1289 dataset-state rows:

| dataset ID | basis | selected rows | role |
|---|---|---:|---|
| `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2` | `x2c-QZVPall` | 430 | primary H-Rn |
| `pbe0_sfx2c_dyallv4z_h-lr_spherical_v2` | `dyall-v4z` | 501 | primary H-Lr |
| `pbe0_sfx2c_x2cqzvpalls_h-rn_spherical_v2` | `x2c-QZVPall-s` | 192 | supplemented H-Rn neutrals/anions |
| `pbe0_sfx2c_dyallav4z_h-ba_hf-ra_spherical_v2` | `dyall-av4z` | 166 | augmented selected neutrals/anions |

The two primary basis branches are large all-electron quadruple-zeta families
chosen for broad periodic-table coverage and reduced radial basis-set error. The
supplemented/augmented branches are not split by neutral/anion charge class;
they retain their own basis identities and deliberately exclude cations. The
Multiwfn interoperability directory contains 931 `.rad` files for the two
primary branches and 86 neutral-atom `.wfn` files for `x2c-QZVPall`; these are
derived products, not replacements for the profile/radii/QA contract. Generated
data files are stored under:

```text
data/profiles/<dataset_id>/profiles.csv
data/radii/<dataset_id>/radii.csv
data/qa/<dataset_id>/qa.csv
data/multiwfn_artifacts/
```

The expensive SCF checkpoints, arrays, and logs are regeneration inputs under
ignored `local-data/scf/` paths and are not part of the committed release tables.

## Quality-assurance summary

Every committed profile row passes the current validation criteria. The validation layer verifies
SCF completion, independent electron-count integration, angular sphericity,
finite density values, tail coverage, and cutoff-radius consistency. The current
maximum independent electron-count error is about `2.5e-12` electrons, and the
maximum relative angular density standard deviation above the QA density floor is
about `1.6e-14`.

Diffuse/supplemented basis sensitivity is stored under
`data/qa/basis_sensitivity/`: dyall-v4z → dyall-av4z has 166 matched
neutral/anion rows with 14 high-sensitivity formal-anion outliers, while
x2c-QZVPall → x2c-QZVPall-s has 192 matched neutral/anion rows and no high
outliers. The primary basis-family comparison is stored under
`data/qa/basis_comparisons/` and matches 430 H-Rn states between x2c-QZVPall and
dyall-v4z. These comparison rows are scientific diagnostics, not release failures.

For a compact Methods-style summary of QA, basis comparisons, and recommended
next analyses, see the [Results](docs/results.md).

## How to inspect the data

The fastest release-data consistency checks are:

```bash
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/check_profile_artifacts.py --require-generated
python scripts/check_multiwfn_artifacts.py --require-generated
python scripts/prepare_docs.py --check
pytest -q
```

`check_basis_bundles.py` is fully offline by default. If PySCF is installed, it
also runs representative parse smoke checks for the frozen basis files; otherwise
those smoke checks are reported as skipped.

The lightweight package layer remains importable without PySCF:

```bash
python -c "import atomref_proatoms; print(atomref_proatoms.__version__)"
```

For a PyPI-style packaging check, build and install the wheel into a fresh
environment and run the public CLI without importing from the source checkout:

```bash
python scripts/smoke_installed_wheel.py
```

The optional `--with-generator-execution` mode additionally installs the
`generator` extra and runs a tiny neutral-H generation smoke test. A full
maintainer release gate is listed in [`docs/workflow.md`](docs/workflow.md).

## Regeneration workflow

Full regeneration requires the optional generator dependencies and complete local
SCF execution:

```bash
python -m pip install -e ".[generator,dev,docs]"
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/compute_wavefunctions.py --resume --quiet-scf-log
python scripts/extract_profiles.py --force --check
python scripts/check_basis_sensitivity.py --force
python scripts/check_basis_comparisons.py --force
python scripts/check_profile_artifacts.py --require-generated
python scripts/export_multiwfn_artifacts.py --format all --force --check
python scripts/check_multiwfn_artifacts.py --require-generated
```

The `--list` and `--dry-run` options on `compute_wavefunctions.py`,
`extract_profiles.py`, and `export_multiwfn_artifacts.py` inspect the active
build/export plan without running SCF or rewriting generated artifacts.
`scripts/prepare_docs.py --write` only reads committed tables and refreshes
`docs/tables/`, `docs/figures/`, and marked blocks in `docs/results.md`.

## Generator examples

The public generator tool has reproducible examples under [`examples/`](examples/):

- `examples/01_cli_neutral_rad_wfn_bse/` generates neutral Multiwfn `.rad` and `.wfn` files for H and B--F from a BSE basis with X2C disabled.
- `examples/02_cli_stockholder_local_basis/` generates stockholder-style profiles/radii/QA, `.rad`, and neutral-only `.wfn` outputs from a local NWChem basis file.
- `examples/03_python_custom_state_pipeline/` is an expert notebook for custom states and project-specific pipelines outside the curated CLI state policies.

The full tool manual is in the [Generator tool](docs/generator/index.md) documentation section.
Use `python -m pip install "atomref-proatoms[generator]"` for the PyPI tool, or
`python -m pip install -e ".[generator]"` from a source checkout. Both include
PySCF and Basis Set Exchange for `bse:` basis sources.

## Documentation map

- [Scientific model](docs/theory.md): spherical fractional-occupation proatoms,
  radial distributions, cutoff-radius definitions, and reference-gauge interpretation.
- [Methods](docs/methods.md): state sources, basis branches, electronic-structure
  settings, radial grids, validation, and comparison metrics.
- [Results](docs/results.md): paper-style summary of QA, basis comparisons, sensitivity patterns, and practical recommendations.
- [Data products](docs/data.md): profile, radii, QA, basis-sensitivity,
  primary-basis-comparison, and Multiwfn interoperability file contracts.
- [Input data](docs/inputs.md): basis bundles and atomic-state curation.
- [State policy](docs/state_policy.md): state-source hierarchy, formal anion
  meaning, and interpretation limits.
- [Workflow](docs/workflow.md): scripts, package layout, and regeneration steps.
- [Notebooks](docs/notebooks/README.md): profile-inspection and sphericalization
  demonstration notebooks.
- [Python API](docs/api.md): package-level state, SCF, profile, and
  interoperability scripting interface.
- [License](docs/license.md) and [AI assistance note](docs/ai_note.md).

## Lightweight consumers

This repository is the data-generation and publication-data project. The wheel
contains code, the CLI, schemas, curated state tables, presets, and small service
resources. The full generated profile/radii/QA tables and Multiwfn `.rad`/`.wfn`
files are release data products in the repository and GitHub/Zenodo assets.
Lightweight runtime packages may consume compact generated snapshots from
`data/profiles/`, `data/radii/`, and `data/qa/`, but they should not depend on
PySCF, Basis Set Exchange tooling, external quantum-chemistry programs, or
generator internals.

## License and attribution

Code in `src/`, `scripts/`, and `tests/` is released under the MIT License. The
released data tables, documentation, and notebooks are released under Creative
Commons Attribution 4.0 International unless an upstream notice states otherwise.
Frozen basis exports retain the Basis Set Exchange BSD-3-Clause notice, and the
atomic-state source layer uses compact configuration labels, ground-level labels,
parsed simple term multiplicities, a small set of manual domain-specific
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
