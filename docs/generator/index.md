# Generator tool overview

`atomref-proatoms generate` is the user-facing local generator for
atomref-proatoms-style spherical proatoms. It wraps the existing package-level
SCF, radial-profile, QA, and Multiwfn exporter machinery behind a conservative
CLI.

The generator produces the same kind of objects as the released v2 data layer:

```text
spherical radial electron-density profiles + radii + QA + provenance
```

It can also export Multiwfn-oriented files:

```text
.rad  density-only atomic radial-density files
.wfn  neutral-only PROAIM wavefunction-like files, where supported
```

The `.rad` and `.wfn` files are interoperability products. They do not replace
the native profile/radii/QA data contract.

## What the generator does

The public CLI can:

- select elements explicitly or by element range;
- use curated `neutral` or `stockholder` state policies;
- run PySCF DFT calculations, or HF when the corresponding backend is available;
- use PySCF basis names, Basis Set Exchange names, or local NWChem-format basis files;
- use either scalar X2C or non-relativistic calculations;
- write local SCF artifacts, profiles, radii, QA, `.rad`, and neutral-only `.wfn` files;
- write manifests and resolved run configurations for reproducibility.

## What the generator intentionally does not do

The CLI is not a general atomic-state laboratory. It does not accept custom
configuration strings, custom multiplicities, state scans, or method-energy
state selection. These are expert workflows and should be handled with Python
scripts or notebooks using package APIs.

The state policies are curated reference policies:

```text
neutral      curated q = 0 states only
stockholder  curated stockholder/Hirshfeld-I-like state set
```

For q < -1, atomref-proatoms provides formal radial-density references for
stockholder/Hirshfeld-I-like workflows. These entries are not claimed to be
stable isolated atomic anions or experimental atomic ground states.

## Installation model

The package is designed so that `import atomref_proatoms` does not require
PySCF. Actual generation requires the optional generator dependencies. BSE basis
resolution requires `basis-set-exchange`.

The PyPI package carries service resources needed for the generator, not the full
released data archive. Full generated profiles/radii/QA and committed Multiwfn
artifacts belong to the repository release and Zenodo/GitHub data products.

The repository includes an installed-wheel smoke test for release checks:

```bash
python scripts/smoke_installed_wheel.py
```

This builds the wheel, installs it into a fresh environment, and verifies that
`atomref-proatoms --help`, `--version`, and `generate --dry-run` work outside a
source checkout.

## Examples

Reproducible examples live in the repository root under [`examples/`](https://github.com/DeloneCommons/atomref-proatoms/tree/main/examples/):

- `examples/01_cli_neutral_rad_wfn_bse/`
- `examples/02_cli_stockholder_local_basis/`
- `examples/03_python_custom_state_pipeline/`
