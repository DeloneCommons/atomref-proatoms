# Published data

This directory is the released data layer of `atomref-proatoms`. You do not need
to install the Python package, PySCF, or Multiwfn to read the committed CSV and
JSON files. Use the toolkit only if you want to select states programmatically or
generate a new local dataset.

## Find the product you need

| Product | Location | What it contains |
|---|---|---|
| Spherical radial densities | [`profiles/`](profiles/) | One shared radial grid and one density column per atomic state |
| Density-cutoff radii | [`radii/`](radii/) | One row per state, with radii in bohr and ångström |
| Validation and basis comparisons | [`qa/`](qa/) | Per-state QA, summaries, outliers, and comparison metrics |
| Multiwfn files | [`multiwfn_artifacts/`](multiwfn_artifacts/) | Released `.rad` files and neutral-atom `.wfn` files |
| Atomic-state definitions | [`states/`](states/) | Curated states, source/status tables, and formal-anion labels |
| Frozen basis inputs | [`basis_sets/`](basis_sets/) | NWChem basis files, manifests, checksums, and references |
| Dataset-generation contract | [`profile_datasets.yaml`](profile_datasets.yaml) | Method, grid, QA, basis, coverage, and export policy |

The profile, radii, and QA directories use the same dataset IDs. Files carrying
the same dataset ID belong together.

## Choose a basis branch

| Basis branch | Coverage | Rows | Recommendation |
|---|---|---:|---|
| `x2c-QZVPall` | H--Rn | 430 | Default when H--Rn coverage is sufficient |
| `dyall-v4z` | H--Lr | 501 | Default when broader heavy-element coverage is needed |
| `x2c-QZVPall-s` | H--Rn | 192 | Supplemented neutral/anion comparison branch |
| `dyall-av4z` | H--Ba and Hf--Ra where available | 166 | Augmented neutral/anion comparison branch |

Start with a primary branch. The supplemented and augmented branches are
separate reference gauges for sensitivity analysis; do not silently substitute
them for primary data. Formal anion rows are likewise explicit reference-density
conventions, not claims of stable isolated atomic anions.

The exact dataset IDs and scopes are listed in the
[data-product reference](../docs/data.md#profile-datasets). Scientific guidance
for choosing a branch is in the [Results](../docs/results.md#practical-result)
and [Discussion](../docs/discussion.md).

## Read a profile table

Each `profiles.csv` is a wide table:

```text
r_bohr,rho_e_bohr3__<state_id>,rho_e_bohr3__<state_id>,...
```

`r_bohr` is the distance from the nucleus in bohr. Each other column is the
spin-summed three-dimensional density `rho(r)` in electrons/bohr³ for one
curated state. It is not the radial distribution `4*pi*r^2*rho(r)`. The electron
count is

```text
N = integral 4*pi*r^2*rho(r) dr
```

For example, with pandas installed, neutral carbon in the primary x2c branch can
be read as follows:

```python
import pandas as pd

path = (
    "data/profiles/"
    "pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2/profiles.csv"
)
table = pd.read_csv(path)
r_bohr = table["r_bohr"]
rho = table["rho_e_bohr3__C_q0_mult3_nist"]
```

Use the adjacent `metadata.json` and the matching radii and QA rows whenever a
profile is reused. The [profile contract](profiles/README.md) documents column
naming and metadata in detail; the
[profile-inspection notebook](../docs/notebooks/proatomic_profiles.ipynb) provides
a fuller worked example.

## Version, validation, and reuse

The current profile data version is `2.0.0`. All 1289 committed dataset-state
rows pass the declared numerical validation criteria; scientific basis
sensitivity is reported separately and is not hidden as a pass/fail result. See
the [paper-style Results](../docs/results.md) and the compact generated
[`qa_report.md`](qa/qa_report.md).

For the complete published data layer, use the
[Zenodo v2.0.0 archive](https://doi.org/10.5281/zenodo.21291022) or the
[tagged GitHub release](https://github.com/DeloneCommons/atomref-proatoms/releases/tag/v2.0.0).
The PyPI wheel is the installable toolkit and intentionally excludes these
complete generated profile, radii, QA, and Multiwfn artifact trees.

When publishing work based on these files, cite the
[concept DOI](https://doi.org/10.5281/zenodo.21291021) for general use and report
the exact release version and dataset ID or basis branch used. Use the
[version-specific v2.0.0 DOI](https://doi.org/10.5281/zenodo.21291022) when an
immutable reference to the exact archived files is required. Code and data use
different licenses, and frozen basis inputs retain upstream notices; see the
[citation and reuse guidance](../docs/other.md#citation-and-reuse-guidance) and
[license and attribution summary](../docs/license.md).
