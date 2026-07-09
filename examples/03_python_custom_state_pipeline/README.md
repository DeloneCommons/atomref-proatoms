# Example 03: expert Python custom-state pipeline

This folder contains an expert notebook for workflows that are intentionally out
of scope for the public CLI:

```text
custom_state_pipeline.ipynb
```

Use this route when you need explicit configurations, custom multiplicities,
state scans, or project-specific pipeline integration. The CLI uses only the
curated `neutral` and `stockholder` state policies.

The notebook is executable as written. The actual SCF calculation cell is guarded
by `RUN_OPTIONAL_CUSTOM_SCF = False` so the notebook can be executed during docs
work without PySCF or expensive quantum-chemistry work. Set it to `True` locally
to run a tiny neutral-H custom-state smoke calculation and write profile, radii,
`.rad`, and `.wfn` outputs under `output/notebook_h/`.

For the optional SCF cell, install the generator dependencies from the repository root:

```bash
python -m pip install -e ".[generator]"
```
