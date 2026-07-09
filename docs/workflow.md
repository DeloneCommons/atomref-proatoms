# Workflow and code layout

The repository separates released data products from the optional code paths that
create them. Users who only inspect the published tables should not need PySCF.
Maintainers who regenerate SCF artifacts, profiles, radii, QA, or Multiwfn files
need the generator dependencies.

## Package layout

The Python package in `src/atomref_proatoms/` is organized into subpackages with
explicit boundaries:

- `dataio/`: source-tree paths, package resources, schema constants, basis bundles, and profile-dataset configuration;
- `states/`: curated atomic-state records, validation, summaries, and state-table loading;
- `engines/`: PySCF-facing backend helpers and spherical fractional-occupation UKS/UHF machinery;
- `profiles/`: radial grids, density-profile evaluation, build plans, QA helpers, and generated-data writers;
- `exporters/`: Multiwfn `.rad`, PROAIM `.wfn`, and validation-side export helpers;
- `generator/`: public generator planning and execution code;
- `cli/`: the installed `atomref-proatoms` command.

The scripts in `scripts/` remain maintainer entry points for full release-data
regeneration and validation. The public CLI is documented in the
[Generator tool](generator/index.md) section.

## Installation choices

Use the smallest environment that matches the task:

```bash
python -m pip install -e .                 # read data, import package, run lightweight checks
python -m pip install -e ".[generator]"     # run atomref-proatoms generate with PySCF and BSE
python -m pip install -e ".[dev]"           # pytest and ruff for code checks
python -m pip install -e ".[docs]"          # build the MkDocs site
python -m pip install -e ".[generator,dev,docs]"  # maintainer release-check environment
```

The `all` extra remains a convenience umbrella for local development, but the
specific extras above are easier to explain to users. The generator extra now
includes both PySCF and Basis Set Exchange because `bse:` basis sources are a
normal public generator path.

## Data distribution model

The wheel carries code, the CLI, schemas, curated state tables, presets, and
small service resources needed for planning and generation. The full generated
profile/radii/QA tables and the committed Multiwfn `.rad`/`.wfn` interoperability
tree are release data products stored in the repository and mirrored by the
GitHub/Zenodo release assets. Lightweight downstream packages should consume the
stable data products, not generator internals.

## Standard maintainer workflow

Run these commands from the repository root when regenerating the committed data
products:

```bash
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/compute_wavefunctions.py --resume --quiet-scf-log
python scripts/extract_profiles.py --force --check
python scripts/check_basis_sensitivity.py --force
python scripts/check_basis_comparisons.py --force
python scripts/check_profile_artifacts.py --require-generated
python scripts/export_multiwfn_artifacts.py --format all --force --check
python scripts/check_multiwfn_artifacts.py --require-generated
python scripts/prepare_docs.py --write
```

`check_states.py` and `check_basis_bundles.py` validate compact tracked inputs.
`compute_wavefunctions.py` creates or reuses ignored local SCF artifacts.
`extract_profiles.py` reads complete local SCF artifacts and writes profile,
radii, and QA tables. The basis-sensitivity and primary-comparison scripts write
scientific diagnostic QA layers. The Multiwfn exporter writes one combined
manifest for the configured `.rad` files and neutral-only `.wfn` files where the
public contract permits them, so use `--format all` for release regeneration.
`prepare_docs.py --write` reads committed CSV/JSON/YAML data and refreshes
derived documentation tables, figures, and marked Results blocks.

Do not run the SCF or exporter steps just to edit documentation. They are
regeneration steps.

## Inspection commands

These commands inspect configured work without running SCF:

```bash
python scripts/compute_wavefunctions.py --list
python scripts/compute_wavefunctions.py --dry-run
python scripts/extract_profiles.py --list
python scripts/extract_profiles.py --dry-run
python scripts/check_basis_sensitivity.py --dry-run
python scripts/check_basis_comparisons.py --dry-run
python scripts/export_multiwfn_artifacts.py --dry-run
```

They are useful for reviewing selected datasets and states on machines without
PySCF. Use `--show-jobs` with `--list` or `--dry-run` when per-state job lines
are needed; summary mode is the default for full plans.

## Release-readiness checklist

The lightweight release gate is:

```bash
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/check_profile_artifacts.py --require-generated
python scripts/check_multiwfn_artifacts.py --require-generated
python scripts/prepare_docs.py --check
pytest -q
python scripts/smoke_installed_wheel.py --no-build-isolation
mkdocs build --strict
```

The installed-wheel smoke test verifies that package resources and the public CLI
work outside the repository checkout. `mkdocs build --strict` requires the docs
extra. When a clean build environment already has the build backend installed,
`--no-build-isolation` keeps the wheel smoke test usable offline.

A heavier optional release smoke is available:

```bash
python scripts/smoke_installed_wheel.py --with-generator-execution --no-build-isolation
```

That mode installs the generator extra and runs a tiny neutral-H generation path.
It is intentionally optional because it executes SCF.

## Regeneration products

`compute_wavefunctions.py` writes ignored local artifacts under
`local-data/scf/<dataset_id>/<state_id>/`:

```text
scf.chk   PySCF checkpoint
scf.npz   reusable numerical arrays
scf.json  SCF metadata and provenance
scf.log   backend log
```

`extract_profiles.py` reads those local artifacts and writes:

```text
data/profiles/<dataset_id>/profiles.csv and metadata.json
data/radii/<dataset_id>/radii.csv and metadata.json
data/qa/<dataset_id>/qa.csv and metadata.json
data/qa/ aggregate summaries
```

`export_multiwfn_artifacts.py` reads the same local SCF artifacts and writes the
configured Multiwfn interoperability tree under `data/multiwfn_artifacts/`.
Generated profile, radii, QA, and Multiwfn files should be committed together
only after the corresponding check scripts pass. Local SCF artifacts under
`local-data/` remain ignored.

## Documentation build

The documentation site is built with MkDocs:

```bash
python -m pip install -e ".[docs]"
NO_MKDOCS_2_WARNING=1 mkdocs serve
mkdocs build --strict
```

Notebook pages are included in the site without execution. Executing notebooks is
a separate review step because method-demo notebooks may require PySCF.
