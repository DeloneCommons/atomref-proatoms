# Generator examples

Executable examples live in the repository root under `examples/`.

## `examples/01_cli_neutral_rad_wfn_bse/`

Beginner Multiwfn-oriented example. It generates neutral `.rad` and `.wfn` files
for H and B--F using `bse:cc-pVDZ` with X2C disabled.

Main command:

```bash
./run.sh
```

## `examples/02_cli_stockholder_local_basis/`

Advanced CLI example. It uses a local NWChem-format dyall-v2z basis file and
writes profiles/radii/QA, `.rad`, and neutral-only `.wfn` outputs for a curated
stockholder subset.

Main command:

```bash
./run.sh
```

## `examples/03_python_custom_state_pipeline/`

Expert notebook for custom state and pipeline design. Use this when you need
state definitions outside the curated CLI state policies.

Notebook:

```text
custom_state_pipeline.ipynb
```
