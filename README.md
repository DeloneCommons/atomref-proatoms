# atomref-proatoms

`atomref-proatoms` is the heavy generator/data companion repository for `atomref`.
It stores frozen atomic-state and basis-set inputs and generates reusable radial
proatomic electron-density profiles for neutral atoms in the v1 release. The curated state
layer still keeps selected ion definitions for later explicitly labeled v2 datasets.

The main downstream use is empirical geometry and IAS-separator estimation in
crystallographic and atom-centered software. The project is not intended to be a
high-accuracy atomic spectroscopy benchmark.

## Current version

The active profile-data version is `1.0.0.dev0`. Dataset identifiers use the `_v1`
suffix and are declared in a single file:

```text
data/profile_datasets.yaml
```

Older generator/data behavior should be preserved by Git tags, GitHub releases, and
Zenodo records rather than by keeping multiple historical workflow layers in the active
branch.

## What is included

This repository contains:

- curated atomic-state inputs under `data/states/`;
- frozen BSE NWChem spherical basis exports under `data/basis_sets/`;
- the active profile dataset specification in `data/profile_datasets.yaml`;
- lightweight Python utilities for loading and validating state, basis, dataset, and
  profile metadata;
- offline data-check scripts;
- the simplified v1 workflow entry points.

The v1 profile datasets are neutral-only. Cations, anions, formal anions, charge-state
interpolation, and diffuse-anion sensitivity branches are intentionally postponed until a
separate v2 scope is justified and documented.

Generated profile datasets are not tracked yet in this patch. The target release layout is:

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

## What this repository is not

This repository is not the lightweight runtime package. The `atomref` package should stay
small and should not depend on PySCF, Basis Set Exchange, Multiwfn, Gaussian, or generator
internals. Future `atomref` integration should use compact released profile snapshots only.

This repository also does not download basis sets during normal operation. The frozen
`data/basis_sets/**/basis.nw` files define the basis-data identity.

## Data checks

From the repository root:

```bash
python scripts/check_basis_bundles.py
python scripts/build_atom_states.py --check
pytest
```

`check_basis_bundles.py` is fully offline by default. If PySCF is installed, it also runs
small optional parse smoke checks for representative elements. If PySCF is absent, that
step is explicitly skipped.

The package itself must remain importable without PySCF:

```bash
python -c "import atomref_proatoms; print(atomref_proatoms.__version__)"
```

## Simplified v1 workflow

The intended workflow is now four production scripts:

```bash
python scripts/build_atom_states.py --check
python scripts/check_basis_bundles.py
python scripts/compute_wavefunctions.py --resume --quiet-scf-log
python scripts/extract_profiles.py --force --check
```

`compute_wavefunctions.py --list` and `--dry-run` already read the active YAML config and
show the selected state/dataset jobs without importing PySCF:

```bash
python scripts/compute_wavefunctions.py --list
python scripts/compute_wavefunctions.py \
  --dataset pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v1 \
  --state H_q0_mult2_hund \
  --dry-run
```

`compute_wavefunctions.py` writes persistent local SCF artifacts. The release generator
extra pins PySCF to `2.13.1`, and the script refuses to create release artifacts with a
different PySCF version unless `--allow-pyscf-version-mismatch` is used for debugging.

`compute_wavefunctions.py` writes persistent local SCF artifacts:

```text
local-data/scf/<dataset_id>/<state_id>/
  scf.chk
  scf.npz
  scf.json
  scf.log
```

`extract_profiles.py` reads those local SCF artifacts without rerunning SCF and writes the
tracked wide profile table plus aggregate metadata JSON under `data/profiles/`:

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

## Layout

```text
src/atomref_proatoms/    lightweight loaders, validators, schema helpers, generator code
data/profile_datasets.yaml
                         active profile dataset specification
data/states/            source / selection / curated state data
data/basis_sets/        frozen BSE NWChem spherical basis exports
data/profiles/          final generated profile datasets, one directory per dataset
data/radii/            generated cutoff-radius result tables
data/qa/               generated QA tables and compact Markdown QA status
scripts/                simplified v1 workflow entry points and data checks
tests/                  unit and integration tests
docs/                   project documentation and narrative notebooks
local-data/             ignored local SCF/checkpoint/log/scratch artifacts
```

## Optional generator dependencies

Install PySCF only on machines that will run the generator:

```bash
python -m pip install -e ".[generator,test,dev]"
python scripts/check_basis_bundles.py
pytest -m "not slow"
```

Default checks do not require internet access and do not compare frozen basis files against
the current Basis Set Exchange API response.
