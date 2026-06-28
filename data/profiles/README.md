# Profile datasets

This directory is reserved for generated v1 radial proatomic electron-density profiles.
Each dataset will be stored as one wide CSV plus one aggregate metadata JSON:

```text
data/profiles/<dataset_id>/
  profiles.csv
  metadata.json
```

`profiles.csv` will contain a shared `r_bohr` column and one density column per state,
using column names of the form `rho_e_bohr3__<state_id>`. `metadata.json` will contain
method, basis, state, QA, derived-radius, column, and provenance metadata for the dataset.

SCF checkpoints, logs, density matrices, and restart material are local artifacts and belong
under ignored `local-data/scf/`, not in this directory.
