# Theory

## Spherical radial density

For an atom or ion \(A\), the released scalar field is the spin-summed spherical radial density

\[
\rho_A(r) = \frac{1}{4\pi}\int \rho_A(r,\Omega)\,d\Omega,
\]

with \(r\) in bohr and \(\rho_A(r)\) in electrons/bohr\(^3\). Its electron-count normalization is

\[
N_A = 4\pi\int_0^\infty r^2\rho_A(r)\,dr.
\]

The radial distribution

\[
D_A(r) = 4\pi r^2\rho_A(r)
\]

has units of electrons/bohr and integrates directly to the number of electrons. This quantity is often more useful than \(\rho(r)\) when comparing two profiles because it shows where electrons are radially redistributed rather than where the point density is largest.

The cumulative electron count is

\[
N_A(<r) = \int_0^r D_A(s)\,ds.
\]

It is used both as an electron-count diagnostic and as a physically interpretable way to compare radial profiles. If two matched profiles have essentially identical total electron count but different tails, \(N(<r)\) shows how much charge has shifted inward or outward at each radius.

## Self-consistent spherical fractional occupations

The production density model is `self_consistent_fractional_occupation_spherical_uks`. For each spin channel and angular momentum \(l\), the curated state record gives the number of electrons assigned to that angular-momentum shell. During the SCF cycle, that occupation is distributed equally over the full magnetic subspace of size \(2l+1\). A partially filled shell therefore contributes equally to every \(m\) component rather than selecting an orientation in space.

The Fock and overlap matrices are also treated as one-center angular-momentum blocks. Within each \(l\) block, the matrices are averaged over matching magnetic components and diagonalized as a radial generalized eigenproblem. The resulting radial eigenvectors are expanded back over the full magnetic manifold with repeated eigenvalues. This preserves the spherical density convention throughout the SCF update.

The stored density is

\[
\rho(r)=\rho_\alpha(r)+\rho_\beta(r),
\]

not a spin-density profile. A determinant-based \(\langle S^2\rangle\) is not
defined by the one-particle density matrix of a fractional-occupation spherical
ensemble. The spherical SCF backends therefore suppress PySCF's standard UHF
`spin_square` value and report the alpha/beta electron populations and nominal
multiplicity implied by their difference instead.

## Density-cutoff radii as level-surface descriptors

A density-cutoff radius is the outermost radius satisfying

\[
\rho_A(R_\rho)=\rho_\mathrm{cut}.
\]

For a general molecular density, an isodensity value defines a surface. For a spherical proatom, that surface collapses to a single radial descriptor. This makes density-cutoff radii useful for comparing atomic reference gauges: they translate changes in low-density tails into length shifts without pretending to be empirical covalent, ionic, or van der Waals radii.

The chemically robust cutoffs are those that describe the outer valence region without relying too strongly on the far asymptotic tail. Much lower cutoffs are still useful as diagnostics, especially for supplemented or augmented bases and for formal anion references. The specific cutoff values, interpolation rule, release grid, and independent QA quadrature are implementation choices described in Methods.

## Reference-gauge interpretation

For a molecular density \(\rho_\mathrm{mol}\), a deformation density relative to spherical proatoms can be written as

\[
\Delta\rho = \rho_\mathrm{mol} - \sum_A \rho_{A,\mathrm{ref}}.
\]

Changing from reference set 1 to reference set 2 changes the deformation density by

\[
\Delta\rho_1-\Delta\rho_2 = \sum_A\left(\rho_{A,2}-\rho_{A,1}\right).
\]

This difference is a sum of atom-centered spherical functions. Consequently, changes in the proatom gauge primarily affect radial shells, density tails, and integrated atom-centered quantities. Directional interatomic features are usually more robust than absolute charge-transfer magnitudes or subtle tail-sensitive conclusions.
