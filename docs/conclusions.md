# Conclusions

`atomref-proatoms` currently provides a validated spherical proatomic data layer with 501 curated state records and 1289 generated dataset-state rows across four all-electron scalar-relativistic basis branches. The generated profiles, density-cutoff radii, QA rows, supplemented/augmented sensitivity comparisons, primary-basis comparison artifacts, and Multiwfn interoperability files are internally consistent under the current validators.

The main scientific conclusions are:

1. The primary branches, `x2c-QZVPall` for H--Rn and `dyall-v4z` for H--Lr, are the recommended default reference gauges.
2. The supplemented/augmented branches are best interpreted as explicit alternative gauges and sensitivity diagnostics for neutral and anion tails, not as silent replacements for the primary branches.
3. The x2c supplemented comparison is uniformly low-sensitivity in the current generated data.
4. The Dyall augmented comparison has high-sensitivity rows, but these are concentrated in formal anion references and do not indicate data corruption or failed validation.
5. The primary x2c-vs-Dyall comparison over H--Rn is low-difference for most states, with a small upper tail dominated by formal anion behavior.

The committed Multiwfn `.rad` and `.wfn` files expose the primary reference gauges to practical Multiwfn workflows, while preserving the same state, basis, and reference-gauge interpretation as the profile/radii/QA layer. They are derived products; they do not redefine the state policy or replace the profile/radii/QA contract.
