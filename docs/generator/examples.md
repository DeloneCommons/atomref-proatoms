# Generator examples

Executable examples live in the repository root under `examples/`. Each example
is intentionally small, uses an explicit `output/` workdir, and can be inspected
without running new SCF calculations.

## `examples/01_cli_neutral_rad_wfn_bse/`

Beginner Multiwfn-oriented example. It generates neutral `.rad` and `.wfn` files
for H and B--F using `bse:cc-pVDZ` with X2C disabled.

Run:

```bash
cd examples/01_cli_neutral_rad_wfn_bse
bash run.sh
```

This example is useful for users who mainly want to understand the Multiwfn file
layout:

```text
output/multiwfn/rad/*.rad
output/multiwfn/wfn/*.wfn
output/multiwfn/manifest.json
```

## `examples/02_cli_stockholder_local_basis/`

Advanced CLI example. It uses a local NWChem-format dyall-v2z basis file and
writes profiles/radii/QA, `.rad`, and neutral-only `.wfn` outputs for a small
Ni/Pd stockholder subset.

Run:

```bash
cd examples/02_cli_stockholder_local_basis
bash run.sh
```

This example is useful for users who need the native density tables:

```text
output/profiles/profiles.csv
output/radii/radii.csv
output/qa/qa.csv
```

It also shows the neutral-only `.wfn` policy: anionic and cationic states still
receive native profile rows and `.rad` files, but `.wfn` files are written only
for neutral selected atoms.

## `examples/03_python_custom_state_pipeline/`

Expert notebook for custom state and pipeline design. Use this when you need
state definitions outside the curated CLI state policies.

Notebook:

```text
custom_state_pipeline.ipynb
```

The notebook is intentionally more explicit than a short code snippet. It shows
how to write down the state, count electrons, record the spin multiplicity, check
a basis source, and keep optional SCF output separated from committed release
data.
