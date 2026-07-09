# Other material and repository reference

## Data dictionaries

Detailed file contracts remain in the data-directory README files:

- `data/states/README.md` for the state source and curated state layer;
- `data/basis_sets/README.md` for frozen all-electron basis bundles;
- `data/profiles/README.md` for profile CSV and metadata fields;
- `data/radii/README.md` for density-cutoff radii fields;
- `data/qa/README.md` for validation, basis-sensitivity, and comparison artifacts.

These pages are data dictionaries and provenance notes. The scientific narrative is in the main paper-style sections of the documentation.

## Regenerating documentation tables and figures

The table fragments in `docs/tables/` and figures in `docs/figures/` are derived from committed CSV/JSON/YAML artifacts. Refresh them after profile/radii/QA or comparison CSVs change:

```bash
python scripts/prepare_docs.py --write
```

Check that committed documentation is current:

```bash
python scripts/prepare_docs.py --check
```

This script does not run SCF, extract profiles, calculate radii, or compute QA comparisons.

## Regenerating deterministic QA products

After profile/radii/QA data change, regenerate comparison products and documentation in this order:

```bash
python scripts/check_basis_sensitivity.py --force
python scripts/check_basis_comparisons.py --force
python scripts/check_profile_artifacts.py --require-generated
python scripts/prepare_docs.py --write
```

Full profile regeneration additionally requires local SCF artifacts or new SCF calculations. That is a maintainer workflow, not a documentation-preparation step.

## Citation and reuse guidance

When using the data layer, cite or describe the reference convention rather than treating the profiles as method-independent isolated-atom truth. A compact description is:

```text
Spherical reference proatoms were taken from atomref-proatoms, using the documented state, basis, spherical fractional-occupation SCF, profile, radii, and QA policies. Neutral and cationic states are NIST-derived; accepted monoanions use the Ning--Lu anion-status layer; formal anions are explicitly labeled reference-density rows and are not claimed as stable isolated atomic anions.
```

This wording is guidance for reuse of the data layer. It is not a substitute for describing the basis branch and profile-data version used in a particular analysis.

## Validation command set

The standard lightweight validation command set is:

```bash
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/check_profile_artifacts.py --require-generated
python scripts/check_multiwfn_artifacts.py --require-generated
python scripts/compute_wavefunctions.py --dry-run
python scripts/extract_profiles.py --dry-run
python scripts/check_basis_sensitivity.py --dry-run
python scripts/check_basis_comparisons.py --dry-run
python scripts/export_multiwfn_artifacts.py --dry-run
python scripts/prepare_docs.py --check
python -m pytest -q
```

If development tools are installed, also run:

```bash
ruff check .
mkdocs build --strict
```

When MkDocs dependencies are not installed in the active environment, create a
temporary documentation environment with pip, for example:

```bash
python -m venv .venv-docs
. .venv-docs/bin/activate
python -m pip install -e ".[docs]"
mkdocs build --strict
```

## Local WFN/Multiwfn validation workflow

The notebook `docs/notebooks/multiwfn_wfn_plane_validation.ipynb` is intended to be copied to `local-data/` for execution. A local Multiwfn executable may be placed at `local-data/Multiwfn` or under a `local-data/Multiwfn*/` directory; `local-data/settings.ini` is used when present. The notebook writes only H, O, and H2O validation files under ignored local paths and parses the resulting point and plane outputs.

## Local Multiwfn interoperability export

The configured Multiwfn export policy is stored in `data/profile_datasets.yaml`. The current policy writes `.rad` files for all states in the two primary basis branches, writes `.wfn` files only for neutral atoms in the primary `x2c-QZVPall` branch, and writes no Multiwfn files for the supplemented/augmented branches.

The maintainer export command is local-first:

```bash
python scripts/export_multiwfn_artifacts.py --dry-run
python scripts/export_multiwfn_artifacts.py --format all --force --check
python scripts/check_multiwfn_artifacts.py --require-generated
```

The default output root is `data/multiwfn_artifacts/`. Both `.rad` and `.wfn` outputs are generated from local SCF `scf.chk`, `scf.npz`, and metadata files under `local-data/scf/`. The `.rad` path evaluates the spherical SCF density directly on the fixed Multiwfn `atmrad` grid rather than interpolating the committed profile CSVs; by default it uses a fixed-ray evaluation and exposes an angular-average diagnostic option. The `.wfn` path preserves wavefunction-like Gaussian primitive and spin-orbital information. For release regeneration, `--format all` keeps the manifest synchronized with both product families. The package-side WFN reader/evaluator remains a validation utility, not the recommended public data path.

## Multiwfn interoperability and generator contract

The exporter code, `data/multiwfn_artifacts/` contract, generated `.rad` files, generated neutral `x2c-QZVPall` `.wfn` files, and manifest are committed. The public generator reuses the same state, basis, SCF, `.rad`, `.wfn`, and manifest contracts for local runs. `.wfn` export remains intentionally conservative: it is neutral-only and requires all-electron basis data.
