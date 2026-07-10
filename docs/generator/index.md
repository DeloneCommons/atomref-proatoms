# Generator tool overview

`atomref-proatoms generate` is the local generator for small, reproducible
atomref-proatoms-style runs. It uses the same basic contract as the released v2
data layer: curated state records, explicit basis provenance, spherical
fractional-occupation self-consistent-field (SCF) calculations, radial density
profiles, cutoff radii, quality-assurance (QA) summaries, and optional Multiwfn
interoperability files.

The safest default remains to use the released data products. Run the generator
when you need a small local subset, a different basis/method convention, or a
controlled custom workflow that should still leave a clear provenance trail.

## Before you begin

You need Python 3.10 or newer and a terminal. Multiwfn is not required to
generate `.rad` or `.wfn` files; those are output formats. Actual generation
uses PySCF and can take appreciably longer than a dry run, so begin with one or a
few elements.

In a new virtual environment, install the generator from PyPI and check the
command:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install "atomref-proatoms[generator]"
atomref-proatoms --version
```

From a source checkout, replace the install command with this command from the
repository root:

```bash
python -m pip install -e ".[generator]"
```

The generator extra includes PySCF and Basis Set Exchange. A base-only install
is sufficient for lightweight imports and planning, but it cannot execute SCF.

## First dry run

This command plans one neutral-carbon run and writes planning JSON under
`./proatoms-carbon/`; it does not run SCF:

```bash
atomref-proatoms generate \
  --elements C \
  --method PBE0 \
  --relativity none \
  --basis bse:cc-pVDZ \
  --state-policy neutral \
  --artifacts profiles,rad \
  --workdir ./proatoms-carbon \
  --dry-run
```

Open `proatoms-carbon/plan.json` and check the selected state, method, basis, and
output paths. Remove `--dry-run` only when those choices are intentional. The
[how-to guide](howto.md) continues from this point.

## Terms used in the manual

| Term | Meaning here |
|---|---|
| proatom | An atomic or ionic density used as a reference in a downstream analysis |
| state | A documented element, charge, spin multiplicity, and electronic configuration |
| basis | The Gaussian basis functions used to represent the atomic calculation |
| SCF | The iterative electronic-structure calculation that produces the density |
| state policy | A rule selecting curated neutral or stockholder-oriented states |
| artifact | Any generated profile, radius, QA, `.rad`, `.wfn`, or SCF file |
| workdir | The output directory that keeps one method/basis/state-policy context together |

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

## Examples

Reproducible examples live under `examples/`:

- `01_cli_neutral_rad_wfn_bse/`: neutral `.rad` and `.wfn` output from a BSE
  basis;
- `02_cli_stockholder_local_basis/`: stockholder profiles/radii/QA and Multiwfn
  output from a local NWChem basis file;
- `03_python_custom_state_pipeline/`: custom-state notebook for expert workflows
  outside the curated CLI policies.

These directories are included in the source repository and full release
archive, not in the PyPI wheel. The [examples page](examples.md) explains what
each run demonstrates. Installed-wheel and release smoke tests are documented in
the [maintainer workflow](../workflow.md#release-readiness-checklist).
