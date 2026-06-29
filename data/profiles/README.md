# Generated radial profile datasets

This directory contains the released atomref-proatoms radial electron-density profile
artifacts for the active repository version.

Each dataset is written as one wide CSV plus one aggregate metadata JSON:

```text
data/profiles/<dataset_id>/
  profiles.csv
  metadata.json
```

`profiles.csv` uses a shared `r_bohr` column and one density column per atomic state:

```text
rho_e_bohr3__<state_id>
```

`metadata.json` records the dataset scope, basis identity, method/provenance fields,
state metadata, and references to the local SCF artifacts that were used to generate
the released profiles. Cutoff radii and QA summaries are published separately under
`data/radii/` and `data/qa/`. Local SCF checkpoints and
NPZ array bundles remain under ignored `local-data/scf/` and are not tracked here.
