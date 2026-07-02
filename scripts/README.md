# Workflow scripts

This directory contains the command-line entry points used to validate inputs,
produce local SCF artifacts, and extract released radial-density datasets. The
scripts are intentionally small wrappers around the Python package code so that
the release workflow is reproducible from the repository root.

## Pipeline order

```bash
python scripts/build_atom_states.py --check
python scripts/check_basis_bundles.py
python scripts/compute_wavefunctions.py --resume --quiet-scf-log
python scripts/extract_profiles.py --force --check
```

`build_atom_states.py --check`, `check_basis_bundles.py`,
`compute_wavefunctions.py --list`, and `compute_wavefunctions.py --dry-run` do
not require PySCF. Running SCF and extracting profiles from PySCF checkpoint
artifacts require the generator dependency set.

## Script summary

| script | purpose | primary outputs |
|---|---|---|
| `build_atom_states.py` | Build or validate curated atomic-state JSON records from compact source and selection CSV files. | `data/states/curated/atom_states_v1.json`, `data/states/curated/atom_states_summary.json` |
| `check_basis_bundles.py` | Validate frozen basis bundles, checksums, NWChem spherical headers, coverage metadata, and optional PySCF parseability. | terminal validation report |
| `compute_wavefunctions.py` | Run spherical fractional-occupation atomic UKS jobs for selected dataset/state pairs. | `local-data/scf/<dataset_id>/<state_id>/` |
| `extract_profiles.py` | Extract radial profiles, cutoff radii, and QA tables from complete local SCF artifacts. | `data/profiles/`, `data/radii/`, `data/qa/` |

## `build_atom_states.py`

Default inputs:

```text
data/states/source/atom_configs_nist_source.csv
data/states/source/atom_configs_formal_anions.csv
data/states/selection/required_states_v1.csv
```

Default outputs:

```text
data/states/curated/atom_states_v1.json
data/states/curated/atom_states_summary.json
```

Common commands:

```bash
python scripts/build_atom_states.py
python scripts/build_atom_states.py --check
```

Options:

- `--data-dir`: directory containing `source/` and `selection/`; default is
  `data/states`.
- `--selection-file`: explicit state-selection CSV; default is
  `<data-dir>/selection/required_states_v1.csv`.
- `--out-dir`: output directory for curated JSON files; default is
  `<data-dir>/curated`.
- `--check`: validate the existing curated JSON without rewriting it.

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

## `compute_wavefunctions.py`

Common inspection commands:

```bash
python scripts/compute_wavefunctions.py --list
python scripts/compute_wavefunctions.py --dry-run
python scripts/compute_wavefunctions.py --dataset pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v1 --show-jobs --list
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
- `--dataset`, `--dataset-id`: select one dataset; may be repeated. `all` and
  `all_v1` select all configured v1 datasets.
- `--state`, `--state-id`: restrict to one state ID; may be repeated.
- `--scf-root`: local SCF artifact root; default is `local-data/scf`.

Execution options:

- `--resume`: reuse matching complete local SCF artifacts.
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
- `--max-cycle`: override maximum SCF cycles.
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
- `--dataset`, `--dataset-id`: select one dataset; may be repeated. `all` and
  `all_v1` select all configured v1 datasets.
- `--state`, `--state-id`: restrict to one state ID; may be repeated.
- `--scf-root`: local SCF artifact root; default is `local-data/scf`.
- `--output-root`, `--profiles-root`: profile output root; default is
  `data/profiles`.
- `--radii-root`: radii output root; default is `data/radii`.
- `--qa-root`: QA output root; default is `data/qa`.

Execution and QA options:

- `--force`: overwrite existing dataset outputs.
- `--check`: check written or existing datasets after extraction.
- `--dry-run`: validate and print required SCF artifacts before importing PySCF.
- `--list`: print the selected extraction plan and exit.
- `--no-profile-qa`: skip independent electron-count QA during extraction.
- `--continue-on-error`: continue remaining datasets after one extraction
  failure.
- `--angular-points`: override angular grid size for stored-profile density
  evaluation.

## Related documentation

- Scientific model: `docs/theory.md`.
- Data products: `docs/data.md`.
- Input data: `docs/inputs.md`.
- MkDocs overview: `docs/index.md`.
