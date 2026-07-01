# Documentation notebooks

This directory contains user-facing narrative notebooks for inspecting released
v1 data products. Notebooks in this directory are report and visualization layers;
they should read generated artifacts rather than run SCF calculations.

Current notebook:

```text
proatomic_profiles_v1.ipynb
```

The notebook reads:

```text
data/profiles/
data/radii/
data/qa/
```

and can be used to display dataset summaries, QA status, selected radial density
curves, and compact radius tables.

Notebook outputs are explanatory. The release artifacts themselves are generated
by the workflow scripts and stored under `data/`.
