# atomref-proatoms

`atomref-proatoms` provides reproducible spherical proatomic radial
electron-density datasets generated from explicitly declared atomic-state, basis,
method, radial-grid, and quality-assurance conventions. The v1 release focuses
on neutral free atoms and publishes canonical radial profiles, density-cutoff
radii, and QA tables for use in atom-centered theoretical-chemistry,
crystallographic, empirical density/radius, and promolecular-density workflows.

The project is not intended to be a high-accuracy atomic spectroscopy benchmark.
Its purpose is to provide consistent quantum-chemical reference densities with a
transparent sphericalization convention and release-level provenance.

## Current version

The active profile-data version is `1.0.0.dev0`. Dataset identifiers use the `_v1`
suffix and are declared in a single file:

```text
data/profile_datasets.yaml
```

The active v1 profile datasets are neutral-only:

```text
pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v1
pbe0_sfx2c_dyallv4z_h-lr_spherical_v1
```

## What is included

This repository contains:

- compact atomic-state source and curated generator inputs under `data/states/`;
- frozen BSE NWChem spherical basis exports under `data/basis_sets/`;
- the active profile dataset specification in `data/profile_datasets.yaml`;
- generated radial profile datasets under `data/profiles/`;
- generated density-cutoff radii under `data/radii/`;
- generated release-gate QA tables under `data/qa/`;
- lightweight Python utilities for loading and validating state, basis, dataset,
  profile, radii, and QA metadata;
- workflow scripts for state generation, basis checks, local SCF generation, and
  profile extraction.

Generated profile, radii, and QA artifacts use this release layout:

```text
data/profiles/<dataset_id>/
  profiles.csv
  metadata.json

data/radii/<dataset_id>/
  radii.csv
  metadata.json

data/qa/<dataset_id>/
  qa.csv
  metadata.json
```

`local-data/scf/` is an ignored local artifact directory for SCF checkpoints,
logs, and array bundles. It is required to regenerate the released data products
but is not part of the public data release.

## Relationship to lightweight consumers

This repository is the data-generation and release-artifact project. Lightweight
runtime packages may consume compact released snapshots from this repository, but
they should not depend on PySCF, Basis Set Exchange tooling, external
quantum-chemistry programs, or generator internals.

The frozen `data/basis_sets/**/basis.nw` files define the basis-data identity.
Normal validation and release checks do not download basis sets from external
services.

## Data checks

From the repository root:

```bash
python scripts/check_basis_bundles.py
python scripts/build_atom_states.py --check
pytest
```

`check_basis_bundles.py` is fully offline by default. If PySCF is installed, it
also runs small optional parse smoke checks for representative elements. If PySCF
is absent, that step is explicitly skipped.

The package itself must remain importable without PySCF:

```bash
python -c "import atomref_proatoms; print(atomref_proatoms.__version__)"
```

## v1 workflow

The v1 workflow uses four production scripts:

```bash
python scripts/build_atom_states.py --check
python scripts/check_basis_bundles.py
python scripts/compute_wavefunctions.py --resume --quiet-scf-log
python scripts/extract_profiles.py --force --check
```

`compute_wavefunctions.py --list` and `--dry-run` read the active YAML config and
show the selected state/dataset jobs without importing PySCF:

```bash
python scripts/compute_wavefunctions.py --list
python scripts/compute_wavefunctions.py \
  --dataset pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v1 \
  --state H_q0_mult2_hund \
  --dry-run
```

`compute_wavefunctions.py` writes persistent local SCF artifacts under
`local-data/scf/`. The release generator extra pins PySCF to `2.13.1`, and the
script refuses to create release artifacts with a different PySCF version unless
`--allow-pyscf-version-mismatch` is used for debugging.

```text
local-data/scf/<dataset_id>/<state_id>/
  scf.chk
  scf.npz
  scf.json
  scf.log
```

`extract_profiles.py` reads those local SCF artifacts without rerunning SCF and
writes the tracked wide profile table, cutoff-radius table, QA table, and
aggregate metadata under `data/profiles/`, `data/radii/`, and `data/qa/`.

## Layout

```text
src/atomref_proatoms/   loaders, validators, schema helpers, and generator code
data/profile_datasets.yaml
                        active profile dataset specification
data/states/           source, selection, and curated atomic-state data
data/basis_sets/       frozen BSE NWChem spherical basis exports
data/profiles/         generated profile datasets, one directory per dataset
data/radii/            generated cutoff-radius result tables
data/qa/               generated QA tables and compact Markdown QA status
scripts/               workflow entry points and data checks
tests/                 test suite
docs/                  project documentation and notebooks
local-data/            ignored local SCF/checkpoint/log/scratch artifacts
```

## Documentation map

```text
docs/theory.md
  Scientific model for the v1 spherical proatomic density profiles.

docs/data_layout.md
  Tracked inputs, generated release artifacts, and ignored local SCF artifacts.

docs/basis_sets.md
  Basis-set layer summary and validation entry point.

docs/state_curation.md
  Atomic-state curation model and generated state-table contract.

docs/multiwfn_interop.md
  Boundary for adapting v1 radial-density data to Multiwfn-related workflows.

docs/notebooks/
  User-facing notebooks that inspect generated release artifacts.
```

## Optional generator dependencies

Install PySCF only on machines that will run the generator:

```bash
python -m pip install -e ".[generator,test,dev]"
python scripts/check_basis_bundles.py
pytest -m "not slow"
```

Default checks do not require internet access and do not compare frozen basis
files against the current Basis Set Exchange API response.
