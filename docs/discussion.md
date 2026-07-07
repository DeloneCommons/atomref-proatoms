# Discussion

## Primary branches as the default gauge

The primary branches are the most appropriate default for ordinary downstream use. They are broad, all-electron, scalar-relativistic, quadruple-zeta-like reference gauges with complete generated coverage over their declared ranges. They also avoid mixing core conventions, basis families, or charge-specific dataset IDs in the default profile layer.

`x2c-QZVPall` is the natural default when H--Rn coverage is sufficient. `dyall-v4z` is the natural default when H--Lr coverage is required or when a single Dyall-family branch is desired. The primary-basis comparison shows that these two families agree closely for most H--Rn matched states, while the largest differences occur in formal anion tails. This supports treating primary-basis differences as a scientific diagnostic rather than a validation failure.

## Role of supplemented and augmented branches

The supplemented/augmented branches answer a narrower question: how much do the spherical reference densities change when additional radial flexibility is introduced? The current results separate two behaviors. `x2c-QZVPall → x2c-QZVPall-s` is low-sensitivity for all matched neutral and anion rows. `dyall-v4z → dyall-av4z` is also well behaved for neutral rows, but it shows high sensitivity for a subset of formal anions.

The two supporting branches should not be read as equivalent diffuse tests. `x2c-QZVPall-s` is an NMR-shielding-oriented `-s` variant of the Karlsruhe x2c basis family, not a conventional density-tail augmented basis. In the present data it can be ignored for most density-reference applications unless a user specifically wants to reproduce this branch as an alternate gauge. When low-density tails are central to the question, `x2c-QZVPall` and `x2c-QZVPall-s` are not the strongest basis family for tail-convergence evidence; the Dyall primary/augmented pair is the more informative comparison where its element coverage exists.

This does not mean the Dyall augmented branch is automatically preferable as the default data branch. It means the formal anion reference gauge has a tail-sensitive component under a basis family that actually adds diffuse radial flexibility. For analyses where only qualitative bond-centered deformation-density features are needed, this may not matter. For analyses that interpret absolute anion tails, cutoff radii at very low density, or charge-transfer magnitudes, the primary and augmented/supplemented branches should be reported as separate reference gauges rather than silently merged.

## Formal anions

Formal anions are included because reference-density workflows often require a density for a formal charge state even when the corresponding isolated atom or ion is not known as a stable experimental species. The documentation and state table preserve this distinction by labeling these rows as formal monoanions or formal multianions.

The current basis-sensitivity results reinforce that this distinction is not cosmetic. The high-sensitivity rows in the Dyall augmented comparison are formal anions. This is scientifically reasonable: extra electrons in a formal negative reference can occupy diffuse radial regions that are particularly sensitive to augmented basis functions. The correct response is to report and expose these sensitivities, not to delete the rows or to reinterpret them as physical isolated-ion evidence.

## Hard failures, warnings, and diagnostics

The validation layer separates several categories of concern.

A hard failure would include stale or mismatched metadata, failed SCF completion, invalid grids, non-finite density values, inconsistent state-record digests in a comparison, impossible electron counts, or cutoff radii that cannot be derived from the declared profile range. No such failures are present in the committed data layer.

A validation warning is a condition worth inspecting but not automatically disqualifying. Linear-dependency handling and dropped primitives fall in this category when the final density still passes independent electron-count and sphericity checks.

A scientific outlier is a row whose metrics show large basis-family or low-density-tail sensitivity while the integrity checks pass. The formal-anion outliers in the current comparison artifacts are in this category.

An informational diagnostic is a metric that helps interpret the data but is not itself a gate: pointwise maximum density difference, moment shifts, tail-electron differences beyond fixed radii, and the exact radius where \(\max|\Delta N(r)|\) occurs.

## Multiwfn interoperability context

Multiwfn is a practical motivation for later export work because it supports wavefunction and real-space density analyses, promolecular and deformation-density concepts, Hirshfeld/Hirshfeld-I-like workflows, and radial-function operations ([Lu and Chen, 2012](https://doi.org/10.1002/jcc.22885); [Lu, 2024](https://doi.org/10.1063/5.0216272)). In this project, however, Multiwfn is an interoperability target, not a state-selection authority. The state and basis policies described here remain the scientific definition of the data layer.

The H/O/H2O WFN validation clarifies the practical role of file formats. Project-native NPZ and structured SCF artifacts remain the efficient internal path for PySCF-side work. Radial profiles, and later compact `.rad` exports, remain the preferred density-only representation for stockholder/Hirshfeld-like workflows. A `.wfn` file is an interoperability container for workflows that need wavefunction-like Gaussian primitive and orbital coefficient data.

The package WFN reader and evaluator added for this validation should therefore be interpreted narrowly. It is useful for checking that a saved WFN reproduces the density and spin-density semantics intended by the exporter; it is not a general PySCF-native WFN importer and does not replace the profile/radii/QA data layer.

The validation is also intentionally limited. H, O, and H2O exercise open-shell atom spin typing, molecular WFN export, spherical-AO to Cartesian-primitive expansion at the WFN boundary, and Multiwfn deformation-density plane output. They do not prove every element, charge, basis, formal anion, high-angular-momentum shell, or future Multiwfn version. Full `.rad` export, full `.wfn` export, generated interoperability products, and a user-facing generator remain separate later stages.

## Limitations

The data layer is a reference convention, not an experimental measurement of atomic size and not a universal ground-state oracle. Approximate density-functional methods can be delicate for weakly bound anions, and finite Gaussian basis sets can affect low-density tails. The present QA and comparison artifacts make those sensitivities visible, but they do not eliminate the conceptual limitations of formal anion references.

The state table is intentionally scoped. It is not a complete catalogue of all atomic excited states, metastable anions, or possible method-selected occupations. Users who need a non-default occupation should treat it as a new reference gauge and document the state explicitly.

Finally, the current repository commits profile, radii, QA, and comparison tables, but not the expensive local SCF checkpoint layer. Full regeneration therefore requires local compute artifacts or rerunning the SCF workflow with the declared generator dependencies.
