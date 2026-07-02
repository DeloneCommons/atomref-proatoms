# Scientific model

The released v1 objects are spherical radial electron-density profiles for
isolated neutral atoms. For an atom $A$, the tabulated quantity is the total
spin-summed density averaged over directions at fixed radius,

\[
\rho_A(r) = \frac{1}{4\pi} \int \rho_A(r, \Omega)\,d\Omega,
\]

with $r$ in bohr and $\rho_A(r)$ in electrons/bohr³. The intended normalization is

\[
4\pi \int_0^\infty r^2 \rho_A(r)\,dr = N_A,
\]

where $N_A$ is the number of electrons in the neutral atom.

These profiles are reference densities for atom-centered models and descriptors.
They are not experimental atomic radii, spectroscopic term energies, or
molecular-environment-dependent atomic densities. Their value is that every row
is generated with the same declared state, basis, density model, radial grid, and
QA policy.

## Why spherical proatoms require a density model

Closed-shell atoms are spherical in the usual single-determinant picture. Many
open-shell atoms are different. A normal unrestricted atomic SCF calculation can
place electrons into a particular set of magnetic components within a partially
filled `p`, `d`, or `f` shell. The resulting density may be a valid broken-symmetry
SCF solution, but it is not a rotationally invariant proatom.

One common shortcut is to run the ordinary anisotropic atom and angularly average
its final density. This gives a radial profile, but it does not make the SCF
state itself spherical. The Coulomb and exchange-correlation potentials are
nonlinear functionals of the density, so the average of a converged anisotropic
density is not generally the same object as a density obtained from a
self-consistent spherical ensemble. In practical terms, post-averaging can shift
radial density tails and density-cutoff radii for open-shell atoms.

The v1 generator therefore defines the proatom at the SCF level. Sphericalization
is not a plotting operation; it is part of the variational model used to obtain
the density.

## Spherical fractional-occupation UKS construction

The production model is named in `data/profile_datasets.yaml` as
`self_consistent_fractional_occupation_spherical_uks`. It is implemented as a
small PySCF UKS subclass in `src/atomref_proatoms/spherical_uks.py`.

For each spin channel and angular momentum `l`, the curated state table provides
the number of electrons assigned to that angular-momentum shell. During the SCF
cycle, that count is distributed equally over the complete magnetic subspace of
size `2l + 1`. Thus a partially filled shell contributes the same occupation to
each `m` component rather than selecting one orientation in space.

The eigenproblem is also made radial within each angular-momentum block. The AO
basis is required to be pure/spherical. For each `l` block, the Fock and overlap
matrices are reshaped into radial and magnetic components, averaged over matching
magnetic indices, diagonalized as a radial generalized eigenproblem, and then
expanded back over all magnetic components with repeated radial eigenvalues. This
keeps the SCF update consistent with a spherical one-center atom.

The stored profile is the spin-summed density,

\[
\rho(r) = \rho_\alpha(r) + \rho_\beta(r),
\]

not a spin-density profile. Backend spin diagnostics are retained as provenance
where available, but `<S^2>` is not used as a release-gate target for these
fractional-occupation spherical ensembles.

## Current electronic-structure convention

The current project version uses PySCF `2.13.1`. Active v1 wavefunctions are
computed with unrestricted PBE0, spin-free one-electron X2C (`sf-X2C-1e`),
pure/spherical Gaussian basis functions, SCF convergence tolerance `1e-9`, and
PySCF DFT grid level `4`.

Two all-electron scalar-relativistic basis branches are active:

- `x2c-QZVPall` for the H-Rn dataset.
- `dyall-v4z` for the H-Lr dataset.

The basis files are frozen in `data/basis_sets/`; their checksums are part of the
release identity. The state table is frozen in `data/states/curated/`, and the
active neutral-only dataset selection is declared in `data/profile_datasets.yaml`.

Effective-core and valence-only density conventions are not mixed into these v1
profile families. A dataset produced with a different basis, relativistic model,
core convention, charge selection, or occupation policy should receive a separate
dataset identifier.

## Radial profile representation

The released profile tables use a common logarithmic radial grid:

- `r_min = 1e-6 bohr`
- `r_max = 60 bohr`
- `n = 1200`

A logarithmic grid is used because atomic densities span many orders of magnitude
between the near-nuclear region and the low-density tail. This grid is a compact
release representation suitable for interpolation and plotting. It is not the
sole numerical quadrature used for QA.

For each radius, the generator evaluates the angular mean density and an angular
standard-deviation diagnostic. A correctly spherical generated profile should
show negligible angular variation except in the far tail, where relative
quantities can be dominated by extremely small densities.

## Density-cutoff radii

The radii tables are derived from the profile tables. A cutoff radius is the
outermost interpolated crossing of

\[
\rho_A(r) = \rho_{\mathrm{cut}}.
\]

The v1 density cutoffs are:

- `0.003 electrons/bohr^3`
- `0.001 electrons/bohr^3`
- `0.0001 electrons/bohr^3`

The `0.003` and `0.001` radii are the primary practical size descriptors. The
`0.0001` radius is mainly a low-density tail and interpolation diagnostic.
Because tail densities are approximately exponential on a radial scale, the
radius lookup uses interpolation in `log(rho)` when the neighboring density
values are positive.

## Independent electron-count QA

Electron-count QA is intentionally performed on an independent grid rather than
by trusting the stored profile mesh. The release QA integrates the angularly
averaged density with Gauss-Legendre quadrature in $t = \log(r)$:

\[
N = \int 4\pi r(t)^3 \rho(r(t))\,dt, \qquad r(t) = \exp(t).
\]

The active QA grid uses:

- `r_min = 1e-7 bohr`
- `r_max = 120 bohr`
- `n_radial = 400`
- `n_angular = 110`

A state passes the numerical release gate only when the SCF artifact is complete,
the independent electron count is within tolerance, angular variation is within
tolerance, the density tail reaches the smallest stored cutoff, and the derived
cutoff radii are consistent.

The detailed QA columns are described in `data/qa/README.md`, and the generated
release report is `data/qa/qa_report.md`.

## Relation to the notebooks

The notebooks in `docs/notebooks/` are the practical companion to this page. The
artifact-inspection notebook reads the released profile/radius/QA tables. A method
notebook can additionally run a small atom to compare ordinary UKS plus post-SCF
angular averaging with the spherical fractional-occupation model described here.
