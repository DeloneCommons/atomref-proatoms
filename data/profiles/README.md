# Generated radial profile datasets

This directory contains the released spherical proatomic radial electron-density
profiles for the active `atomref-proatoms` data version. A profile is a tabulated
free-atom electron density, `rho(r)`, evaluated on the common radial grid defined
in `data/profile_datasets.yaml` and stored with explicit state, basis, method,
and QA provenance.

The profiles are intended as stable reference data for atom-centered
computational chemistry workflows. Typical downstream uses include empirical
atomic density/radius models, crystallographic descriptors, promolecular-density
approximations, deformation-density baselines, and lightweight packages that need
precomputed consistent atomic reference densities rather than a local quantum-
chemistry generator.

## Dataset layout

Each generated dataset is written as one wide CSV plus one aggregate metadata
JSON:

```text
data/profiles/<dataset_id>/
  profiles.csv
  metadata.json
```

`profiles.csv` uses one shared radius column and one density column per selected
atomic state:

```text
r_bohr,rho_e_bohr3__<state_id>,rho_e_bohr3__<state_id>,...
```

The radius unit is bohr. Electron density is reported as electrons/bohr³.
Column names are deterministic and are based on curated state IDs.

## Metadata

`metadata.json` records the dataset identity, profile-data version, basis ID and
basis checksum, density model, method settings, radial grid, QA grid, density
cutoffs, column map, per-state metadata, related artifact paths, local SCF
artifact paths, and release provenance.

The local SCF artifacts referenced in metadata are stored under ignored
`local-data/scf/` directories and are not tracked in the release repository. They
are the regeneration source for these profiles.

## Active v1 datasets

The active v1 datasets are declared in `data/profile_datasets.yaml`:

```text
pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v1
pbe0_sfx2c_dyallv4z_h-lr_spherical_v1
```

Both select neutral atomic states. Generated cutoff radii and QA summaries are
published separately under `data/radii/` and `data/qa/`.

## Regeneration

Profiles are generated artifacts and should not be hand-edited. Regenerate them
from complete local SCF artifacts with:

```bash
python scripts/extract_profiles.py --force --check
```

For inspection without writing files:

```bash
python scripts/extract_profiles.py --list
python scripts/extract_profiles.py --dry-run
```
