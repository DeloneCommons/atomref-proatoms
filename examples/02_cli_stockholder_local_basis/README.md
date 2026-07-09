# Example 02: stockholder references from a local basis file

This advanced CLI example uses a local NWChem-format basis file and generates
all public artifact families for a curated stockholder subset.

The basis file is:

```text
input/dyall-v2z-ni-pd-pt.nw
```

It was downloaded from Basis Set Exchange with the equivalent URL:

```text
http://www.basissetexchange.org/api/basis/dyall-v2z/format/nwchem/?version=1&elements=28,46,78
```

The example command selects Ni and Pd with the charge filter `-1,0,+1`.

Install the generator dependencies once before rerunning the example. From PyPI:

```bash
python -m pip install "atomref-proatoms[generator]"
```

From a source checkout, use the editable equivalent from the repository root:

```bash
python -m pip install -e ".[generator]"
```

Run the example from this directory in a source checkout or full GitHub/Zenodo
release archive:

```bash
./run.sh
```

The script sets `--grid-level 0` to keep the committed example lightweight and
quick to rerun. For production-quality work, choose grid settings appropriate
for your method and validation requirements.

The file name includes Pt because the downloaded basis file also contains Pt.
You can add Pt to `--elements` for your own run, but the committed output keeps
the example lightweight enough to inspect and rerun.

The command uses:

```text
--state-policy stockholder
--artifacts all
--relativity x2c
--basis-file input/dyall-v2z-ni-pd-pt.nw
```

The committed `output/` directory contains:

```text
output/profiles/profiles.csv  # radial electron-density profiles rho(r)
output/radii/radii.csv        # density-cutoff radii derived from profiles
output/qa/qa.csv              # independent QA checks
output/multiwfn/rad/          # .rad files for all selected curated states
output/multiwfn/wfn/          # .wfn files for neutral selected states only
output/scf/                   # local SCF cache
output/manifest.json          # generator manifest
```

## What is ED(r) here?

In the native profile table, `rho_e_bohr3` is the radial electron density
`rho(r)` in electron/bohr^3 sampled on the release radial grid. It is a local
three-dimensional density evaluated at radius `r`, not the radial distribution
`4*pi*r^2*rho(r)`. The integrated electron count is obtained from:

```text
N = integral 4*pi*r^2*rho(r) dr
```

The `radii.csv` file stores cutoff radii where `rho(r)` reaches the project
cutoffs, such as `0.001 e/bohr^3`. The `qa.csv` file records independent
integration and consistency diagnostics.

## Neutral-only WFN policy

`--artifacts all` requests `.wfn`, but the public generator writes `.wfn` only
for neutral states. Ionic and formal stockholder states still receive `.rad`
files and native profile/radii/QA rows. This mirrors the conservative public
WFN policy of atomref-proatoms.
