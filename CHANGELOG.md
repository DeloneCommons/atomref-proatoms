# Changelog

All notable changes to this project are documented in this file. The project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html) for the Python
toolkit; published data products carry the same release version.

## 2.0.0 - 2026-07-10

### Added

- Versioned spherical proatomic profile, cutoff-radius, QA, and Multiwfn
  interoperability datasets.
- Public Python API and `atomref-proatoms generate` command for curated local
  generation workflows.
- Reproducible state, basis, SCF, profile, export, and documentation validation
  layers.

### Fixed during release review

- Use the outermost outward density-cutoff crossing for non-monotonic profile
  tails, consistently in library calculations and regenerated release data.
- Use signed charged-state filenames consistently in generator plans and actual
  Multiwfn `.rad` outputs.
- Validate runtime controls and preserve them in input, resolved, and plan
  provenance files.
- Build installed-wheel smoke artifacts from a clean staged source tree and
  reject stale or incomplete wheel contents.
- Align CLI errors, grid defaults, maintainer inspection behavior, documentation,
  and release-distribution checks with their public contracts.

[Semantic Versioning]: https://semver.org/
