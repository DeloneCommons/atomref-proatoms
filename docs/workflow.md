# Workflow and code layout

The repository separates lightweight loading/validation utilities from the
optional SCF generator. Users who only read released data products should not need
PySCF. PySCF is required only for local regeneration of SCF artifacts and radial
profiles.

## Package layout

The Python package in `src/atomref_proatoms/` is organized into v2 subpackages with explicit boundaries:

- `dataio/`: source-tree paths, schema constants, basis bundles, and profile-dataset configuration;
- `states/`: curated atomic-state records, validation, summaries, and state-table loading;
- `engines/`: PySCF-facing backend helpers and spherical fractional-occupation UKS machinery;
- `profiles/`: radial grids, density-profile evaluation, build plans, QA helpers, and release-artifact writers.

The current code does not yet create `exporters/` or `cli/` packages because no Multiwfn exporters or final user-facing generator commands are implemented in this stage. Historical top-level import modules remain as thin compatibility re-export shims, but new package code and maintainer scripts should prefer the subpackage imports.

The public scripts in `scripts/` are small workflow entry points around this
package code. Their detailed command-line options are documented in
`scripts/README.md`.

## Standard workflow

Run the workflow checks from the repository root:

```bash
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/compute_wavefunctions.py --resume --quiet-scf-log
python scripts/extract_profiles.py --force --check
```

`check_states.py` and `check_basis_bundles.py` validate compact tracked inputs. The third command creates
or reuses ignored local SCF artifacts. The fourth command extracts tracked
profile, radii, and QA artifacts from complete local SCF material.

## Inspection commands

These commands inspect the configured work without running SCF:

```bash
python scripts/compute_wavefunctions.py --list
python scripts/compute_wavefunctions.py --dry-run
python scripts/extract_profiles.py --list
python scripts/extract_profiles.py --dry-run
```

They are useful for reviewing selected datasets and states on machines without
PySCF.

## Generator dependencies

Install generator dependencies only where SCF generation will be run:

```bash
python -m pip install -e ".[generator,test,dev]"
```

The release configuration expects PySCF `2.13.1`. `compute_wavefunctions.py`
refuses to create release artifacts with a different PySCF version unless
`--allow-pyscf-version-mismatch` is supplied for debugging.

## Regeneration products

`compute_wavefunctions.py` writes ignored local artifacts under
`local-data/scf/<dataset_id>/<state_id>/`:

- `scf.chk`: PySCF checkpoint;
- `scf.npz`: reusable numerical arrays;
- `scf.json`: SCF metadata and provenance;
- `scf.log`: backend log.

`extract_profiles.py` reads those local artifacts and writes:

- `data/profiles/<dataset_id>/profiles.csv` and `metadata.json`;
- `data/radii/<dataset_id>/radii.csv` and `metadata.json`;
- `data/qa/<dataset_id>/qa.csv` and `metadata.json`;
- aggregate QA files under `data/qa/`.

The generated profile, radii, and QA files should be committed together after the
QA report has been inspected.

## Documentation build

The documentation site is built with MkDocs:

```bash
python -m pip install -e ".[docs]"
NO_MKDOCS_2_WARNING=1 mkdocs serve
```

Notebook pages are included in the site without execution. Executing notebooks is
a separate review step because method-demo notebooks may require PySCF.
