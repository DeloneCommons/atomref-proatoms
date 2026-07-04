# Basis-set input data

This directory contains the fixed basis-set input layer used by `atomref-proatoms`
for spherical proatomic radial electron-density generation. The directory is not
a general basis-set database: it contains the basis families selected for the
first neutral production datasets plus auxiliary frozen inputs kept for
basis-sensitivity work.

All basis definitions are stored in NWChem format with spherical/pure Gaussian
basis functions. Generated profile metadata must record both the `basis_id` and
the `dataset_id`; diffuse and non-diffuse basis branches must not be merged
silently.

## Basis-set selection rationale

The primary H-Rn branch uses `x2c-QZVPall`. This Karlsruhe x2c quadruple-zeta
basis family is a practical default for spin-free X2C all-electron calculations.
The quadruple-zeta level is preferred over lower-zeta x2c-TZVPall-like
alternatives because radial density tails and density-cutoff radii are sensitive
to basis quality, while still keeping the dataset feasible for a reusable
empirical proatom library.

The primary heavy-element extension uses `dyall-v4z`. It provides continuous
coverage through the actinide region and is therefore the default basis branch
for the H-Lr dataset.

The supplemented/augmented branches, `x2c-QZVPall-s` and `dyall-av4z`, are
active v2 anion-sensitivity inputs. They are intentionally separate from the
primary non-diffuse branches. In particular, `dyall-av4z` has discontinuous
element coverage and should be treated as an available-element auxiliary basis,
not as an H-Lr basis.

## Directory layout

```text
data/basis_sets/
  README.md
  basis_set_summary.json
  LICENSE-BSE-BSD-3-Clause.txt

  x2c-QZVPall/
    basis.nw
    manifest.json
    sha256sums.txt
    references.md
    README.md

  x2c-QZVPall-s/
    basis.nw
    manifest.json
    sha256sums.txt
    references.md
    README.md

  dyall-v4z/
    basis.nw
    manifest.json
    sha256sums.txt
    references.md
    README.md

  dyall-av4z/
    basis.nw
    manifest.json
    sha256sums.txt
    references.md
    README.md

scripts/
  check_basis_bundles.py
```

Each bundle stores one basis text file, one canonical JSON manifest, one SHA256
checksum for the basis text, and local reference notes. The top-level summary is
a compact index of the bundle manifests.

## Methods: source data and metadata

Basis definitions were retrieved from Basis Set Exchange in NWChem format. The
exact BSE API URL used for each exported basis is recorded in the corresponding
`manifest.json` file as `source.source_api_url`.

For each bundle, the manifest records the upstream basis name, BSE export
version, upstream basis version, retrieval date, basis-file checksum, element
coverage intervals, active v2 dataset identifiers, redistribution note, and the
expected spherical NWChem header. The basis-file checksum is the basis-data
identity used by this project; documentation and metadata edits do not change the
basis-data identity.

The basis text is stored as `basis.nw` in each bundle. It is the file consumed by
the density generator and by the structural checker.

## Bundle summary

| basis_id | role | coverage | n_elements | active v2 dataset IDs |
|---|---|---:|---:|---|
| `x2c-QZVPall` | primary H-Rn | H-Rn | 86 | `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2` |
| `x2c-QZVPall-s` | auxiliary H-Rn anions | H-Rn | 86 | `pbe0_sfx2c_x2cqzvpalls_h-rn_anions_spherical_v2` |
| `dyall-v4z` | primary H-Lr / actinide-capable | H-Og | 118 | `pbe0_sfx2c_dyallv4z_h-lr_spherical_v2` |
| `dyall-av4z` | auxiliary augmented anions / discontinuous | H-Ba, Hf-Ra, Rf-Og | 88 | `pbe0_sfx2c_dyallav4z_h-ba_hf-ra_anions_spherical_v2` |

## Validation

Run from the repository root:

```bash
python scripts/check_basis_bundles.py
```

The checker validates required bundle files, the SHA256 checksum of `basis.nw`,
the NWChem spherical basis header, BSE header metadata, and element coverage
intervals. If PySCF is installed, the same command also performs small PySCF
basis-parse smoke checks. If PySCF is not installed, the script reports that the
PySCF smoke checks were skipped and still completes the structural validation.

## Citation and redistribution

Basis files in this directory were obtained from Basis Set Exchange. When
publishing results generated from this data layer, cite Basis Set Exchange and
the upstream basis-set references listed in each bundle.

The BSE BSD-3-Clause license notice is included as
`LICENSE-BSE-BSD-3-Clause.txt`. Dyall basis-set source records are additionally
covered by the upstream Zenodo/CC-BY citation recorded in the Dyall bundle
references.

## Related documentation

- Scientific model and active electronic-structure convention: `docs/theory.md`.
- Input-data summary: `docs/inputs.md`.
- Basis validation workflow: `docs/workflow.md` and `scripts/README.md`.
