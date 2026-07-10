# atomref-proatoms examples

This directory contains small, reproducible workflows for the public
`atomref-proatoms generate` tool and for expert Python use of the package APIs.

The examples are intentionally split by user level:

| example | audience | purpose |
|---|---|---|
| `01_cli_neutral_rad_wfn_bse/` | new users / Multiwfn users | Generate neutral `.rad` and neutral `.wfn` references for H and B--F from a BSE basis with X2C disabled. |
| `02_cli_stockholder_local_basis/` | advanced CLI users | Generate stockholder-style profiles/radii/QA, `.rad`, and neutral-only `.wfn` files for Ni/Pd using a local NWChem basis file. |
| `03_python_custom_state_pipeline/` | expert users | Notebook-style guide for custom states, explicit configurations, profile/radius export, and pipeline organization. |

The CLI examples include committed output directories produced by the corresponding
`run.sh` scripts. The examples themselves live in the source tree or full
GitHub/Zenodo release archive; PyPI installs the CLI and package resources, not
these example folders. Re-running an example requires the optional generator
dependencies. From PyPI, install the generator tool with:

```bash
python -m pip install "atomref-proatoms[generator]"
```

From a source checkout, use the editable equivalent from the repository root:

```bash
python -m pip install -e ".[generator]"
```

The generator extra includes PySCF and Basis Set Exchange, so it is enough for
both PySCF basis names and `bse:` basis sources.

To avoid BLAS/OpenMP oversubscription on workstations, the example scripts set
`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, and `OPENBLAS_NUM_THREADS` to `1` unless
those variables are already set.
