# x2c-QZVPall-s

This bundle defines the `x2c-QZVPall-s` basis input used by `atomref-proatoms`.
It is part of the fixed basis-set layer for spherical PBE0/sf-X2C proatomic
radial-density generation.

## Scope

- Role: auxiliary H-Rn supplemented x2c basis retained for basis-sensitivity work.
- Coverage: H-Rn.
- Basis representation: NWChem spherical/pure Gaussian basis functions.
- Active dataset identifiers: `pbe0_sfx2c_x2cqzvpalls_h-rn_anions_spherical_v2`.

The active profile configuration uses this basis for the H-Rn anion
sensitivity branch. Results produced with it remain separately identified by
dataset and basis identifiers.

## Bundle metadata

The canonical metadata record is `manifest.json`. It includes the upstream BSE
basis name, exact BSE API URL, BSE export version, upstream basis version,
retrieval date, coverage intervals, active dataset identifiers, and
redistribution note. The exact source URL is recorded as `source.source_api_url`
in `manifest.json`.

The basis-data identity is the SHA256 checksum of `basis.nw`:

```text
f11e108ed19a8e72a6a9858e7f427972c5e4fd47fdc753290b9b83aa2d5f8dec
```

`sha256sums.txt` repeats this checksum in standard checksum-file form.
`references.md` records the BSE citation and the upstream basis-family citation.

## References

Franzke, Spiske, Pollak, and Weigend, J. Chem. Theory Comput. 2020, 16, 5658-5674. DOI:
10.1021/acs.jctc.0c00546.
