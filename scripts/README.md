# Workflow scripts

This directory contains command-line entry points used to validate inputs,
produce local SCF artifacts, and extract released radial-density datasets. The
scripts are intentionally small wrappers around the Python package code so that
workflow behavior is reproducible from the repository root.

## Pipeline order

```bash
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/compute_wavefunctions.py --resume --quiet-scf-log
python scripts/extract_profiles.py --force --check
python scripts/check_basis_sensitivity.py --force
python scripts/check_profile_artifacts.py --require-generated
```

`check_states.py`, `check_basis_bundles.py`, `check_profile_artifacts.py`,
`compute_wavefunctions.py --list`, and `compute_wavefunctions.py --dry-run` do
not require PySCF. Running SCF and extracting profiles from PySCF checkpoint
artifacts require the generator dependency set.

## Script summary

| script | purpose | primary outputs |
|---|---|---|
| `check_states.py` | Validate the active v2 curated atomic-state table without rewriting generated state outputs. | terminal validation report |
| `build_atom_states.py` | Build the active v2 curated atomic-state table from compact source/status CSV files. | `data/states/selection/required_states_v2.csv`, `data/states/curated/atom_states_v2.csv`, `data/states/curated/atom_states_v2.json`, `data/states/curated/atom_states_summary_v2.json` |
| `check_basis_bundles.py` | Validate frozen basis bundles, checksums, NWChem spherical headers, coverage metadata, and optional PySCF parseability. | terminal validation report |
| `compute_wavefunctions.py` | Run spherical fractional-occupation atomic UKS jobs for selected dataset/state pairs. | `local-data/scf/<dataset_id>/<state_id>/` |
| `extract_profiles.py` | Extract radial profiles, cutoff radii, and QA tables from complete local SCF artifacts. | `data/profiles/`, `data/radii/`, `data/qa/` |
| `check_basis_sensitivity.py` | Compare primary and diffuse anion profile branches where both generated datasets are present. | `data/qa/basis_sensitivity/` |
| `check_profile_artifacts.py` | Validate generated profile/radii/QA artifact directories against the active v2 dataset config. | terminal validation report |

## `check_states.py`

Common command:

```bash
python scripts/check_states.py
```

This is the clearest validation command for users and CI jobs that only need to
confirm the active v2 state table. It delegates to the same state-table validator
used by the builder and does not rewrite any generated state outputs.

Options:

- `--data-dir`: directory containing `source/`, `selection/`, and `curated/`;
  default is `data/states`.

## `build_atom_states.py`

Default inputs:

```text
data/states/source/nist_gsie/nist_neutral_cation_states.csv
data/states/source/ning2022/ning2022_monoanions.csv
data/states/curated/formal_atoms_ions.csv
```

Default outputs:

```text
data/states/selection/required_states_v2.csv
data/states/curated/atom_states_v2.csv
data/states/curated/atom_states_v2.json
data/states/curated/atom_states_summary_v2.json
```

Common commands:

```bash
python scripts/build_atom_states.py
python scripts/build_atom_states.py --check
```

Options:

- `--data-dir`: directory containing `source/`, `selection/`, and `curated/`;
  default is `data/states`.
- `--check`: validate the existing curated v2 JSON without rewriting it.

The builder is v2-only in the active codebase. `--check` remains available for
maintainer compatibility, but `scripts/check_states.py` is the preferred
user-facing validation command. Historical v1 state files are kept at
release/tag/archive level, not as live source-tree functionality.

## `check_basis_bundles.py`

Common command:

```bash
python scripts/check_basis_bundles.py
```

The checker validates required bundle files, SHA256 checksums, NWChem spherical
headers, stored BSE metadata, and element coverage intervals. If PySCF is
installed, it also performs small basis-parse smoke checks; otherwise the PySCF
step is reported as skipped.

Options:

- `--basis-root`: basis bundle root; default is `data/basis_sets`.

## `check_basis_sensitivity.py`

Common commands:

```bash
python scripts/check_basis_sensitivity.py --force
python scripts/check_basis_sensitivity.py --profiles-root local-data/profiles --qa-root local-data/qa --force
```

This optional QA step compares radial density profiles for configured primary/diffuse
anion basis pairs. It currently compares `x2c-QZVPall` vs `x2c-QZVPall-s` and
`dyall-v4z` vs `dyall-av4z` when both corresponding generated profile datasets
are present. The output is diagnostic: large basis-sensitivity rows are written as
warnings/outliers, not as automatic release failures.

Outputs:

```text
data/qa/basis_sensitivity/basis_sensitivity.csv
data/qa/basis_sensitivity/basis_sensitivity_summary.csv
data/qa/basis_sensitivity/basis_sensitivity_outliers.csv
data/qa/basis_sensitivity/metadata.json
```

Options:

- `--config`: active dataset YAML; default is `data/profile_datasets.yaml`.
- `--profiles-root`: generated profile artifact root; default is `data/profiles`.
- `--qa-root`: generated QA artifact root; default is `data/qa`.
- `--force`: overwrite existing basis-sensitivity QA outputs.
- `--dry-run`: list configured comparison pairs and whether their profile
  directories are present.
- `--warn-relative-l1`: warning threshold for integrated relative L1 density
  difference.
- `--warn-delta-radius-angstrom`: warning threshold for radius shifts in Å.

## `check_profile_artifacts.py`

Common commands:

```bash
python scripts/check_profile_artifacts.py
python scripts/check_profile_artifacts.py --require-generated
```

Before profile generation, the default command passes cleanly when no generated
profile/radii/QA dataset directories are present. After generation, the release
gate is `--require-generated`: it checks that dataset directories under
`data/profiles/`, `data/radii/`, and `data/qa/` exactly match the active dataset
IDs, carry the configured `profile_data_version`, and have matching state rows,
profile columns, metadata, and QA overview files.

Options:

- `--config`: active dataset YAML; default is `data/profile_datasets.yaml`.
- `--states-file`: active curated state JSON; default is
  `data/states/curated/atom_states_v2.json`.
- `--profiles-root`, `--radii-root`, `--qa-root`: generated artifact roots.
- `--require-generated`: fail if no generated dataset artifacts are present.
- `--allow-partial`: permit a matching subset of configured datasets for
  incremental local work.
- `--allow-qa-failures`: inspect artifact consistency without treating QA
  failures as a checker failure.

## `compute_wavefunctions.py`

Common inspection commands:

```bash
python scripts/compute_wavefunctions.py --list
python scripts/compute_wavefunctions.py --dry-run
python scripts/compute_wavefunctions.py --dataset pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2 --show-jobs --list
```

Production command shape:

```bash
python scripts/compute_wavefunctions.py --resume --quiet-scf-log
```

Outputs:

```text
local-data/scf/<dataset_id>/<state_id>/
  scf.chk
  scf.npz
  scf.json
  scf.log
```

Selection options:

- `--config`: profile dataset YAML; default is `data/profile_datasets.yaml`.
- `--dataset`, `--dataset-id`: select one dataset; may be repeated. `all` selects
  all configured datasets.
- `--state`, `--state-id`: restrict to one state ID; may be repeated.
- `--scf-root`: local SCF artifact root; default is `local-data/scf`.

Execution options:

- `--resume`: reuse matching complete, converged local SCF artifacts.
- `--force`: regenerate even when reusable artifacts exist.
- `--continue-on-error`: continue remaining selected jobs after a failed SCF.
- `--quiet-scf-log`: write PySCF output to `scf.log` without echoing it to
  stdout.
- `--allow-pyscf-version-mismatch`: permit a PySCF version different from the
  expected release version in `data/profile_datasets.yaml`; intended only for
  debugging.

Method/debug options:

- `--no-x2c`: disable scalar X2C for debugging.
- `--xc`: override the configured exchange-correlation functional.
- `--conv-tol`: override SCF convergence tolerance.
- `--max-cycle`: override maximum SCF cycles; the v2 dataset default is 300.
- `--grid-level`: override PySCF DFT grid level.
- `--verbose`: set PySCF verbosity.

Planning options:

- `--list`: print the selected build plan and exit before running PySCF.
- `--dry-run`: validate and print the plan before importing or running PySCF.
- `--show-jobs`: print every selected state/dataset job.

## `extract_profiles.py`

Common inspection commands:

```bash
python scripts/extract_profiles.py --list
python scripts/extract_profiles.py --dry-run
```

Production command shape:

```bash
python scripts/extract_profiles.py --force --check
```

Outputs:

```text
data/profiles/<dataset_id>/profiles.csv
data/profiles/<dataset_id>/metadata.json
data/radii/<dataset_id>/radii.csv
data/radii/<dataset_id>/metadata.json
data/qa/<dataset_id>/qa.csv
data/qa/<dataset_id>/metadata.json
data/qa/qa_summary.csv
data/qa/qa_report.md
data/qa/metadata.json
```

Selection and path options:

- `--config`: active dataset YAML; default is `data/profile_datasets.yaml`.
- `--dataset`, `--dataset-id`: select one dataset; may be repeated. `all` selects
  all configured datasets.
- `--state`, `--state-id`: restrict to one state ID; may be repeated.
- `--scf-root`: local SCF artifact root; default is `local-data/scf`.
- `--output-root`, `--profiles-root`: profile output root; default is
  `data/profiles`.
- `--radii-root`: radii output root; default is `data/radii`.
- `--qa-root`: QA output root; default is `data/qa`.

Execution and QA options:

- `--force`: overwrite existing dataset outputs.
- `--check`: check written or existing datasets after extraction.
- `--dry-run`: validate and print a summary of required SCF artifacts before
  importing PySCF.
- `--list`: print the selected extraction plan and exit.
- `--show-jobs`: with `--list` or `--dry-run`, print every selected
  state/dataset job.
- `--no-profile-qa`: skip independent electron-count QA during extraction.
- `--continue-on-error`: continue remaining datasets after one extraction
  failure.
- `--angular-points`: override angular grid size for stored-profile density
  evaluation.

## Related documentation

- Scientific model: `docs/theory.md`.
- Data products: `docs/data.md`.
- Input data: `docs/inputs.md`.
- State policy: `docs/state_policy.md`.
- MkDocs overview: `docs/index.md`.
