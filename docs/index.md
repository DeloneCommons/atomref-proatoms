# atomref-proatoms: spherical reference proatoms

## Abstract

`atomref-proatoms` is a reproducible data layer for spherical atomic and ionic reference densities. The current release provides self-consistent spherical PBE0/sf-X2C radial electron densities for neutral atoms, cations, curated monoanions, and explicitly formal anion references under a fixed state, basis, SCF, profile-extraction, radii, and validation policy. The profiles are intended as documented proatomic reference gauges for stockholder, Hirshfeld-like, promolecular, deformation-density, descriptor, and related real-space workflows. They are not claimed to be universal isolated-atom ground states for every approximate Hamiltonian, basis set, or molecular environment.

The current data layer contains 1289 generated dataset-state rows across four basis branches. The primary branches are `x2c-QZVPall` for H--Rn and `dyall-v4z` for H--Lr. The supplemented/augmented branches, `x2c-QZVPall-s` and `dyall-av4z`, contain neutral and anion rows used to quantify branch and tail sensitivity; cations are deliberately not duplicated in these branches. All committed rows pass the current validation criteria. A committed Multiwfn interoperability product is provided under `data/multiwfn_artifacts/`: 931 SCF-derived `.rad` files for the primary branches and 86 neutral `x2c-QZVPall` PROAIM `.wfn` files for workflows that expect Multiwfn atomic radial-density or atomwfn-style inputs.

## Choose a reading path

| If you want to... | Read... |
|---|---|
| Understand the scientific motivation and evidence | [Introduction](introduction.md) → [Theory](theory.md) → [Methods](methods.md) → [Results](results.md) → [Discussion](discussion.md) → [Conclusions](conclusions.md) |
| Use the published tables or Multiwfn files | [Data products](data.md), then the README in the relevant [data directory on GitHub](https://github.com/DeloneCommons/atomref-proatoms/tree/main/data) |
| Cite or reuse the data | [Citation, release, and reuse guidance](other.md#citation-and-reuse-guidance) |
| Generate a small local subset | [Generator overview and quick start](generator/index.md), then the [how-to guide](generator/howto.md) |
| Use the package from Python | [Python scripting](generator/scripting.md) and the [Python API](api.md) |
| Reproduce or maintain the release | [Workflow and validation](workflow.md) and [repository notes](other.md) |

The first path is organized as a paper-like technical note. Data dictionaries,
script details, notebooks, licensing, and repository operations are separated
from that sequence so that the scientific argument remains readable.

The documentation also includes a compact Multiwfn WFN interoperability notebook
for the fixed H/O/H₂O validation system. The committed `.rad` and `.wfn` files are
practical interoperability products; the profile/radii/QA layer remains the
canonical data representation. The public `atomref-proatoms generate` command is
available for small local generation runs and custom release-adjacent workflows
without redefining the released data contract.

## Data entry points

The main generated files are:

```text
data/profiles/<dataset_id>/profiles.csv
data/radii/<dataset_id>/radii.csv
data/qa/<dataset_id>/qa.csv
data/qa/basis_sensitivity/
data/qa/basis_comparisons/
data/multiwfn_artifacts/
```

The state and generation contracts are:

```text
data/states/curated/atom_states_v2.json
data/states/selection/required_states_v2.csv
data/profile_datasets.yaml
```

The expensive SCF checkpoints and logs are local regeneration material under ignored `local-data/scf/` paths and are not part of the committed data layer.

Use the complete [Zenodo v2.0.0 archive](https://doi.org/10.5281/zenodo.21291022)
or [tagged GitHub release](https://github.com/DeloneCommons/atomref-proatoms/releases/tag/v2.0.0)
for the published data layer. The evolving source tree is available from the
[GitHub repository](https://github.com/DeloneCommons/atomref-proatoms).

## Citation and release access

Please cite the atomref-proatoms [concept DOI](https://doi.org/10.5281/zenodo.21291021)
for general use and report the exact release version and dataset ID or basis
branch used. Cite the [version-specific v2.0.0 DOI](https://doi.org/10.5281/zenodo.21291022)
when an immutable reference to the exact archived files is required.

The complete Zenodo/GitHub release contains the published data layer. The
[PyPI project](https://pypi.org/project/atomref-proatoms/) provides the installable
API, CLI, curated state resources, schemas, presets, and generator tooling, but
not the complete generated profiles, radii, QA, or Multiwfn artifact trees. See
[Citation, release, and reuse guidance](other.md#citation-and-reuse-guidance) for
the full access map and scientific provenance requirements.

## Optional checkout validation

Tagged data can be read directly. To audit the data layer in a source checkout,
run the two artifact checks:

```bash
python scripts/check_profile_artifacts.py --require-generated
python scripts/check_multiwfn_artifacts.py --require-generated
```

The full release gate and documentation-regeneration procedure are in
[Workflow and validation](workflow.md). Full SCF regeneration requires generator
dependencies and local compute resources; it is not needed to consume the
committed data products.

Continue with the [Introduction](introduction.md), or go directly to the
[generator quick start](generator/index.md) if your goal is a local run.
