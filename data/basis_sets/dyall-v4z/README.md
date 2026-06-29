# dyall-v4z

This bundle defines the `dyall-v4z` basis input used by `atomref-proatoms`.
It is part of the fixed basis-set layer for spherical PBE0/sf-X2C proatomic
radial-density generation.

## Scope

- Role: primary actinide-capable Dyall quadruple-zeta basis for the H-Lr production extension.
- Coverage: H-Og basis coverage; active v1 profile dataset H-Lr.
- Basis representation: NWChem spherical/pure Gaussian basis functions.
- Active v1 dataset identifiers: `pbe0_sfx2c_dyallv4z_h-lr_spherical_v1`.

The Dyall v4z branch is included to provide a relativistic quadruple-zeta basis with
continuous heavy-element coverage, including lanthanides and actinides. It is the
primary branch for the H-Lr extension beyond the H-Rn x2c-QZVPall dataset.

The basis file covers H-Og. The active production dataset is intentionally H-Lr unless
the state-selection policy is expanded later.

## Bundle metadata

The canonical metadata record is `manifest.json`. It includes the upstream BSE
basis name, exact BSE API URL, BSE export version, upstream basis version,
retrieval date, coverage intervals, active v1 dataset identifiers, and
redistribution note. The exact source URL is recorded as `source.source_api_url`
in `manifest.json`.

The basis-data identity is the SHA256 checksum of `basis.nw`:

```text
0ee543855f8b1e7fbe9868d4abb844d8e8cc8b8c2694067b2b40de014bb4be94
```

`sha256sums.txt` repeats this checksum in standard checksum-file form.
`references.md` records the BSE citation and the upstream basis-family citation.

## References

Dyall basis-set archive, Zenodo Version 1, DOI: 10.5281/zenodo.7574629, plus the
original Dyall references listed in this bundle.
