# Introduction

## Proatoms as reference gauges

Many atom-centered density analyses require a free-atom reference density. In stockholder and Hirshfeld-like schemes, promolecular-density constructions, deformation-density plots, and real-space descriptors, the reference proatom defines the radial background assigned to each element and charge state. The proatom is therefore a gauge: changing it changes atom-centered shells, tails, and integrated charge-transfer magnitudes, but it does not by itself create directional bond accumulation or other anisotropic interatomic features.

This project provides a source-traceable and reproducible gauge for such workflows. The central data product is a spherical radial electron-density profile, accompanied by state, basis, method, grid, radii, and validation metadata. The aim is not to choose a chemically privileged atom for every molecular environment. The aim is to make the chosen atomic reference explicit, auditable, and stable across downstream analyses.

## Why a spherical self-consistent model is needed

Closed-shell free atoms are spherical in the usual single-determinant picture, but many chemically important atoms and ions are open-shell systems. A standard unrestricted atomic calculation can select a particular orientation within a partially filled `p`, `d`, or `f` shell. Angularly averaging that final density produces a radial curve, but the SCF potential that generated the density was not itself spherical. Because the Coulomb and exchange-correlation contributions are nonlinear functionals of the density, this post-SCF average is not generally equivalent to a self-consistent spherical ensemble.

`atomref-proatoms` therefore defines the proatom at the SCF-model level. Fractional occupations are distributed over complete angular-momentum manifolds during the SCF cycle, and the one-center Fock problem is solved in angular-momentum-averaged radial blocks. The resulting radial density is the density of the spherical reference model, not merely a visualization of an anisotropic solution.

## State-source problem

Neutral atoms and positive ions can be anchored primarily to evaluated spectroscopic state data. In the present data layer, neutral/cation state labels are prepared from compact NIST-derived source tables. The stored state records retain compact configurations, ground-level labels, multiplicities or curated multiplicity assignments, and ionization-energy provenance classes needed for reproducible generation.

Atomic anions require a different treatment. Negative-ion evidence is uneven across the periodic table, and weakly bound, metastable, controversial, or theory-only cases cannot be treated as a single uniform class. The monoanion layer therefore uses a compact Ning--Lu 2022 status table together with explicit project curation. Accepted and provisional monoanions are separated from theory-only diagnostics, excluded/problematic entries, and formal rows introduced only to support reference-density workflows.

For charges below -1, and for required monoanions without an accepted physical row, the dataset uses explicitly formal anion references. These rows are included because stockholder/Hirshfeld-I-like workflows often need an anionic reference density for every atom that can appear in an iterative charge model. They are not claims of stable isolated atomic multianions or experimental negative-ion ground states.

## Basis branches and scientific questions

The current data layer uses four fixed all-electron scalar-relativistic basis branches. Two are primary branches: `x2c-QZVPall` over H--Rn and `dyall-v4z` over H--Lr. Two are supplemented/augmented branches used for neutral and anion tail-sensitivity analysis: `x2c-QZVPall-s` and `dyall-av4z`.

This organization answers five questions:

1. Which spherical atomic and ionic reference densities are provided?
2. Which state, basis, SCF, profile, radii, and validation policies produced them?
3. How stable are the profiles under supplemented or augmented basis branches?
4. How do the two primary basis families compare over their H--Rn overlap?
5. How should users choose between primary and supplemented/augmented branches?

The Results and Discussion sections answer these questions from the committed data layer. Multiwfn `.rad` and `.wfn` interoperability products are planned separately; they are practical export targets, not the state-selection authority for the present data layer.
