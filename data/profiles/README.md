# Generated radial profile datasets

This directory is the target location for released spherical proatomic radial
electron-density profiles. Profiles are generated from the active v2 state table
and the dataset scopes declared in `data/profile_datasets.yaml`.

No final v2 profile tables are committed in this preparation snapshot. The old
neutral-only v1 profile artifacts were removed from the active tree; v1 remains
available from historical tags/releases/archives.

## Active v2 dataset scopes

The active v2 profile configuration declares four dataset scopes:

```text
pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2
  x2c-QZVPall, H-Rn, all curated v2 states

pbe0_sfx2c_dyallv4z_h-lr_spherical_v2
  dyall-v4z, H-Lr, all curated v2 states

pbe0_sfx2c_x2cqzvpalls_h-rn_anions_spherical_v2
  x2c-QZVPall-s, H-Rn, anions only

pbe0_sfx2c_dyallav4z_h-ba_hf-ra_anions_spherical_v2
  dyall-av4z, H-Ba and Hf-Ra within the active H-Lr state range, anions only
```

The two primary datasets are deliberately not split into separate neutral,
cation, and anion products. Charge/state membership is part of the dataset scope
record and generated metadata.

## Dataset layout after generation

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

The radius unit is bohr. Electron density is reported as electrons/bohr³. Column
names are deterministic and are based on curated state IDs.

## Metadata

`metadata.json` records the dataset identity, profile-data version, basis ID and
basis checksum, density model, method settings, radial grid, QA grid, density
cutoffs, column map, per-state metadata, related artifact paths, local SCF
artifact paths, and release provenance.

The local SCF artifacts referenced in metadata are stored under ignored
`local-data/scf/` directories and are not tracked in the release repository. They
are the regeneration source for these profiles.

## Regeneration

Profiles are generated artifacts and should not be hand-edited. After complete
local SCF artifacts have been produced, regenerate them and run the artifact
consistency gate with:

```bash
python scripts/extract_profiles.py --force --check
python scripts/check_profile_artifacts.py --require-generated
```

For inspection without writing files:

```bash
python scripts/extract_profiles.py --list
python scripts/extract_profiles.py --dry-run
```

## Related documentation

- Scientific density model: `docs/theory.md`.
- Released artifact contract: `docs/data.md`.
- Regeneration workflow: `docs/workflow.md`.
