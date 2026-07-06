# atomref-proatoms: spherical reference proatoms

## Abstract

`atomref-proatoms` is a reproducible data layer for spherical atomic and ionic reference densities. The current release provides self-consistent spherical PBE0/sf-X2C radial electron densities for neutral atoms, cations, curated monoanions, and explicitly formal anion references under a fixed state, basis, SCF, profile-extraction, radii, and validation policy. The profiles are intended as documented proatomic reference gauges for stockholder, Hirshfeld-like, promolecular, deformation-density, descriptor, and related real-space workflows. They are not claimed to be universal isolated-atom ground states for every approximate Hamiltonian, basis set, or molecular environment.

The current data layer contains 1289 generated dataset-state rows across four basis branches. The primary branches are `x2c-QZVPall` for H--Rn and `dyall-v4z` for H--Lr. The supplemented/augmented branches, `x2c-QZVPall-s` and `dyall-av4z`, contain neutral and anion rows used to quantify branch and tail sensitivity; cations are deliberately not duplicated in these branches. All committed rows pass the current validation criteria.

## How to read these docs

The main documentation is organized as a paper-like technical note. The core argument is in the Introduction, Theory, Methods, Results, Discussion, and Conclusions. Data dictionaries, script details, notebooks, license material, and repository-operation notes are kept in the Other and Reference sections so that the scientific narrative remains readable.

The Results page includes generated tables and figures produced from committed CSV/JSON artifacts by:

```bash
python scripts/prepare_docs.py --write
```

The visible Markdown remains the source of the scientific prose. The script only refreshes marked table and figure blocks plus reusable fragments under `docs/tables/` and `docs/figures/`.

## Data entry points

The main generated files are:

```text
data/profiles/<dataset_id>/profiles.csv
data/radii/<dataset_id>/radii.csv
data/qa/<dataset_id>/qa.csv
data/qa/basis_sensitivity/
data/qa/basis_comparisons/
```

The state and generation contracts are:

```text
data/states/curated/atom_states_v2.json
data/states/selection/required_states_v2.csv
data/profile_datasets.yaml
```

The expensive SCF checkpoints and logs are local regeneration material under ignored `local-data/scf/` paths and are not part of the committed data layer.

## Minimal validation

For users who only inspect the committed data layer, the lightweight validation path is:

```bash
python scripts/check_states.py
python scripts/check_basis_bundles.py
python scripts/check_profile_artifacts.py --require-generated
python scripts/check_basis_sensitivity.py --dry-run
python scripts/check_basis_comparisons.py --dry-run
python scripts/prepare_docs.py --check
pytest
```

Full SCF regeneration is a maintainer workflow requiring generator dependencies and local compute resources; it is not needed to consume the committed profile, radii, and QA tables.
