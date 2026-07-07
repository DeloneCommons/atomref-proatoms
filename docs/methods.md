# Methods

## State curation

The state layer is a curated proatomic reference-state table, not a complete atomic spectroscopy database. Each generated state has a deterministic `state_id`, element, charge, electron count, multiplicity, configuration label, state role, source category, occupation policy, and state-record digest.

Neutral atoms and cations are prepared from compact source tables derived from the [NIST Atomic Spectra Database Ground States and Ionization Energies interface](https://physics.nist.gov/PhysRefData/ASD/ionEnergy.html). The generated state layer stores the information needed for reproducibility but does not redistribute raw NIST pages, numerical ionization energies, uncertainty tables, or bibliographic rows.

Monoanions are curated separately because anion evidence is not captured by a simple NIST-only rule. Accepted or provisional monoanions are drawn from a compact status layer derived from the Ning--Lu review ([Ning and Lu, 2022](https://doi.org/10.1063/5.0080243)) and project curation. Rows whose evidence is theory-only, excluded, unbound, metastable-only, or otherwise problematic are not silently promoted to production physical anions. Formal monoanions and formal multianions are explicitly labeled as reference-density rows.

The state roles used in the generated layer are:

- `reference` and `reference_uncertain` for neutral/cation references;
- `bound_experimental` and `bound_provisional` for source-backed monoanions;
- `diagnostic_theory` for source-backed theory-only monoanion diagnostics included in the current H--Lr primary branch;
- `formal_monoanion` and `formal_multianion` for deliberately formal reference rows.

## Basis-set branches

The fixed basis universe is:

| basis | branch role | current generated scope |
|---|---|---|
| `x2c-QZVPall` | primary x2c branch | H--Rn, all curated states in basis coverage |
| `dyall-v4z` | primary Dyall branch | H--Lr, all curated states |
| `x2c-QZVPall-s` | supplemented x2c branch | H--Rn neutral and anion states, cations excluded |
| `dyall-av4z` | augmented Dyall branch | H--Ba and Hf--Ra neutral and anion states where covered, cations excluded |

The primary branches define the default reference gauges. The supplemented/augmented branches are basis-distinct data products used to quantify tail sensitivity and to provide explicitly selected alternative gauges for tail-sensitive analyses. They are not split into separate neutral and anion dataset IDs because the basis branch, not the charge class, is the data identity.

The `x2c-QZVPall-s` branch needs a specific caveat. Its Basis Set Exchange header describes it as an all-electron relativistic polarized quadruple-zeta basis for one-component NMR shielding, from the same Karlsruhe x2c basis-set work as `x2c-QZVPall` ([Franzke et al., 2020](https://doi.org/10.1021/acs.jctc.0c00546)). It is retained here as a supplemented comparison branch, not as a conventional diffuse tail-optimized basis. The `dyall-av4z` branch is the actual augmented Dyall branch, with discontinuous element coverage inherited from the available basis bundle.

## Electronic-structure convention

All current profiles use PBE0 ([Adamo and Barone, 1999](https://doi.org/10.1063/1.478522)), spin-free one-electron X2C, unrestricted Kohn--Sham SCF, PySCF `2.13.1`, and pure/spherical Gaussian basis functions. The all-electron convention is part of the profile identity: effective-core or valence-only densities should not be mixed silently with these data. A different basis, relativistic treatment, core convention, state policy, or density model should receive a separate dataset identifier.

## SCF generation

For each selected state and basis branch, the generator runs a one-center self-consistent spherical fractional-occupation UKS calculation under this electronic-structure convention. The SCF defaults are deliberately conservative:

```text
conv_tol = 1.0e-9
max_cycle = 300
diis_space = 12
diis_start_cycle = 1
grid_level = 4
```

The increased cycle count and DIIS settings are applied uniformly so that difficult augmented-basis or highly anionic cases are not handled by undocumented local exceptions. The generated metadata record the engine, expected engine version, basis checksum, SCF settings, state digest, and local SCF artifact paths.

## Profile extraction

Profile extraction reads local SCF artifacts and evaluates the angular mean density on the release radial grid. Each profile CSV is a wide table with one `r_bohr` column and one density column per state:

```text
rho_e_bohr3__<state_id>
```

The associated metadata records the profile-data version, basis identity, grid, method, density cutoffs, state list, column map, checksums, and related radii/QA paths. Profile extraction also writes radii and QA tables for the same dataset so that profile, radius, and validation rows remain synchronized.

## Radial grids and density-cutoff radii

The released profile tables use a 1200-point logarithmic grid from \(10^{-6}\) to 60 bohr. This grid resolves both near-nuclear density and low-density tails compactly; it is the release representation, not the only quadrature used for validation.

For each profile, the radii layer computes the outermost interpolated crossing of the density cutoffs \(0.003\), \(0.001\), and \(0.0001\) electrons/bohr\(^3\). Interpolation uses the logarithm of density when both neighboring values are positive. The radii are reported in bohr and ångström.

The cutoff radii are not experimental atomic radii. They are reproducible density-level descriptors of the selected spherical reference gauge. The two higher cutoffs are practical outer-size descriptors; the \(0.0001\) electrons/bohr\(^3\) cutoff is intentionally retained as a far-tail and interpolation diagnostic.

## Validation criteria

The validation layer combines hard consistency checks and softer scientific diagnostics. A generated row must have a complete SCF artifact, finite density values, valid grid metadata, a density tail reaching the declared cutoff range, consistent cutoff radii, and an independent electron-count integration within tolerance. Angular sphericity is checked by evaluating the density over a Lebedev angular grid at multiple radii. Linear-dependency and dropped-primitive information is retained as a diagnostic and is not by itself a failure when the numerical density passes the release criteria.

The independent electron-count check integrates on a separate logarithmic Gauss--Legendre radial grid, not by trusting the release profile mesh. This makes the profile grid a data representation while the QA grid remains an independent numerical audit.

## WFN and Multiwfn interoperability validation

A local H/O/H2O validation was used to test the PROAIM WFN interoperability path. The test writes atom and molecule WFN files from the same PySCF and atomref density objects used to define the reference, reads the saved files back with an independent package-side WFN evaluator, and compares Multiwfn plane densities against the corresponding PySCF total-density and deformation-density references.

The atom WFN convention is deliberately spin-orbital based for open-shell cases: alpha orbitals are written first, beta orbitals second, each occupation is at most one, and the file contains an explicit `$MOSPIN` block with labels `1` and `2`. A printed MO-index gap is retained at the beta block as a fallback cue for Multiwfn-like readers, but the explicit spin block is the primary convention. The exporter does not use `$MOSPIN=3` spatial-orbital reconstruction for fractional/open-shell atom references.

The independent WFN evaluator parses the PROAIM centers, primitive center assignments, primitive type assignments, exponents, occupations, orbital energies, coefficients, and `$MOSPIN` records. Its Cartesian primitive type handling follows the Multiwfn convention for WFN inputs, including the external g-type WFN sequence and h-type primitive labels. This evaluator is a validation and documentation utility; it is not the preferred public data path.

The Multiwfn portion is automated only through small local helpers that find an executable under `local-data/`, run `-silent`, add `-set local-data/settings.ini` when available, and parse exported plane files or point-output logs. Multiwfn remains an optional local interoperability context, not a package dependency and not a state-selection authority.

## Supplemented/augmented basis sensitivity

Basis sensitivity compares exact matched states between a primary basis and its supplemented or augmented counterpart:

```text
dyall-v4z     → dyall-av4z
x2c-QZVPall   → x2c-QZVPall-s
```

State matching requires both the same `state_id` and the same state-record digest. A mismatch is an integrity problem because it would compare different physical/reference states rather than different basis representations of the same state.

For a base profile \(A\) and a supplemented/augmented profile \(B\), the reported signed cumulative difference is

\[
\Delta N_{A\to B}(r)=N_B(<r)-N_A(<r).
\]

The comparison reports the sup norm \(\max_r |\Delta N(r)|\), the radius where this maximum occurs, the integrated absolute cumulative difference \(\int |\Delta N(r)|dr\), tail-electron differences beyond fixed radii, density-cutoff radius shifts, and radial-distribution L1 metrics. The signed density-cutoff shift is

\[
\Delta R_\rho = R_\rho(B)-R_\rho(A).
\]

The relative radial-distribution L1 difference is

\[
\frac{\int |D_B(r)-D_A(r)|\,dr}{N},
\]

where \(N\) is the matched electron count. This normalization makes rows with different electron counts easier to compare. Large values for formal anions are interpreted as scientific sensitivity flags unless they coincide with electron-count, state-digest, convergence, or finite-density failures.

## Primary basis-family comparison

The primary comparison uses the same matched-state and state-digest contract but asks a different question. It compares `x2c-QZVPall` and `dyall-v4z` over their H--Rn overlap. This is a comparison of two primary all-electron scalar-relativistic basis families, not a diffuse-basis sensitivity test.

The current artifact is stored under:

```text
data/qa/basis_comparisons/x2c-QZVPall__dyall-v4z/
```

Signed deltas are reported as `dyall-v4z` minus `x2c-QZVPall`. The main scientific metrics are radial-distribution L1, relative L1, cumulative electron-count differences, integrated absolute cumulative differences, density-cutoff radius shifts, tail-electron shifts, and moments such as \(\langle r\rangle\), \(\langle r^2\rangle\), and RMS radius. Pointwise maximum density difference is retained only as a diagnostic because near-nuclear point-density differences can be large without implying a large radial redistribution of electrons.

## Documentation-derived outputs

The Results page includes reusable generated Markdown tables in `docs/tables/` and compact SVG figures in `docs/figures/`. They are regenerated from committed artifacts by:

```bash
python scripts/prepare_docs.py --write
```

and checked by:

```bash
python scripts/prepare_docs.py --check
```

This script does not generate SCF artifacts, profile tables, radii, QA data, or comparison CSVs. It only keeps the documentation tables and figures synchronized with those committed data products.
