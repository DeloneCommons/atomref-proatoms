# Scientific model for v1 profiles

The v1 data products are spherical radial electron-density profiles for isolated
neutral atoms. For an atom `A`, the stored function is

```text
rho_A(r) = angular average of total electron density at distance r
```

with `r` in bohr and `rho_A(r)` in electron/bohr³. The intended normalization is

```text
4 pi integral_0^infty r^2 rho_A(r) dr = N_A
```

where `N_A` is the number of electrons in the neutral atom. The profiles are
reference densities for atom-centered models and descriptors; they are not
high-precision atomic spectroscopy records.

## Production density model

The production density model is declared in `data/profile_datasets.yaml` as

```text
self_consistent_fractional_occupation_spherical_uks
```

The current v1 settings are:

```text
engine: PySCF 2.13.1
SCF type: UKS
exchange-correlation functional: PBE0
relativity: spin-free one-electron X2C (sf-X2C-1e)
basis representation: pure/spherical Gaussian basis functions
SCF convergence tolerance: 1e-9
DFT grid level: 4
```

The two active basis branches are:

```text
x2c-QZVPall  H-Rn neutral atoms
dyall-v4z    H-Lr neutral atoms
```

Both active branches are treated as all-electron scalar-relativistic reference
densities. Effective-core or valence-only density conventions are not mixed with
these v1 datasets.

## Atomic states and spherical occupations

The atomic state table provides the element, charge, electron count, reference
configuration, multiplicity, and spin-resolved angular-momentum occupations. For
v1 profile datasets, `data/profile_datasets.yaml` selects neutral recommended
states only.

Open-shell free atoms have direction-dependent densities if one occupies a
specific set of magnetic components. The v1 production model avoids this by using
self-consistent spherical fractional occupations. For each spin channel and
angular momentum `l`, the total occupation assigned to that angular-momentum shell
is distributed equally over the complete magnetic subspace with degeneracy
`2l + 1`.

The important distinction is that sphericalization is part of the SCF model. The
production density is not obtained by first computing an anisotropic atom and then
averaging it as a post-processing step. Instead, the SCF occupation rule itself is
spherical, so the self-consistent density is the target proatomic density.

The stored radial density is the total electron density,

```text
rho(r) = rho_alpha(r) + rho_beta(r)
```

and not a spin-density profile. Spin diagnostics from the backend are retained in
QA/provenance where available, but backend `<S^2>` is not a pass/fail target for
fractional-occupation spherical proatoms.

## Radial profile grid

Released profile CSV files use a compact logarithmic radial grid:

```text
r_min = 1e-6 bohr
r_max = 60 bohr
n = 1200
```

A logarithmic grid is used because atomic electron densities vary over many
orders of magnitude between the near-nuclear region and the low-density tail. The
stored grid is a canonical data representation, not a recommendation that every
downstream consumer must work on the same mesh.

For each radius, the generator evaluates the angular mean density and an angular
standard-deviation diagnostic. In a correctly spherical profile, the angular
standard deviation should be negligible relative to the density except in the
far-tail region where the denominator is extremely small.

## Density-cutoff radii

The radius tables are derived from the generated radial profiles. A cutoff radius
is the outermost interpolated crossing of

```text
rho_A(r) = rho_cut
```

for a chosen density cutoff. The v1 cutoffs are:

```text
0.003  electron/bohr^3
0.001  electron/bohr^3
0.0001 electron/bohr^3
```

The `0.003` and `0.001` electron/bohr³ radii are the primary practical density
cutoff radii. The `0.0001` electron/bohr³ radius is retained as a low-density tail
and interpolation diagnostic.

Because tail densities are close to exponential on a radial scale, radius lookup
uses interpolation in `log(rho)` when both neighboring density values are
positive. The radii table stores values in both bohr and ångström.

## Independent QA integration

The stored profile grid is not used as the only electron-count check. Release QA
uses an independent logarithmic Gauss-Legendre radial quadrature:

```text
r_min = 1e-7 bohr
r_max = 120 bohr
n_radial = 400
n_angular = 110
```

Electron count is evaluated from the angularly averaged density as

```text
sum_i w_i 4 pi r_i^3 rho(r_i)
```

where the quadrature is performed in `t = log(r)`. This independent grid extends
beyond the stored profile range to make the electron-count and tail checks less
dependent on the released tabulation mesh.

A generated state passes the standard numerical gate only if the SCF converged,
the independent electron count is within tolerance, the angular-symmetry
criterion is satisfied, the density tail reaches the minimum stored cutoff, and
the derived radii are monotonic with decreasing cutoff.

## Scope and limitations

The v1 profiles are designed as reproducible reference densities with declared
state, basis, method, grid, and QA conventions. They should be used as named data
products rather than as anonymous atomic radii or generic atom-wavefunction files.

The v1 data products do not attempt to provide:

- experimental atomic radii;
- spectroscopic term energies;
- molecular-environment-dependent atomic densities;
- basis-matched atomic wavefunction files for arbitrary external workflows;
- charged-state profile datasets.

Applications that require a different electronic-structure convention should keep
the resulting data under a separate dataset identifier rather than silently mixing
it with the v1 profile families.
