# Ning--Lu 2022 monoanion source table

`ning2022_monoanions.csv` is the compact v2 monoanion source/status layer curated
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
numerics. Rows accepted as physical/provisional monoanion references can enter
the active v2 compute table. Theory-only, unbound, metastable-only, or otherwise
problematic rows remain visible here for auditing but are not silently upgraded
to physical reference states.
