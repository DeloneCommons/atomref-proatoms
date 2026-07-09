# Python scripting for custom states

The CLI intentionally supports only curated `neutral` and `stockholder` state
policies. This keeps the public tool reproducible and avoids turning it into a
state-search interface.

Use Python scripting when you need:

- explicit configurations such as `s2p3` or `s2d`;
- custom multiplicities;
- state-sensitivity scans;
- special basis/method conventions;
- custom project pipelines.

A scripting workflow should preserve the same provenance discipline as the CLI:

```text
state definition
method and relativistic convention
basis source and hash
SCF settings
profile/radii/QA settings
export settings
```

The expert notebook is:

```text
examples/03_python_custom_state_pipeline/custom_state_pipeline.ipynb
```

It shows how to think about charge, spin, configuration, alpha/beta counts by
angular momentum `l`, profile interpolation, and artifact organization.

For anions, transition metals, lanthanides, and actinides, custom state scans
should be treated as diagnostics unless supported by a curated or experimental
state source.
