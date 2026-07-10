# How-it-works notebooks

This directory contains notebook-style documentation that complements the
scientific and data-reference pages.

Two notebook roles are useful for this project:

- profile-data inspection notebooks, which read `data/profiles/`,
  `data/radii/`, and `data/qa/` without running SCF;
- method demonstration notebooks, which run a small optional generator example to
  show the difference between ordinary SCF plus post-SCF angular averaging and
  the spherical fractional-occupation model.

The current notebooks are:

- `proatomic_profiles.ipynb`
- `spherical_vs_post_average_demo.ipynb`
- `multiwfn_wfn_plane_validation.ipynb`

The profile-inspection notebook reads generated profile, radii, and QA tables
and can be used to display summary tables, selected radial density curves,
cutoff radii, basis-sensitivity summaries, and QA status. The sphericalization
demo runs one small optional SCF example from the frozen project basis files and
compares the release spherical density with ordinary UKS plus post-SCF angular
averaging. The Multiwfn WFN validation notebook is a local H/O/H2O interoperability
check: it writes representative WFN files, evaluates them with the package WFN
reader, and compares Multiwfn point/plane outputs against PySCF references.

Method demonstration notebooks may require the `generator` dependency extra and
should avoid writing persistent data outputs into the repository. Temporary
basis or SCF material should be kept outside tracked paths or created in a
notebook-local temporary directory.

The Multiwfn validation notebook should be copied to `local-data/` before local execution. It expects the Multiwfn executable and optional `settings.ini` there, and it writes only ignored local validation outputs.
