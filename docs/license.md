# License and attribution

The root `LICENSE.md` file is the canonical repository license statement.

Summary:

- Code in `src/`, `scripts/`, and `tests/` is released under the MIT License.
- Released data tables, metadata, documentation, and notebooks are released under
  Creative Commons Attribution 4.0 International (CC BY 4.0), unless a file or
  upstream notice states otherwise.
- Frozen basis files retain the Basis Set Exchange BSD-3-Clause notice included
  in `data/basis_sets/LICENSE-BSE-BSD-3-Clause.txt`.
- Compact atomic-state labels are prepared from the NIST Atomic Spectra Database,
  NIST Standard Reference Database 78. Raw NIST ASD pages and quantitative SRD
  tables are not redistributed in this repository.

When publishing work based on these data, cite the atomref-proatoms
[concept DOI](https://doi.org/10.5281/zenodo.21291021), report the exact release
version and dataset ID or basis branch, and cite Basis Set Exchange, the upstream
basis references used by the selected dataset, and the NIST Atomic Spectra
Database for the state-configuration source layer.
The repository root `CITATION.cff` cites the released dataset and therefore
records `type: dataset` and the dataset license, `CC-BY-4.0`. The accompanying
code remains MIT-licensed under the root `LICENSE.md`; the Python distribution's
metadata reflects both kinds of bundled material. Use the
[version-specific v2.0.0 DOI](https://doi.org/10.5281/zenodo.21291022) when an
immutable reference to the exact archived files is required. See the full
[citation and reuse guidance](other.md#citation-and-reuse-guidance).
