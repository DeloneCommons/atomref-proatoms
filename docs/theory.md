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

not a spin-density profile. Spin diagnostics may be retained as provenance, but \(\langle S^2\rangle\) is not used as a validation target for fractional-occupation spherical ensembles.

## Electronic-structure convention

The current profiles use PBE0, spin-free one-electron X2C, unrestricted Kohn--Sham SCF, PySCF `2.13.1`, pure/spherical Gaussian basis functions, SCF convergence tolerance \(10^{-9}\), PySCF DFT grid level `4`, `max_cycle = 300`, `diis_space = 12`, and `diis_start_cycle = 1`.

The all-electron convention is part of the profile identity. Effective-core or valence-only densities should not be mixed silently with these branches. A different basis, relativistic treatment, core convention, state policy, or density model should receive a separate dataset identifier.

## Radial grid and cutoff radii

The released profile tables use a 1200-point logarithmic grid from \(10^{-6}\) to 60 bohr. This grid resolves both near-nuclear density and low-density tails compactly. It is the release representation, not the only quadrature used for validation.

A density-cutoff radius is the outermost interpolated radius satisfying

\[
\rho_A(R_\rho)=\rho_\mathrm{cut}.
\]

The current cutoffs are \(0.003\), \(0.001\), and \(0.0001\) electrons/bohr\(^3\). The first two are practical size descriptors. The smallest cutoff is retained mainly as a tail/interpolation diagnostic because it is more sensitive to diffuse basis functions and formal anion behavior.

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
