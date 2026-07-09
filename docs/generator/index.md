# Generator tool overview

`atomref-proatoms generate` is the local generator for small, reproducible
atomref-proatoms-style runs. It uses the same basic contract as the released v2
data layer: curated state records, explicit basis provenance, spherical
fractional-occupation SCF, radial density profiles, cutoff radii, QA summaries,
and optional Multiwfn interoperability files.

The safest default remains to use the released data products. Run the generator
when you need a small local subset, a different basis/method convention, or a
controlled custom workflow that should still leave a clear provenance trail.

## Output families

The native output is the profile/radii/QA set:

```text
profiles/profiles.csv  radial electron density rho(r)
radii/radii.csv        density-cutoff radii derived from rho(r)
qa/qa.csv              independent integration and sphericity checks
```

The generator can also write Multiwfn-oriented files:

```text
multiwfn/rad/*.rad     density-only atomic radial-density files
multiwfn/wfn/*.wfn     neutral-only PROAIM files, all-electron basis only
```

The `.rad` and `.wfn` files are interoperability products. They do not replace
the native profile/radii/QA data contract.

## Which path should I use?

Use the committed data when you need the published atomref-proatoms v2 reference
set. Use `generate --dry-run` when you want to inspect a planned run without SCF.
Use actual generation only when the plan is small enough to review and the method,
basis, state policy, and output folder are all intentional.

For Multiwfn work, request `.rad` when you need density-only atom references.
Request `.wfn` only for neutral atoms with all-electron basis data. If an ECP is
used with `--allow-ecp`, generated profiles and `.rad` files represent the
explicit/effective-valence density; `.wfn` export is rejected because the PROAIM
file would not contain a full all-electron atom.

## Public state policies

The CLI deliberately exposes only curated state policies:

```text
neutral      curated q = 0 states only
stockholder  curated stockholder/Hirshfeld-I-like state set
```

For charges below -1, atomref-proatoms provides formal radial-density references
for stockholder/Hirshfeld-I-like workflows. These entries are not claims of
stable isolated atomic anions or experimental atomic ground states.

Custom configurations, custom multiplicities, and state scans belong in Python
scripts or notebooks, where the state definition can be reviewed directly.

## Installation model

The base package is importable without PySCF. Generation requires the optional
generator dependencies. For the published PyPI tool, use:

```bash
python -m pip install atomref-proatoms
python -m pip install "atomref-proatoms[generator]"
```

For a source checkout, use the editable equivalent from the repository root:

```bash
python -m pip install -e ".[generator]"
```

The generator extra installs PySCF and Basis Set Exchange. The wheel carries the
code, CLI, schemas, state table, presets, and small service resources needed for
planning and local generation. The full generated profile/radii/QA tables and
committed Multiwfn artifacts are repository and GitHub/Zenodo release data
products.

## Installed-wheel smoke test

The repository includes a release smoke test:

```bash
python scripts/smoke_installed_wheel.py
```

It builds the wheel, installs it into a fresh environment, moves outside the
source checkout, and verifies import, `--help`, `--version`, and
`generate --dry-run`. The optional `--with-generator-execution` mode also runs a
tiny neutral-H generation smoke test and is intentionally heavier because it
executes SCF.

## Examples

Reproducible examples live under `examples/`:

- `01_cli_neutral_rad_wfn_bse/`: neutral `.rad` and `.wfn` output from a BSE basis;
- `02_cli_stockholder_local_basis/`: stockholder profiles/radii/QA and Multiwfn output from a local NWChem basis file;
- `03_python_custom_state_pipeline/`: custom-state notebook for expert workflows outside the curated CLI policies.
