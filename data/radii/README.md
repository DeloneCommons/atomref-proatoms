# Density-cutoff radii

This directory stores density-cutoff radii derived from the generated spherical
radial profile datasets. It is a data contract page: it describes table layout,
column names, numerical interpolation, and regeneration. For the conceptual
meaning of cutoff radii, see `docs/theory.md`; for the current interpretation,
see `docs/results.md` and `docs/discussion.md`.

A cutoff radius is the outer radial position where the spherical free-atom
density reaches a declared density threshold,
\(\rho(r)=\rho_\mathrm{cut}\). The radii are not empirical van der Waals or
covalent radii. They are reproducible isodensity radii of the computed
all-electron spherical reference density.

## Dataset layout

Generated cutoff-radius result tables live under:

```text
data/radii/<dataset_id>/
  radii.csv
  metadata.json
```

Current row counts are:

| dataset ID | rows |
|---|---:|
| `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2` | 430 |
| `pbe0_sfx2c_dyallv4z_h-lr_spherical_v2` | 501 |
| `pbe0_sfx2c_x2cqzvpalls_h-rn_spherical_v2` | 192 |
| `pbe0_sfx2c_dyallav4z_h-ba_hf-ra_spherical_v2` | 166 |

`radii.csv` contains one row per generated state. For each cutoff declared in
`data/profile_datasets.yaml`, radii are reported in bohr and ångström:

```text
r_iso_<cutoff>_e_bohr3_bohr
r_iso_<cutoff>_e_bohr3_angstrom
```

The source profile table and source profile metadata are recorded in
`metadata.json`.

## Numerical definition

The radius is computed from the tabulated radial profile by locating the outermost
crossing from `rho >= cutoff` to `rho <= cutoff`. When the neighboring density
values are positive, the interpolation is linear in `log(rho)`, which is more
stable for approximately exponential atomic tails than direct linear density
interpolation. QA checks require finite radii and monotonic ordering with respect
to the density cutoff.

The current density cutoffs are:

| cutoff (e/bohr³) | primary interpretation |
|---:|---|
| 0.003 | compact valence/outer-size descriptor |
| 0.001 | lower-density valence/tail descriptor |
| 0.0001 | far-tail sensitivity and interpolation diagnostic |

The 0.003 and 0.001 electron/bohr³ radii are the most chemically robust practical
size descriptors. The 0.0001 electron/bohr³ cutoff is intentionally retained
because formal and weakly bound anions can differ mainly in the far tail.

## Basis-comparison use

Cutoff radii are often more interpretable than integrated quantile radii for
quick basis comparisons, because they answer a direct isodensity question. The
Results and `data/qa/basis_comparisons/` use them to compare
the primary `x2c-QZVPall` and `dyall-v4z` branches. The
`data/qa/basis_sensitivity/` layer uses them to summarize supplemented/augmented
neutral-plus-anion sensitivity.

## Regeneration

Radii are generated artifacts and should not be hand-edited. They are regenerated
alongside profiles and QA tables, then checked for active-dataset consistency, with:

```bash
python scripts/extract_profiles.py --force --check
python scripts/check_basis_sensitivity.py --force
python scripts/check_basis_comparisons.py --force
python scripts/check_profile_artifacts.py --require-generated
```

## Related documentation

- Density-cutoff radius definition: `docs/theory.md`.
- Results: `docs/results.md`.
- Released artifact contract: `docs/data.md`.
- Regeneration workflow: `docs/workflow.md`.
