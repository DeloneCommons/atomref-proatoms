# Multiwfn interoperability

Multiwfn export is deferred until the core v1 profile pipeline is stable. The current
tracked outputs should remain radial profiles and aggregate metadata, not raw `.wfn`,
`.wfx`, `.molden`, checkpoint, or log files.

A future optional exporter can read `local-data/scf` artifacts and/or canonical profile
CSV data after direct compatibility tests confirm the correct treatment of fractional
spherical occupations.
