# atomref-proatoms data-layer notes

This archive contains the compact atomic-configuration/state-data slice and the
frozen basis-set data slice of the future `DeloneCommons/atomref-proatoms`
repository.

Atomic-state decisions:

- Keep raw NIST HTML snapshots out of the public repo.
- Keep the NIST-derived source table minimal: `z`, `symbol`, `charge`,
  `electron_count`, `configuration`.
- Do not redistribute ionization energies, uncertainties, NIST bibliography rows,
  or raw ASD tables in this state-data layer.
- Keep formal multi-charged anions in a separate table and mark them as
  `formal_crystal_ion_reference`.
- Use `data/states/selection/required_states_v0.csv` as the versioned state
  selection file. It is not a complete spin-state configuration file.
- Generate complete generator-ready records with `scripts/build_atom_states.py`.
- The recommended spin convention for v0 is `free_ion_hund_high_spin`.
- Do not mix future low-spin/sensitivity variants into the recommended v0 state
  list. Add a separate selection file and mark those states as diagnostic or
  spin-sensitivity records.
- JSON is the only curated output for now; JSONL was intentionally removed.

Basis-set decisions:

- Store production basis data as frozen project files under `data/basis_sets/`.
- Do not silently download basis sets during production density generation.
- Use BSE NWChem-format text exports as `basis.nw` without reformatting.
- Do not preserve `.mhtml` acquisition snapshots in the public data layer.
- Use `manifest.json` as the canonical basis metadata file; no one-row
  `manifest.csv` files are used.
- Hash only the production basis file (`basis.nw`) for basis-data identity.
- Keep the BSE BSD-3-Clause notice in `data/basis_sets/`.
- Treat diffuse and non-diffuse basis outputs as separate datasets; never merge
  them silently.
- Every future density profile must record both `dataset_id` and `basis_id`.

Questions to revisit during repository initialization:

- Whether `data/states/selection/` should later be moved to a package-level config
  directory. For now it stays under `data/states/` because it is tightly coupled
  to the source tables and generated curated states.
- Whether to add optional spin-sensitivity selections for selected d-shell ions
  after the recommended v0 density build is stable.
