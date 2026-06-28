# atomref-proatoms

`atomref-proatoms` is the heavy generator/data companion repository for `atomref`.
It stores frozen atomic-state and basis-set inputs, implements checks around those inputs,
and will later generate reusable radial proatomic electron-density profiles for atoms and
selected ions.

The main downstream use is empirical geometry and IAS-separator estimation in
crystallographic and atom-centered software. The project is not intended to be a
high-accuracy atomic spectroscopy benchmark.

## What is included now

This first repository skeleton contains:

- the curated atomic-state data layer copied from `atomref-proatoms-data-v2.zip`;
- the frozen basis-set bundles copied from `atomref-proatoms-data-v2.zip`;
- lightweight Python utilities for loading and validating basis/state/profile metadata;
- offline data-check scripts;
- unit tests for the frozen data layer and initial metadata helpers;
- documentation placeholders for the next stages.

It intentionally does not contain generated radial profiles yet.

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
python scripts/build_atom_states.py
python scripts/check_states.py
pytest
```

`check_basis_bundles.py` is fully offline by default. If PySCF is installed, it also runs
small optional parse smoke checks for representative elements. If PySCF is absent, that
step is explicitly skipped.

## Optional PySCF smoke checks

On a local machine with PySCF installed:

```bash
python -m pip install -e ".[generator,test,dev]"
# or install every optional mode at once:
python -m pip install -e ".[all]"
python scripts/check_basis_bundles.py
pytest -m "not slow"
```

The package itself must remain importable without PySCF:

```bash
python -c "import atomref_proatoms; print(atomref_proatoms.__version__)"
```

## Layout

```text
src/atomref_proatoms/    lightweight loaders, validators, schema helpers
data/states/            source / selection / curated state data
data/basis_sets/        frozen BSE NWChem spherical basis exports
data/profiles/          reserved for future generated profile datasets
scripts/                data checks and future build entry points
tests/                  unit and integration tests
docs/                   project documentation placeholders
local-data/             ignored local SCF/checkpoint/scratch artifacts
```

## Generator status

The first pilot generator path is available through `scripts/run_dataset.py`. It keeps
PySCF imports lazy and is intended for local smoke tests before full dataset builds.
Generated profile artifacts default to per-state `.csv.zip` archives plus JSON metadata.

Example dry run without PySCF:

```bash
python scripts/run_dataset.py \
  --state-id H_q0_mult2_hund \
  --dataset-id pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0 \
  --dry-run
```

Example local PySCF smoke run with fast/skipped independent electron-count QA:

```bash
python scripts/run_dataset.py \
  --state-id H_q0_mult2_hund \
  --dataset-id pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0 \
  --no-profile-qa \
  --profile-n-ang 50
```

Example local PySCF smoke run with the independent profile QA enabled:

```bash
python scripts/run_dataset.py \
  --state-id H_q0_mult2_hund \
  --dataset-id pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0 \
  --profile-n-ang 50 \
  --qa-n-r 120 \
  --qa-n-ang 50
```

In this context, QA means generated-profile quality assurance: SCF convergence,
independent radial electron-count integration, density-tail coverage for cutoff radii,
monotonic cutoff radii, nonnegative finite density values, and angular-sigma checks that
confirm the supposedly spherical density is nearly angle-independent.

Validate generated pilot artifacts without running PySCF:

```bash
python scripts/check_profiles.py \
  --dataset-dir local-data/pilot-profiles/pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0
```

Use `--require-profile-qa` when checking artifacts that should include independent
electron-count QA rather than skipped/null QA fields. Full profile generation should
proceed only after pilot profiles pass metadata and QA checks.
