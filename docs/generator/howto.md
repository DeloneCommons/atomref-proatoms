# Generator how-to guide

This page shows common local workflows. For complete executable examples, see the
root `examples/` directory.

## 1. Plan first

A dry run is the normal first step:

```bash
atomref-proatoms generate \
  --elements H \
  --element-range B-F \
  --method PBE0 \
  --relativity none \
  --basis bse:cc-pVDZ \
  --state-policy neutral \
  --artifacts rad,wfn \
  --workdir ./proatoms-neutral \
  --dry-run
```

Read `./proatoms-neutral/plan.json`. It should show the selected states, the
basis check, planned SCF directories, and planned Multiwfn paths. Remove
`--dry-run` only after the plan is sensible.

## 2. Generate neutral Multiwfn references

For neutral atoms, `.rad` and `.wfn` can be generated together when the basis is
all-electron or accepted as all-electron by the user:

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

Expected output:

```text
proatoms-neutral/
  manifest.json
  failures.csv
  basis/
  scf/
  multiwfn/
    rad/*.rad
    wfn/*.wfn
```

See `examples/01_cli_neutral_rad_wfn_bse/`.

## 3. Generate stockholder references

Use the stockholder state policy when you need the curated set of ionic and
formal reference densities for stockholder or Hirshfeld-I-like workflows:

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

Expected output:

```text
proatoms-stockholder/
  profiles/profiles.csv
  radii/radii.csv
  qa/qa.csv
  multiwfn/rad/*.rad
  multiwfn/wfn/*.wfn  # neutral selected states only
```

See `examples/02_cli_stockholder_local_basis/`.

## 4. Read the scientific checks

A generated proatom is not just an output file. Check the pieces together:

```text
state        element, charge, configuration, spin multiplicity, l occupations
basis        source, coverage, hash, ECP/full-electron status
method       HF or DFT functional, scalar-relativity setting, PySCF version
SCF          convergence status, energy, log, checkpoint, density matrices
profile      rho(r) on the radial grid
radii        cutoff radii derived from rho(r)
QA           independent electron-count and angular-sphericity checks
```

In `profiles.csv`, `rho_e_bohr3` is the local three-dimensional density
`rho(r)` in electron/bohr^3. The electron count is recovered as:

```text
N = integral 4*pi*r^2*rho(r) dr
```

For ECP/effective-core runs allowed by `--allow-ecp`, the generated profile and
`.rad` files describe the explicit/effective-valence density. The QA electron
count is therefore the explicit electron count recorded in `scf.json`, while the
full state electron count and effective core count are preserved in metadata.

The release validators in `scripts/check_profile_artifacts.py` and
`scripts/check_multiwfn_artifacts.py` check the committed publication layout
under `data/`. Local generator workdirs are runtime products; inspect their
`manifest.json`, `failures.csv`, profile/radius/QA tables, Multiwfn artifacts,
and SCF metadata directly.

## 5. Move to Python scripting

Use scripting when you need custom configurations, custom multiplicities,
state-sensitivity scans, or pipeline integration beyond the curated CLI state
policies. The custom-state notebook keeps the same plain scientific bookkeeping:
charge, electron count, spin multiplicity, configuration, alpha/beta l counts,
basis source, SCF settings, profile grid, and QA.

See `examples/03_python_custom_state_pipeline/custom_state_pipeline.ipynb`.
