# CLI reference

The public command is:

```bash
atomref-proatoms generate [options]
```

Use installed help as the exact source for current flags:

```bash
atomref-proatoms generate --help
```

This page explains the main choices behind those flags.

## Basic dry run

Start with a dry run. It checks the state selection, method, basis source, output
context, and artifact policy without running SCF:

```bash
atomref-proatoms generate \
  --elements C,N,O \
  --method PBE0 \
  --relativity x2c \
  --basis bse:x2c-QZVPall \
  --state-policy neutral \
  --artifacts profiles,rad \
  --workdir ./proatoms \
  --dry-run
```

Dry run writes:

```text
atomref_proatoms_workspace.json
run_config.input.json
run_config.resolved.json
plan.json
```

Inspect `plan.json` before removing `--dry-run`.

## Element selection

Use a comma-separated element list:

```bash
--elements C,N,O
```

Use a closed element range:

```bash
--element-range B-F
```

Both can be combined:

```bash
--elements H --element-range B-F
```

## State policies and charges

```text
--state-policy neutral
```

selects only curated neutral states.

```text
--state-policy stockholder
```

selects the curated stockholder/Hirshfeld-I-like state set for the requested
elements. For stockholder runs, filter charges explicitly when possible:

```bash
--charges=-1,0,+1
```

The `=` form is recommended because values beginning with `-` can otherwise be
parsed as options by the shell or argument parser.

The CLI does not accept custom configurations or multiplicities. Use Python
scripting for those workflows.

## Method and relativity

HF and DFT are both public method paths:

```bash
--method hf
--method PBE0
--method B3LYP
--method "wB97X-D"
```

HF uses the spherical fractional-occupation UHF backend. DFT uses the spherical
fractional-occupation UKS backend and passes the exchange-correlation string to
PySCF. The generator does not maintain its own dictionary of valid DFT names;
the installed PySCF/libxc stack is the source of truth.

Relativity is selected with:

```bash
--relativity x2c
--relativity none
```

`x2c` records the spin-free one-electron X2C convention.

## Basis sources

PySCF basis name:

```bash
--basis def2-SVP
--basis pyscf:def2-SVP
```

Basis Set Exchange basis name:

```bash
--basis bse:cc-pVDZ
```

Local NWChem-format file:

```bash
--basis-file input/my_basis.nw --basis-name my-basis
```

The generator saves basis provenance and checks under:

```text
<workdir>/basis/
```

Detected ECP/effective-core basis data fail by default. Use `--allow-ecp` only
when an explicit-valence density is intended. With that flag, BSE and local
NWChem basis sources may carry ECP sections into execution. `.wfn` export still
requires all-electron basis data and is rejected for ECP sources.

Local basis files may have unknown full-electron status. For `.wfn` planning,
use `--allow-unverified-basis` only when you have inspected the file and accept
that responsibility.

## Artifacts

```text
profiles  native profiles + radii + QA
rad       Multiwfn density-only .rad files
wfn       neutral-only PROAIM .wfn files, all-electron basis only
all       profiles + rad + neutral-only wfn where allowed
```

Default:

```bash
--artifacts profiles,rad
```

SCF artifacts are always written during execution and are used for resume and
export:

```text
<workdir>/scf/<run_id>/<state_id>/scf.chk
<workdir>/scf/<run_id>/<state_id>/scf.npz
<workdir>/scf/<run_id>/<state_id>/scf.json
<workdir>/scf/<run_id>/<state_id>/scf.log
```

## Workdir behavior

One workdir corresponds to one method, relativity, basis, and state-policy
context. If an existing workdir was initialized with a different context, the
command stops and asks you to choose another directory.

Important root files are:

```text
atomref_proatoms_workspace.json
run_config.input.json
run_config.resolved.json
plan.json
manifest.json
failures.csv
```
