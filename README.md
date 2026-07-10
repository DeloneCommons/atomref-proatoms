# atomref-proatoms

[![CI][ci-badge]][ci-workflow]
[![Documentation][pages-badge]][documentation]
[![DOI][zenodo-badge]][zenodo-doi]

`atomref-proatoms` is both a versioned dataset and a Python toolkit for spherical
atomic and ionic reference densities. The released data can be used directly in
stockholder and Hirshfeld-like analyses, promolecular and deformation-density
work, radius models, and related real-space workflows. The toolkit is optional:
install it only when you want to select packaged states, generate a local subset,
or build a different documented reference convention.

## Choose what you need

| Goal | Start here | Installation needed? |
|---|---|---|
| Use the published radial profiles, cutoff radii, or QA tables | [v2.0.0 archive](https://doi.org/10.5281/zenodo.21291022) and [data guide](https://delonecommons.github.io/atomref-proatoms/data/) | No |
| Use the released Multiwfn `.rad` or `.wfn` files | [Multiwfn artifacts](https://github.com/DeloneCommons/atomref-proatoms/tree/main/data/multiwfn_artifacts) | No |
| Understand or cite the scientific convention | [Scientific note](https://delonecommons.github.io/atomref-proatoms/) | No |
| Generate a small local dataset | [Generator quick start](https://delonecommons.github.io/atomref-proatoms/generator/) | Yes, generator extra |
| Develop or regenerate the release | [Maintainer workflow](https://delonecommons.github.io/atomref-proatoms/workflow/) | Yes, source checkout |

The PyPI package contains the Python API, command-line interface, curated state
table, presets, schemas, and small supporting resources. It does **not** contain
the complete published profile/radii/QA tables or Multiwfn artifact tree; obtain
those from the [Zenodo v2.0.0 archive](https://doi.org/10.5281/zenodo.21291022)
or [tagged GitHub release](https://github.com/DeloneCommons/atomref-proatoms/releases/tag/v2.0.0).

## Why these proatoms are different

The central scientific choice is to define each proatom as a **self-consistent
spherical density**, not as an angular average applied after an ordinary
broken-symmetry open-shell calculation. Open-shell occupations are distributed
over complete angular-momentum manifolds during the self-consistent-field (SCF)
cycle, and the atomic Fock problem is solved in angular-momentum-averaged radial
blocks. The tabulated radial density therefore belongs to the spherical ensemble
used by the mean-field model itself.

The current data layer combines NIST-derived neutral/cation states, a compact
Ning--Lu 2022 monoanion status layer, and explicitly formal anion references.
Formal anions are included for stockholder/Hirshfeld-I-like reference-density
coverage; they are not claims of stable isolated atomic anions. The state table is
`data/states/curated/atom_states_v2.json`, and the selected generation scope is
`data/states/selection/required_states_v2.csv`.

The profile-generation protocol is declared in `data/profile_datasets.yaml`:
PBE0, spin-free one-electron exact two-component (X2C) relativity,
self-consistent spherical fractional-occupation unrestricted Kohn--Sham (UKS),
pure all-electron Gaussian basis functions, a logarithmic release grid, and an
independent log-radius QA quadrature. The profile data version is `2.0.0`.

The paper-style [Introduction](https://delonecommons.github.io/atomref-proatoms/introduction/),
[Theory](https://delonecommons.github.io/atomref-proatoms/theory/),
[Methods](https://delonecommons.github.io/atomref-proatoms/methods/),
[Results](https://delonecommons.github.io/atomref-proatoms/results/),
[Discussion](https://delonecommons.github.io/atomref-proatoms/discussion/), and
[Conclusions](https://delonecommons.github.io/atomref-proatoms/conclusions/) document
the scientific reasoning and its limits.

## Installation for the toolkit

No installation is required to read the released CSV, JSON, `.rad`, or `.wfn`
files. To generate new profiles with PySCF and Basis Set Exchange, install the
published tool with its generator dependencies:

```bash
python -m pip install "atomref-proatoms[generator]"
```

For lightweight state selection and profile operations without SCF generation:

```bash
python -m pip install atomref-proatoms
```

From a source checkout, use the corresponding editable install from the
repository root:

```bash
python -m pip install -e ".[generator]"
```

See the [Generator tool overview](https://delonecommons.github.io/atomref-proatoms/generator/)
for a dry-run-first
walkthrough suitable for a first local calculation.

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
`generator` extra. See the [Python API](https://delonecommons.github.io/atomref-proatoms/api/)
and the [custom-state scripting guide](https://delonecommons.github.io/atomref-proatoms/generator/scripting/)
for the supported
package-level interface.

## Published data at a glance

The data layer contains four profile/radii/quality-assurance (QA) datasets and
1289 dataset-state rows:

| basis branch | coverage | selected rows | intended use |
|---|---|---:|---|
| `x2c-QZVPall` | H--Rn | 430 | primary/default branch |
| `dyall-v4z` | H--Lr | 501 | primary branch with broader coverage |
| `x2c-QZVPall-s` | H--Rn | 192 | supplemented neutral/anion comparison |
| `dyall-av4z` | H--Ba and Hf--Ra where available | 166 | augmented neutral/anion comparison |

The two primary basis branches are large all-electron quadruple-zeta families
chosen for broad periodic-table coverage and reduced radial basis-set error. The
supplemented/augmented branches are not split by neutral/anion charge class;
they retain their own basis identities and deliberately exclude cations. The
Multiwfn interoperability directory contains 931 `.rad` files for the two
primary branches and 86 neutral-atom `.wfn` files for `x2c-QZVPall`; these are
derived products, not replacements for the profile/radii/QA contract. Generated
data files are stored under:

```text
data/profiles/<dataset_id>/profiles.csv       spherical density rho(r)
data/radii/<dataset_id>/radii.csv             density-cutoff radii
data/qa/<dataset_id>/qa.csv                   per-state validation results
data/multiwfn_artifacts/                      released .rad and .wfn files
```

The [data landing page](https://github.com/DeloneCommons/atomref-proatoms/tree/main/data)
gives the exact dataset IDs, default-basis advice,
file contracts, and interpretation cautions.

The expensive SCF checkpoints, arrays, and logs are regeneration inputs under
ignored `local-data/scf/` paths and are not part of the committed release tables.

## Quality-assurance summary

Every committed profile row passes the current validation criteria. The
validation layer verifies SCF completion, independent electron-count integration,
angular sphericity, finite density values, tail coverage, and cutoff-radius
consistency. The current maximum independent electron-count error is about
`2.5e-12` electrons, and the maximum relative angular density standard deviation
above the QA density floor is about `1.6e-14`.

Diffuse/supplemented basis sensitivity is stored under
`data/qa/basis_sensitivity/`: dyall-v4z → dyall-av4z has 166 matched
neutral/anion rows with 14 high-sensitivity formal-anion outliers, while
x2c-QZVPall → x2c-QZVPall-s has 192 matched neutral/anion rows and no high
outliers. The primary basis-family comparison is stored under
`data/qa/basis_comparisons/` and matches 430 H-Rn states between x2c-QZVPall and
dyall-v4z. These comparison rows are scientific diagnostics, not release failures.

For a compact Methods-style summary of QA, basis comparisons, and recommended
next analyses, see the [Results](https://delonecommons.github.io/atomref-proatoms/results/).

## Validate a source checkout

You do not need to run validation scripts to consume a tagged release. To audit
a source checkout, the fastest release-data consistency checks are:

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

A full maintainer release gate, including the installed-wheel smoke test and
documentation build, is listed in the
[maintainer workflow](https://delonecommons.github.io/atomref-proatoms/workflow/).

## Regeneration workflow

Full release regeneration is a maintainer workflow that requires optional
dependencies, substantial local SCF execution, and the ignored checkpoint layer.
See the [ordered regeneration procedure](https://delonecommons.github.io/atomref-proatoms/workflow/#standard-maintainer-workflow)
and [script reference](https://github.com/DeloneCommons/atomref-proatoms/blob/main/scripts/README.md).
The maintainer scripts provide
`--list` and `--dry-run` modes for inspecting a plan before expensive work.

## Generator examples

The public generator tool has reproducible examples under
[`examples/`](https://github.com/DeloneCommons/atomref-proatoms/tree/main/examples):

- `examples/01_cli_neutral_rad_wfn_bse/` generates neutral Multiwfn `.rad` and
  `.wfn` files for H and B--F from a BSE basis with X2C disabled.
- `examples/02_cli_stockholder_local_basis/` generates stockholder-style
  profiles/radii/QA, `.rad`, and neutral-only `.wfn` outputs from a local NWChem
  basis file.
- `examples/03_python_custom_state_pipeline/` is an expert notebook for custom
  states and project-specific pipelines outside the curated CLI state policies.

The full workflow is explained in the
[generator overview and quick start](https://delonecommons.github.io/atomref-proatoms/generator/).

## Documentation map

- **Scientific note:** [Abstract and scope](https://delonecommons.github.io/atomref-proatoms/) →
  [Introduction](https://delonecommons.github.io/atomref-proatoms/introduction/) →
  [Theory](https://delonecommons.github.io/atomref-proatoms/theory/) →
  [Methods](https://delonecommons.github.io/atomref-proatoms/methods/) →
  [Results](https://delonecommons.github.io/atomref-proatoms/results/) →
  [Discussion](https://delonecommons.github.io/atomref-proatoms/discussion/) →
  [Conclusions](https://delonecommons.github.io/atomref-proatoms/conclusions/).
- **Generator manual:** [overview and quick start](https://delonecommons.github.io/atomref-proatoms/generator/),
  [how-to guide](https://delonecommons.github.io/atomref-proatoms/generator/howto/),
  [CLI reference](https://delonecommons.github.io/atomref-proatoms/generator/cli/),
  [Python scripting](https://delonecommons.github.io/atomref-proatoms/generator/scripting/),
  and [examples](https://delonecommons.github.io/atomref-proatoms/generator/examples/).
- **Data and scientific reference:** [data products](https://delonecommons.github.io/atomref-proatoms/data/),
  [input data](https://delonecommons.github.io/atomref-proatoms/inputs/),
  [state policy](https://delonecommons.github.io/atomref-proatoms/state_policy/), and
  [notebooks](https://delonecommons.github.io/atomref-proatoms/notebooks/).
- **Developer and maintainer reference:** [Python API](https://delonecommons.github.io/atomref-proatoms/api/),
  [workflow and validation](https://delonecommons.github.io/atomref-proatoms/workflow/), and
  [script reference](https://github.com/DeloneCommons/atomref-proatoms/blob/main/scripts/README.md).
- **Project policies:** [license](https://delonecommons.github.io/atomref-proatoms/license/),
  [citation metadata](https://github.com/DeloneCommons/atomref-proatoms/blob/main/CITATION.cff),
  [changelog](https://github.com/DeloneCommons/atomref-proatoms/blob/main/CHANGELOG.md), and
  [AI assistance note](https://delonecommons.github.io/atomref-proatoms/ai_note/).

## Lightweight consumers

This repository is the data-generation and publication-data project. The wheel
contains code, the CLI, schemas, curated state tables, presets, and small service
resources. The full generated profile/radii/QA tables and Multiwfn `.rad`/`.wfn`
files are release data products in the repository and GitHub/Zenodo assets.
Lightweight runtime packages may consume compact generated snapshots from
`data/profiles/`, `data/radii/`, and `data/qa/`, but they should not depend on
PySCF, Basis Set Exchange tooling, external quantum-chemistry programs, or
generator internals.

## Citation

Please cite the atomref-proatoms [concept DOI](https://doi.org/10.5281/zenodo.21291021)
for general use and report the exact release version and dataset ID or basis
branch used. Cite the [version-specific v2.0.0 DOI](https://doi.org/10.5281/zenodo.21291022)
when an immutable reference to the exact archived files is required.

Machine-readable metadata are provided in
[`CITATION.cff`](https://github.com/DeloneCommons/atomref-proatoms/blob/main/CITATION.cff).
See the detailed
[citation, release, and reuse guidance](https://delonecommons.github.io/atomref-proatoms/other/#citation-and-reuse-guidance)
for data-access links and scientific provenance requirements.

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
[`LICENSE.md`](https://github.com/DeloneCommons/atomref-proatoms/blob/main/LICENSE.md)
for the full repository license statement. Machine-readable dataset-release
citation metadata is provided in
[`CITATION.cff`](https://github.com/DeloneCommons/atomref-proatoms/blob/main/CITATION.cff).

Project planning, scientific discussion, code drafting, and documentation drafting
used OpenAI models as assistance tools. The repository author is responsible for
the final scientific content, code, data, validation, and release decisions. See
[`AI_NOTE.md`](https://github.com/DeloneCommons/atomref-proatoms/blob/main/AI_NOTE.md).

[ci-badge]: https://github.com/DeloneCommons/atomref-proatoms/actions/workflows/ci.yml/badge.svg
[ci-workflow]: https://github.com/DeloneCommons/atomref-proatoms/actions/workflows/ci.yml
[pages-badge]: https://github.com/DeloneCommons/atomref-proatoms/actions/workflows/pages.yml/badge.svg
[documentation]: https://delonecommons.github.io/atomref-proatoms/
[zenodo-badge]: https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21291021-blue.svg
[zenodo-doi]: https://doi.org/10.5281/zenodo.21291021
