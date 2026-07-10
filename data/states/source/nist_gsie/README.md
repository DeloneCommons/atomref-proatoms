# NIST GSIE neutral/cation source table

`nist_neutral_cation_states.csv` is the compact source table used by the current
state builder for neutral atoms and cations. It was prepared from the NIST
[Atomic Spectra Database Ground States and Ionization Energies interface](https://physics.nist.gov/PhysRefData/ASD/ionEnergy.html).

Retained fields are deliberately small and auditable:

```text
z
symbol
charge
electron_count
configuration
ground_level
ground_multiplicity
nist_ie_provenance
```

The table does not redistribute raw NIST HTML/MHTML pages, URLs, bibliography
rows, numerical ionization energies, or numerical uncertainties. The
`nist_ie_provenance` field records only the provenance class inferred from the
NIST ionization-energy syntax: plain numeric values are `evaluated`, bracketed
values are `semiempirical`, and parenthesized values are `theoretical`.

`ground_level` is the retained NIST label used for multiplicity curation.
`ground_multiplicity` was parsed from simple LS-like labels where possible. Seven
current-domain non-LS/jj-style labels were assigned manually and are documented in
`data/states/source/state_source_summary_v2.json` and `data/states/README.md`.
Rows outside the current neutral/cation policy domain may keep blank multiplicities.
