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
  --profile-n-ang 110 \
  --qa-n-r 400 \
  --qa-n-ang 110
```

In this context, QA means generated-profile quality assurance: SCF convergence,
independent radial electron-count integration, density-tail coverage for cutoff radii,
monotonic cutoff radii, nonnegative finite density values, and angular-sigma checks that
confirm the supposedly spherical density is nearly angle-independent.

The default strict checker tolerance for independent electron-count QA is
`max(2e-6, 2e-7 * electron_count)` electrons. This keeps light atoms strict while
avoiding false failures for heavy Dyall pilots on finite QA quadrature grids.

Generated metadata also records backend diagnostics that are not pass/fail QA targets:
PySCF-reported `<S^2>`/multiplicity values and parsed overlap-linear-dependency warnings.
For spherical fractional-occupation proatoms the reported `<S^2>` can differ from the
formal target spin, so it is kept for auditability rather than used as a release check.

After the H smoke profile is stable, run the light neutral pilot batch with the same
profile/QA settings.  The `--build-indexes` flag writes the planned dataset-level
`dataset_manifest.json`, `profile_index.csv`, and `derived_radii.csv` files after
the per-state profile checks pass:

```bash
python scripts/run_pilots.py \
  --group neutral_light_x2c \
  --profile-n-ang 110 \
  --qa-n-r 400 \
  --qa-n-ang 110 \
  --check-profiles \
  --require-profile-qa \
  --build-indexes \
  --summary
```

Available pilot groups can be listed without PySCF:

```bash
python scripts/run_pilots.py --list
```

Validate generated pilot artifacts without running PySCF:

```bash
python scripts/check_profiles.py \
  --dataset-dir local-data/pilot-profiles/pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0
```

Build and validate dataset-level index files after profiles are generated:

```bash
python scripts/build_dataset_index.py \
  --dataset-dir local-data/pilot-profiles/pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0 \
  --require-profile-qa

python scripts/check_dataset.py \
  --dataset-dir local-data/pilot-profiles/pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0 \
  --require-profile-qa \
  --summary

python scripts/summarize_dataset.py \
  --dataset-dir local-data/pilot-profiles/pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0
```


After more than one pilot group has been generated, validate the expected pilot-output root
rather than checking each dataset directory manually. This is useful when the primary light
neutral dataset and the diffuse anion/formal-anion sensitivity dataset coexist under the
same `local-data/pilot-profiles/` root:

```bash
python scripts/check_pilot_outputs.py \
  --output-dir local-data/pilot-profiles \
  --group neutral_light_x2c \
  --group anion_formal_x2c_diffuse \
  --require-profile-qa \
  --summary
```

Run the first diffuse anion/formal-anion pilot group as a separate sensitivity dataset:

```bash
python scripts/run_pilots.py \
  --group anion_formal_x2c_diffuse \
  --profile-n-ang 110 \
  --qa-n-r 400 \
  --qa-n-ang 110 \
  --check-profiles \
  --require-profile-qa \
  --build-indexes \
  --summary
```

This group writes to `pbe0_sfx2c_x2cqzvpall-s_h-rn_anioncheck_v0`, not to the
primary non-diffuse H-Rn dataset. The pilot-output checker verifies that selected
pilot states appear in their expected dataset directories, helping prevent accidental
mixing of primary and sensitivity outputs.

The remaining recommended pilot calculations cover the Dyall augmented anion branch
and the heavy Dyall smoke states:

```bash
python scripts/run_pilots.py \
  --group remaining_dyall_pilots \
  --profile-n-ang 110 \
  --qa-n-r 400 \
  --qa-n-ang 110 \
  --check-profiles \
  --require-profile-qa \
  --build-indexes \
  --summary
```

To rerun the entire pilot suite in one command, use `full_pilot_suite`. This includes
light neutral x2c profiles, x2c diffuse anion/formal-anion checks, Dyall-av4z
anion/formal-anion checks, Eu3+, and neutral U:

```bash
python scripts/run_pilots.py \
  --group full_pilot_suite \
  --profile-n-ang 110 \
  --qa-n-r 400 \
  --qa-n-ang 110 \
  --check-profiles \
  --require-profile-qa \
  --build-indexes \
  --summary
```

Package selected pilot outputs into one ZIP archive for review:

```bash
python scripts/package_pilot_outputs.py \
  --group full_pilot_suite \
  --archive local-data/pilot-profiles-full_pilot_suite.zip
```

Use `--require-profile-qa` when checking artifacts that should include independent
electron-count QA rather than skipped/null QA fields. The summary command prints compact
counts for profiles, elements, charge states, state categories, QA coverage, and derived
radius ranges. Full profile generation should proceed only after pilot profiles pass
metadata and QA checks.

## Full dataset build orchestration

After the pilot suite is stable, use `scripts/run_dataset_build.py` for resumable
full-dataset generation from the curated v0 state selection. It derives dataset
membership from `data/states/curated/atom_states_v0.json` and the dataset scope table,
so no state can silently fall back to another basis or dataset.

List the planned jobs without PySCF:

```bash
python scripts/run_dataset_build.py --list
```

Build one dataset, skipping existing state artifacts by default and writing indexes after
successful profile checks:

```bash
python scripts/run_dataset_build.py \
  --dataset-id pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0 \
  --check-profiles \
  --require-profile-qa \
  --build-indexes \
  --summary
```

Useful chunking/resume options:

```bash
python scripts/run_dataset_build.py --dataset-id all --limit 20
python scripts/run_dataset_build.py --dataset-id all --start-after-state-id Xe_q0_mult1_hund
python scripts/run_dataset_build.py --dataset-id all --only-state-id I_qm1_mult1_hund
```

Use `--force` only when existing per-state artifacts should be regenerated.
