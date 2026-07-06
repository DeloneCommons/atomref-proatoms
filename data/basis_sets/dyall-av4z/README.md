# dyall-av4z

This bundle defines the `dyall-av4z` basis input used by `atomref-proatoms`.
It is part of the fixed basis-set layer for spherical PBE0/sf-X2C proatomic
radial-density generation.

## Scope

- Role: augmented Dyall quadruple-zeta branch used for neutral/anion basis-sensitivity work.
- Coverage: H-Ba, Hf-Ra, Rf-Og.
- Basis representation: NWChem spherical/pure Gaussian basis functions.
- Active dataset identifiers: `pbe0_sfx2c_dyallav4z_h-ba_hf-ra_spherical_v2`.

The active profile configuration uses this basis for H-Ba/Hf-Ra neutral atoms
and selected anions in the same available intervals, including Fr and Ra
monoanions. The bundle itself also contains basis functions beyond that generated
profile scope; its coverage is discontinuous and excludes the lanthanide and
actinide blocks, so it must not be described as an H-Lr basis.

## Bundle metadata

The canonical metadata record is `manifest.json`. It includes the upstream BSE
basis name, exact BSE API URL, BSE export version, upstream basis version,
retrieval date, coverage intervals, active dataset identifiers, and
redistribution note. The exact source URL is recorded as `source.source_api_url`
in `manifest.json`.

The basis-data identity is the SHA256 checksum of `basis.nw`:

```text
f5a4a4c03a9b08ba6c40ff409f91d89196ba96dcd620dc563f4b1cd103213e96
```

`sha256sums.txt` repeats this checksum in standard checksum-file form.
`references.md` records the BSE citation and the upstream basis-family citation.

## References

Dyall basis-set archive, Zenodo Version 1, [DOI: 10.5281/zenodo.7574629](https://doi.org/10.5281/zenodo.7574629), plus the original Dyall references listed in this bundle.
