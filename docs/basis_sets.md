# Basis-set layer

The basis-set layer defines the Gaussian basis data used to generate the v1
spherical proatomic density profiles. It is a compact, frozen input layer rather
than a general basis-set database.

The authoritative files are stored under `data/basis_sets/`. Each bundle contains
one NWChem-format spherical basis file, a manifest, a checksum file, local
reference notes, and a short bundle README.

## Active v1 basis branches

| basis_id | active v1 role | profile coverage |
|---|---|---:|
| `x2c-QZVPall` | primary H-Rn scalar-relativistic branch | H-Rn |
| `dyall-v4z` | primary H-Lr heavy-element branch | H-Lr |

Auxiliary frozen basis bundles may be present for sensitivity checks, but they
are not active v1 profile datasets unless selected in `data/profile_datasets.yaml`.

## Identity and checks

The basis text checksum is the basis-data identity used by the project. Ordinary
checks are offline and validate:

- required bundle files;
- SHA256 checksums;
- NWChem spherical-basis headers;
- manifest/source consistency;
- declared element coverage.

Run from the repository root:

```bash
python scripts/check_basis_bundles.py
```

If PySCF is installed, the same command also performs representative basis-parse
smoke checks. If PySCF is unavailable, those smoke checks are skipped while the
offline structural checks still run.

For full methods, source, citation, and redistribution notes, see
`data/basis_sets/README.md`.
