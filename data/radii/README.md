# Density-cutoff radii

This directory is the target location for density-cutoff radii derived from the
generated spherical radial profile datasets. No final v2 radii tables are
committed in this preparation snapshot.

The old neutral-only v1 radii artifacts were removed from the active tree; v1
remains available from historical tags/releases/archives.

A cutoff radius is the interpolated radial position at which a spherical
free-atom density profile reaches a declared density threshold. These radii
provide compact, reproducible size descriptors associated with the same state,
basis, method, and sphericalization conventions as the corresponding profiles.

## Dataset layout after generation

Generated cutoff-radius result tables live under:

```text
data/radii/<dataset_id>/
  radii.csv
  metadata.json
```

`radii.csv` contains one row per generated state. For each cutoff declared in
`data/profile_datasets.yaml`, radii are reported in bohr and ångström:

```text
r_iso_<cutoff>_e_bohr3_bohr
r_iso_<cutoff>_e_bohr3_angstrom
```

The source profile table and source profile metadata are recorded in
`metadata.json`.

## Cutoff interpretation

The 0.003 and 0.001 electron/bohr³ cutoff radii are the primary practical size
descriptors. The 0.0001 electron/bohr³ cutoff probes the low-density tail and is
mainly useful for tail diagnostics and sensitivity inspection.

Radii are obtained from the tabulated radial profile by interpolation on the
monotone outer-density crossing. QA checks verify that reported radii are finite
when expected and monotonic with respect to the density cutoff.

## Regeneration

Radii are generated artifacts and should not be hand-edited. They are regenerated
alongside profiles and QA tables, then checked for active-dataset consistency, with:

```bash
python scripts/extract_profiles.py --force --check
python scripts/check_profile_artifacts.py --require-generated
```

## Related documentation

- Density-cutoff radius definition: `docs/theory.md`.
- Released artifact contract: `docs/data.md`.
- Regeneration workflow: `docs/workflow.md`.
