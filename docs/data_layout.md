# Data layout

The active branch carries one current profile-data version. Historical versions are
preserved by Git tags, GitHub releases, and Zenodo records rather than by keeping multiple
parallel workflow layouts in the repository.

```text
data/profile_datasets.yaml
  Active v1 dataset specification: method defaults, grids, cutoff radii, dataset IDs,
  basis IDs, charge-scope rules, and element coverage.

data/states/
  Source / selection / curated atomic-state records. The generator reads the curated JSON.

data/basis_sets/
  Frozen Basis Set Exchange NWChem spherical basis exports and their manifests. Default
  checks are offline and validate stored identity/provenance.

data/profiles/<dataset_id>/
  Final generated radial-density release data. The v1 layout is one `profiles.csv` plus
  one `metadata.json` per dataset.

local-data/scf/<dataset_id>/<state_id>/
  Ignored local SCF artifacts: `scf.chk`, `scf.npz`, `scf.json`, and `scf.log`.

report/
  Current generated scientific report and derived report tables/figures.
```

`local-data/` is intentionally ignored. It contains expensive/reusable SCF material and
scratch diagnostics, while `data/profiles/` contains compact release artifacts.
