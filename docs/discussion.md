# Discussion

## Primary branches as the default gauge

The primary branches are the most appropriate default for ordinary downstream use. They are broad, all-electron, scalar-relativistic, quadruple-zeta-like reference gauges with complete generated coverage over their declared ranges. They also avoid mixing core conventions, basis families, or charge-specific dataset IDs in the default profile layer.

`x2c-QZVPall` is the natural default when H--Rn coverage is sufficient. `dyall-v4z` is the natural default when H--Lr coverage is required or when a single Dyall-family branch is desired. The primary-basis comparison shows that these two families agree closely for most H--Rn matched states, while the largest differences occur in formal anion tails. This supports treating primary-basis differences as a scientific diagnostic rather than a validation failure.

## Role of supplemented and augmented branches

The supplemented/augmented branches answer a narrower question: how much do the spherical reference densities change when additional diffuse or supplemented radial flexibility is introduced? The current results separate two behaviors. `x2c-QZVPall → x2c-QZVPall-s` is low-sensitivity for all matched neutral and anion rows. `dyall-v4z → dyall-av4z` is also well behaved for neutral rows, but it shows high sensitivity for a subset of formal anions.

This does not mean the augmented branch is wrong. It means the formal anion reference gauge has a tail-sensitive component under that basis family. For analyses where only qualitative bond-centered deformation-density features are needed, this may not matter. For analyses that interpret absolute anion tails, cutoff radii at very low density, or charge-transfer magnitudes, the supplemented/augmented branch should be used as an explicit sensitivity check.

## Formal anions

Formal anions are included because reference-density workflows often require a density for a formal charge state even when the corresponding isolated atom or ion is not known as a stable experimental species. The documentation and state table preserve this distinction by labeling these rows as formal monoanions or formal multianions.

The current basis-sensitivity results reinforce that this distinction is not cosmetic. The high-sensitivity rows in the Dyall augmented comparison are formal anions. This is scientifically reasonable: extra electrons in a formal negative reference can occupy diffuse radial regions that are particularly sensitive to augmented basis functions. The correct response is to report and expose these sensitivities, not to delete the rows or to reinterpret them as physical isolated-ion evidence.

## Hard failures, warnings, and diagnostics

The validation layer separates several categories of concern.

A hard failure would include stale or mismatched metadata, failed SCF completion, invalid grids, non-finite density values, inconsistent state-record digests in a comparison, impossible electron counts, or cutoff radii that cannot be derived from the declared profile range. No such failures are present in the committed data layer.

A validation warning is a condition worth inspecting but not automatically disqualifying. Linear-dependency handling and dropped primitives fall in this category when the final density still passes independent electron-count and sphericity checks.

A scientific outlier is a row whose metrics show large basis-family or diffuse-tail sensitivity while the integrity checks pass. The formal-anion outliers in the current comparison artifacts are in this category.

An informational diagnostic is a metric that helps interpret the data but is not itself a gate: pointwise maximum density difference, moment shifts, tail-electron differences beyond fixed radii, and the exact radius where \(\max|\Delta N(r)|\) occurs.

## Multiwfn interoperability context

Multiwfn is a practical motivation for later export work because it supports wavefunction and real-space density analyses, promolecular and deformation-density concepts, Hirshfeld/Hirshfeld-I-like workflows, and radial-function operations. In this project, however, Multiwfn is an interoperability target, not a state-selection authority. The state and basis policies described here remain the scientific definition of the data layer.

The next Multiwfn stage can add `.rad` and `.wfn` outputs without changing the profile/radii/QA interpretation. The safest order is to validate how Multiwfn interprets representative atomic wavefunction containers, then implement density-only `.rad` export, and only then implement `.wfn` export for cases where a wavefunction container is needed.

## Limitations

The data layer is a reference convention, not an experimental measurement of atomic size and not a universal ground-state oracle. Approximate density-functional methods can be delicate for weakly bound anions, and finite Gaussian basis sets can affect low-density tails. The present QA and comparison artifacts make those sensitivities visible, but they do not eliminate the conceptual limitations of formal anion references.

The state table is intentionally scoped. It is not a complete catalogue of all atomic excited states, metastable anions, or possible method-selected occupations. Users who need a non-default occupation should treat it as a new reference gauge and document the state explicitly.

Finally, the current repository commits profile, radii, QA, and comparison tables, but not the expensive local SCF checkpoint layer. Full regeneration therefore requires local compute artifacts or rerunning the SCF workflow with the declared generator dependencies.
