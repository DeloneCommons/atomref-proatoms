# Generator how-to guide

This page describes common workflows. For complete executable examples, see the
root [`examples/`](https://github.com/DeloneCommons/atomref-proatoms/tree/main/examples/) directory.

## Generate neutral Multiwfn references

Use neutral state policy and request `.rad` and `.wfn`:

```bash
atomref-proatoms generate \
  --elements H \
  --element-range B-F \
  --method PBE0 \
  --relativity none \
  --basis bse:cc-pVDZ \
  --state-policy neutral \
  --artifacts rad,wfn \
  --workdir ./proatoms-neutral
```

This produces density-only `.rad` files and neutral `.wfn` files for all selected
neutral states.

See:

```text
examples/01_cli_neutral_rad_wfn_bse/
```

## Generate stockholder references

Use stockholder state policy when you need the curated set of ionic/formal
reference densities for stockholder or Hirshfeld-I-like workflows:

```bash
atomref-proatoms generate \
  --elements Ni,Pd \
  --charges=-1,0,+1 \
  --method PBE0 \
  --relativity x2c \
  --basis-file input/dyall-v2z-ni-pd-pt.nw \
  --basis-name dyall-v2z-ni-pd-pt \
  --state-policy stockholder \
  --artifacts all \
  --workdir ./proatoms-stockholder \
  --allow-unverified-basis
```

This writes native profiles/radii/QA, `.rad` files for all selected states, and
`.wfn` files for neutral states only.

See:

```text
examples/02_cli_stockholder_local_basis/
```

## Understand profiles, radii, and QA

The native `profiles.csv` stores `rho_e_bohr3`, the local three-dimensional
electron density `rho(r)` in electron/bohr^3 on the radial grid. It is not the
radial distribution `4*pi*r^2*rho(r)`.

The electron count is recovered as:

```text
N = integral 4*pi*r^2*rho(r) dr
```

`radii.csv` stores density-cutoff radii derived from `rho(r)`. `qa.csv` stores
independent checks such as electron-count integration and angular sphericity.

## Use a local basis file

Use `--basis-file` for a NWChem-format basis file. Always provide a stable
`--basis-name` if the file name is not already a clear basis identifier.

```bash
--basis-file input/my_basis.nw --basis-name my-local-basis
```

Local files may have unknown full-electron status. The generator records the
check result in `<workdir>/basis/basis_check.json`.

## Move to Python scripting

Use scripting when you need custom configurations, custom multiplicities,
state-sensitivity scans, or pipeline integration beyond the curated CLI state
policies.

See:

```text
examples/03_python_custom_state_pipeline/custom_state_pipeline.ipynb
```
