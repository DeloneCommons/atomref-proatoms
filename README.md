# atomref-proatoms

[![CI][ci-badge]][ci-workflow]
[![Pages][pages-badge]][pages-workflow]

`atomref-proatoms` publishes reproducible spherical proatomic radial electron-density
profiles for isolated atoms and ions. The data are intended for atom-centered
reference-density models: stockholder and Hirshfeld-like analyses, promolecular
density construction, deformation-density inspection, empirical radius models,
and related cheminformatics or crystallographic workflows that need a documented
atomic reference convention.

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

The committed data layer contains four profile/radii/QA datasets and 1128
dataset-state rows:

| dataset ID | basis | selected rows | role |
|---|---|---:|---|
| `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2` | `x2c-QZVPall` | 430 | primary H-Rn |
| `pbe0_sfx2c_dyallv4z_h-lr_spherical_v2` | `dyall-v4z` | 501 | primary H-Lr |
| `pbe0_sfx2c_x2cqzvpalls_h-rn_anions_spherical_v2` | `x2c-QZVPall-s` | 106 | supplemented H-Rn anions |
| `pbe0_sfx2c_dyallav4z_h-ba_hf-ra_anions_spherical_v2` | `dyall-av4z` | 91 | augmented selected anions |

The two primary basis branches are large all-electron quadruple-zeta families
chosen for broad periodic-table coverage and reduced radial basis-set error. The
supplemented/augmented anion branches are separate sensitivity branches and
retain their own basis identities. Generated artifacts are stored under:

```text
data/profiles/<dataset_id>/profiles.csv
data/radii/<dataset_id>/radii.csv
data/qa/<dataset_id>/qa.csv
```

The expensive SCF checkpoints, arrays, and logs are regeneration inputs under
ignored `local-data/scf/` paths and are not part of the committed release tables.

## Quality-assurance summary

Every committed profile row passes the current release gate. The gate verifies
SCF completion, independent electron-count integration, angular sphericity,
finite density values, tail coverage, and cutoff-radius consistency. The current
maximum independent electron-count error is about `2.5e-12` electrons, and the
maximum relative angular density standard deviation above the QA density floor is
about `1.6e-14`.

Diffuse/supplemented basis sensitivity is stored under
`data/qa/basis_sensitivity/`. The dyall augmented comparison shows large and
scientifically meaningful tail sensitivity for a small set of formal/high-charge
anions; the x2c supplemented comparison is very small for the current anion set.
These sensitivity rows are scientific diagnostics, not release failures.

For a compact Methods-style summary of QA, basis comparisons, and recommended
next analyses, see the [scientific data-layer report](docs/data_layer_report.md).

## How to inspect the data

The fastest consistency checks are:

```bash
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/check_profile_artifacts.py --require-generated
pytest
```

`check_basis_bundles.py` is fully offline by default. If PySCF is installed, it
also runs representative parse smoke checks for the frozen basis files; otherwise
those smoke checks are reported as skipped.

The lightweight package layer remains importable without PySCF:

```bash
python -c "import atomref_proatoms; print(atomref_proatoms.__version__)"
```

## Regeneration workflow

Full regeneration requires the optional generator dependencies and complete local
SCF execution:

```bash
python -m pip install -e ".[generator,test,dev]"
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/compute_wavefunctions.py --resume --quiet-scf-log
python scripts/extract_profiles.py --force --check
python scripts/check_basis_sensitivity.py --include-x2c-optional --force
python scripts/check_profile_artifacts.py --require-generated
```

The `--list` and `--dry-run` options on `compute_wavefunctions.py` and
`extract_profiles.py` inspect the active build plan without running SCF or
rewriting generated artifacts. `scripts/build_data_layer_report.py` only reads
committed tables and regenerates `docs/data_layer_report.md`.

## Documentation map

- [Scientific model](docs/theory.md): spherical fractional-occupation proatoms,
  radial profiles, cutoff radii, and independent QA integration.
- [Scientific data-layer report](docs/data_layer_report.md): generated narrative
  summary of QA, basis comparisons, sensitivity patterns, and pending analyses.
- [Data products](docs/data.md): profile, radii, QA, and basis-sensitivity file
  contracts.
- [Input data](docs/inputs.md): basis bundles and atomic-state curation.
- [State policy](docs/state_policy.md): state-source hierarchy, formal anion
  meaning, and interpretation limits.
- [Workflow](docs/workflow.md): scripts, package layout, and regeneration steps.
- [Notebooks](docs/notebooks/README.md): artifact-inspection and sphericalization
  demonstration notebooks.
- [License](docs/license.md) and [AI assistance note](docs/ai_note.md).

## Lightweight consumers

This repository is the data-generation and release-artifact project. Lightweight
runtime packages may consume compact generated snapshots from `data/profiles/`,
`data/radii/`, and `data/qa/`, but they should not depend on PySCF, Basis Set
Exchange tooling, external quantum-chemistry programs, or generator internals.

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
