# Data layout and artifact contract

The repository separates compact tracked inputs, tracked release artifacts, and
ignored local generator artifacts. This split is part of the data contract: a
user can inspect and load released profile/radius/QA tables without possessing the
SCF checkpoints used to regenerate them.

## Top-level data contract

```text
data/profile_datasets.yaml
  Active v1 dataset specification. It declares the profile-data version, method
  defaults, radial grids, QA grids, density cutoffs, basis IDs, element coverage,
  and neutral-only v1 selection rules.

data/states/
  Compact source, selection, and curated atomic-state records. The generator uses
  the curated JSON table. Active v1 profile datasets select neutral states from
  this layer through `data/profile_datasets.yaml`.

data/basis_sets/
  Frozen NWChem-format spherical basis-set exports, bundle manifests, checksums,
  and reference notes. These files define the basis-data identity used by the
  generator.

data/profiles/<dataset_id>/
  Generated radial electron-density profiles. Each dataset directory contains
  `profiles.csv` and `metadata.json`.

data/radii/<dataset_id>/
  Generated density-cutoff radii derived from the corresponding profile table.
  Each dataset directory contains `radii.csv` and `metadata.json`.

data/qa/<dataset_id>/
  Generated per-state QA rows for the corresponding profile dataset. Aggregate QA
  files are stored directly under `data/qa/`.

docs/notebooks/proatomic_profiles_v1.ipynb
  User-facing narrative report. It reads generated release artifacts from `data/`
  and does not run SCF calculations.

local-data/scf/<dataset_id>/<state_id>/
  Ignored local SCF artifacts. These directories contain checkpoints, reusable
  arrays, metadata, and logs used to regenerate profile/radius/QA tables.
```

## Active v1 datasets

| dataset_id | basis_id | coverage | selected states |
|---|---|---:|---:|
| `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v1` | `x2c-QZVPall` | H-Rn | neutral recommended states |
| `pbe0_sfx2c_dyallv4z_h-lr_spherical_v1` | `dyall-v4z` | H-Lr | neutral recommended states |

The dataset ID is a stable part of the public data product. It encodes method,
basis family, coverage, spherical density convention, and major data version in a
compact name. The full machine-readable specification remains
`data/profile_datasets.yaml` and each dataset's `metadata.json`.

## Generated profile tables

`data/profiles/<dataset_id>/profiles.csv` is a wide table:

```text
r_bohr
rho_e_bohr3__<state_id>
rho_e_bohr3__<state_id>
...
```

Each density column is the spherical total electron density for one selected
state. The matching `metadata.json` records units, method metadata, basis SHA256,
profile grid, QA grid, cutoffs, state list, related artifact paths, and generator
provenance.

Generated profile tables should not be manually edited. Changes to state
selection, basis identity, method settings, grid settings, or version fields
should be made in the corresponding source/configuration layer and then
regenerated.

## Generated radii tables

`data/radii/<dataset_id>/radii.csv` stores one row per selected state. It includes
state identifiers and cutoff radii in both bohr and ångström:

```text
r_iso_0.003_e_bohr3_bohr
r_iso_0.001_e_bohr3_bohr
r_iso_0.0001_e_bohr3_bohr
r_iso_0.003_e_bohr3_angstrom
r_iso_0.001_e_bohr3_angstrom
r_iso_0.0001_e_bohr3_angstrom
```

Radii are generated from the profile table by interpolation at the declared
density cutoffs. They are first-class release data because many downstream
models need compact atom-size descriptors rather than full radial profiles.

## Generated QA tables

`data/qa/<dataset_id>/qa.csv` stores one row per selected state. The aggregate
files are:

```text
data/qa/qa_summary.csv
  One summary row per generated dataset.

data/qa/qa_report.md
  Compact human-readable release-gate report.
```

QA outputs are generated artifacts and should be refreshed together with profile
and radii outputs.

## Local SCF artifacts

The generator writes expensive local material to:

```text
local-data/scf/<dataset_id>/<state_id>/
  scf.chk
  scf.npz
  scf.json
  scf.log
```

`local-data/` is intentionally ignored by Git. The public release does not depend
on users having the same checkpoint files, but the checkpoint layer is needed to
recreate the tracked generated tables without rerunning every SCF calculation.

## Standard regeneration sequence

From the repository root, the intended v1 data workflow is:

```bash
python scripts/build_atom_states.py --check
python scripts/check_basis_bundles.py
python scripts/compute_wavefunctions.py --resume --quiet-scf-log
python scripts/extract_profiles.py --force --check
```

For inspection-only runs that do not require PySCF:

```bash
python scripts/compute_wavefunctions.py --list
python scripts/extract_profiles.py --list
```
