# How-it-works notebooks

This directory contains notebook-style documentation that complements the
scientific and data-reference pages.

Two notebook roles are useful for this project:

- release-artifact inspection notebooks, which read `data/profiles/`,
  `data/radii/`, and `data/qa/` without running SCF;
- method demonstration notebooks, which run a small optional generator example to
  show the difference between ordinary SCF plus post-SCF angular averaging and
  the spherical fractional-occupation model.

The current release-artifact notebook is:

- `proatomic_profiles_v1.ipynb`
- `spherical_vs_post_average_demo.ipynb`

The artifact-inspection notebook reads the generated v1 profile, radii, and QA
tables and can be used to display summary tables, selected radial density curves,
cutoff radii, and QA status. The sphericalization demo runs one small optional
SCF example from the frozen project basis files and compares the production
spherical density with ordinary UKS plus post-SCF angular averaging.

Method demonstration notebooks may require the `generator` dependency extra and
should avoid writing persistent data artifacts into the repository. Temporary
basis or SCF material should be kept outside tracked paths or created in a
notebook-local temporary directory.
