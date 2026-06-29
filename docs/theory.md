# Theory notes

This file is a placeholder for the scientific description of the production density model:
self-consistent spherical fractional-occupation UKS with PBE0, spin-free one-electron X2C,
and pure/spherical Gaussian basis functions.

Ordinary UKS followed by post-hoc angular averaging is diagnostic only and is not a
production density family.


## Stored radial grid

The released profiles use a logarithmic radial grid from the near-nuclear region through
the low-density tail. This is intentional: proatomic densities vary over many orders of
magnitude, and cutoff-radius lookup is performed by interpolation rather than by treating
the stored rows as a fixed linear sampling mesh. In the chemically relevant tail region,
log-density interpolation is the expected downstream use. A linear 0.01 Å table can be
created later as a derived export if a consumer needs direct tabulation on that mesh, but
it should not replace the compact canonical log-grid profile.
