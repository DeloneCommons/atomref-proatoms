# Generated radial profile datasets

This directory stores the released spherical proatomic radial electron-density
profiles. These files are the primary scientific data product of the repository:
for each selected atom or ion, the table gives the spin-summed spherical density
\(\rho(r)\) generated from the declared state, basis, relativistic convention,
and self-consistent spherical fractional-occupation UKS model.

The profile tables are not hand-fitted atomic radii and not post-SCF angular
averages of ordinary open-shell atoms. The underlying SCF density is constrained
to be spherical through angular-momentum-resolved fractional occupations; the
stored profile is the radial representation of that self-consistent spherical
reference density.

## Dataset scopes

The current profile configuration declares four dataset scopes:

```text
pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2
  x2c-QZVPall, H-Rn, all curated states, 430 density columns

pbe0_sfx2c_dyallv4z_h-lr_spherical_v2
  dyall-v4z, H-Lr, all curated states, 501 density columns

pbe0_sfx2c_x2cqzvpalls_h-rn_spherical_v2
  x2c-QZVPall-s, H-Rn, neutrals and anions, 192 density columns

pbe0_sfx2c_dyallav4z_h-ba_hf-ra_spherical_v2
  dyall-av4z, H-Ba/Hf-Ra neutrals plus selected H-Ba/Hf-At anions,
  164 density columns
```

The primary datasets are deliberately not split into separate neutral, cation,
and anion products. The supplemented/augmented branches follow the same design
for the states they support: neutral and anion rows are grouped under one basis
identity, while cations are excluded from these tail-sensitivity branches.
Charge/state membership is part of the dataset scope record and generated
metadata.

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

The radius unit is bohr. Electron density is reported as electrons/bohr³. Column
names are deterministic and are based on curated state IDs. The stored radial grid
has 1200 logarithmic rows from `1e-6` to `60` bohr for every generated dataset.

This grid is the release representation. Independent QA integration uses a
separate Gauss-Legendre grid in log-radius, so a profile can pass only if it is
consistent under a second numerical integration scheme.

## Metadata

`metadata.json` records the dataset identity, profile-data version, basis ID and
basis checksum, density model, method settings, radial grid, QA grid, density
cutoffs, column map, per-state metadata, related artifact paths, local SCF
artifact paths, and release provenance.

The local SCF artifacts referenced in metadata are stored under ignored
`local-data/scf/` directories and are not tracked in the release repository. They
are the regeneration source for these profiles.

## Interpretation

Use a profile column only together with its dataset metadata. A row such as a
formal multianion profile is a formal spherical reference density for
stockholder-like workflows, not an experimental isolated-ion claim. A density in
a supplemented or augmented branch should be cited with that branch's `basis_id`
in any downstream analysis.

For the current scientific QA and basis-sensitivity summary, see
`docs/data_layer_report.md` and `data/qa/README.md`.

## Regeneration

Profiles are generated artifacts and should not be hand-edited. After complete
local SCF artifacts have been produced, regenerate them and run the artifact
consistency gate with:

```bash
python scripts/extract_profiles.py --force --check
python scripts/check_basis_sensitivity.py --force
python scripts/check_profile_artifacts.py --require-generated
```

For inspection without writing files:

```bash
python scripts/extract_profiles.py --list
python scripts/extract_profiles.py --dry-run
```

## Related documentation

- Scientific density model: `docs/theory.md`.
- Scientific data-layer report: `docs/data_layer_report.md`.
- Released artifact contract: `docs/data.md`.
- Regeneration workflow: `docs/workflow.md`.
