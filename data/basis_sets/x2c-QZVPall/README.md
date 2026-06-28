# x2c-QZVPall

This bundle defines the `x2c-QZVPall` basis input used by `atomref-proatoms`.
It is part of the fixed basis-set layer for spherical PBE0/sf-X2C proatomic
radial-density generation.

## Scope

- Role: primary H-Rn basis for the default PBE0/sf-X2C spherical proatom dataset.
- Coverage: H-Rn.
- Basis representation: NWChem spherical/pure Gaussian basis functions.
- Planned dataset identifiers: `pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v0`.

This is the default Karlsruhe x2c quadruple-zeta basis branch for H-Rn. The quadruple-
zeta level is preferred over lower-zeta x2c-TZVPall-like alternatives because radial
density tails and density-cutoff radii are sensitive to basis quality, while the project
does not require a still larger validation-only basis by default.

Non-diffuse primary branch. Diffuse/supplemented results must not be silently merged
into this dataset.

## Bundle metadata

The canonical metadata record is `manifest.json`. It includes the upstream BSE
basis name, exact BSE API URL, BSE export version, upstream basis version,
retrieval date, coverage intervals, intended dataset identifiers, and
redistribution note. The exact source URL is recorded as `source.source_api_url`
in `manifest.json`.

The basis-data identity is the SHA256 checksum of `basis.nw`:

```text
acdfcd7694d0de10703ff9194e3190f6859a51dabd23a8dfb68b7e3ec44b1d21
```

`sha256sums.txt` repeats this checksum in standard checksum-file form.
`references.md` records the BSE citation and the upstream basis-family citation.

## References

Franzke, Spiske, Pollak, and Weigend, J. Chem. Theory Comput. 2020, 16, 5658-5674. DOI:
10.1021/acs.jctc.0c00546.
