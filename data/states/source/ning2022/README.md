# Ning--Lu 2022 monoanion source table

`ning2022_monoanions.csv` is the compact monoanion source/status layer curated
from Ning and Lu, *Electron Affinities of Atoms and Structures of Atomic Negative
Ions*, J. Phys. Chem. Ref. Data 51, 021502 (2022).

Retained fields are:

```text
z
symbol
charge
electron_count
configuration
ground_level
ground_multiplicity
state_role
physical_status
notes
```

The table intentionally omits electron-affinity values and uncertainties because
the current state layer needs state labels and status flags, not affinity
numerics. Rows accepted as physical/provisional monoanion references can enter the current
compute table. In addition, the source-backed Fr-U rows enter the primary
dyall-v4z H-Lr dataset with their original physical/provisional/theory-only
status retained. Other theory-only, unbound, metastable-only, or otherwise
problematic rows remain visible here for auditing but are not silently promoted
to physical reference states.
