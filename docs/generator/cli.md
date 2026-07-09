# CLI reference

The MVP public command is:

```bash
atomref-proatoms generate [options]
```

Use the installed help as the exact source for current flags:

```bash
atomref-proatoms generate --help
```

This page explains the main concepts behind those flags.

## Basic command

```bash
atomref-proatoms generate \
  --elements C,N,O \
  --method PBE0 \
  --relativity x2c \
  --basis bse:x2c-QZVPall \
  --state-policy neutral \
  --artifacts profiles,rad \
  --workdir ./proatoms
```

Use `--dry-run` to resolve the plan without running SCF:

```bash
atomref-proatoms generate ... --dry-run
```

Dry run writes:

```text
atomref_proatoms_workspace.json
run_config.input.json
run_config.resolved.json
plan.json
```

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

## State policies

```text
--state-policy neutral
```

selects only curated neutral states.

```text
--state-policy stockholder
```

selects the curated stockholder/Hirshfeld-I-like state set for the requested
elements.

For stockholder runs, you may filter charges:

```bash
--charges=-1,0,+1
```

The `=` form is recommended because values beginning with `-` can otherwise be
parsed as options by the shell/argument parser.

The CLI does not accept custom configurations or multiplicities. Use Python
scripting for those workflows.

## Method and relativity

`--method hf` is reserved for HF generation. Other method strings are passed to
PySCF as DFT exchange-correlation specifications, for example:

```bash
--method PBE0
--method B3LYP
--method "wB97X-D"
```

The generator does not maintain its own dictionary of valid DFT names. The
installed PySCF version is the source of truth.

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

Detected ECP/effective-core basis data fail by default unless `--allow-ecp` is
used. Local basis files may have unknown full-electron status; for WFN export,
use `--allow-unverified-basis` only when you accept that responsibility.

## Artifacts

```text
profiles  native profiles + radii + QA
rad       Multiwfn density-only .rad files
wfn       neutral-only PROAIM .wfn files
all       profiles + rad + neutral-only wfn
```

Default:

```bash
--artifacts profiles,rad
```

SCF artifacts are always written as part of execution and are used for resume and
export.

## Workdir behavior

One workdir corresponds to one method + relativity + basis + state-policy
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
