# Python scripting for custom states

The CLI intentionally supports only curated `neutral` and `stockholder` state
policies. That is a release feature, not a limitation: the public command should
not silently turn a custom state guess into a reference density.

Use Python when the state itself is part of the question.

## A good custom-state record

A custom state should answer a few plain questions before any SCF calculation is
run:

```text
Which element is this?
What is the charge and therefore the electron count?
What spin multiplicity is intended?
Which compact configuration is being represented?
How many alpha and beta electrons are assigned to each angular-momentum l block?
Is this a reference state, a diagnostic state, or a purely local project choice?
```

The alpha/beta `l` counts are the key spherical-atom input. For example, a
nitrogen-like `2p3` open shell is not represented by choosing three particular p
orbitals. It is represented by distributing the open-shell occupation over the
complete p manifold during SCF.

## Minimal workflow

A practical custom-state script usually follows this order:

1. Construct or load one explicit state record.
2. Validate the electron count, multiplicity, and alpha/beta `l` counts.
3. Resolve the basis source and record its hash or package name.
4. Build a dry-run-like plan or local manifest before running SCF.
5. Run spherical UKS or UHF only after the state and basis are reviewed.
6. Write profiles, radii, QA, and optional Multiwfn files with the same metadata style as the CLI.

The package APIs used by the CLI are available for this purpose, but scripts
should keep their inputs visible. Avoid hiding the scientific state definition
behind a long helper function unless it is thoroughly documented.

## Public imports

The supported scripting interface is imported directly from the package:

```python
from atomref_proatoms import (
    AtomState,
    interpolate_density,
    make_spherical_uks,
    select_packaged_states,
    validate_atom_state,
)
```

Importing the package remains lightweight and does not require PySCF. Calling
SCF-backed functions such as `make_spherical_uks` requires the `generator`
extra. The complete supported surface, signatures, units, and optional-dependency
boundaries are listed in the [Python API](../api.md).

## Example notebook

The expert notebook is:

```text
examples/03_python_custom_state_pipeline/custom_state_pipeline.ipynb
```

It starts with a small custom state record, checks the same schema-level fields
used by the project, inspects a local basis source, and outlines how SCF-derived
profiles and Multiwfn files would be written. The optional SCF cell is disabled
by default so documentation execution does not accidentally run quantum-chemistry
work.

For anions, transition metals, lanthanides, and actinides, custom state scans
should be treated as diagnostics unless supported by a curated or experimental
state source. A generated density can be useful without being a reference state.
