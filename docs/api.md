# Python API

`atomref-proatoms` exposes a compact scripting API directly from the package:

```python
from atomref_proatoms import AtomState, interpolate_density, select_packaged_states
```

The names documented on this page are the supported package-level API and are
listed explicitly in `atomref_proatoms.__all__`. More specialized release,
validation, schema, and workspace helpers remain available from their canonical
subpackages, but they are not part of this concise facade.

Importing `atomref_proatoms` requires only the base dependencies and does not
import PySCF. Functions operating on PySCF molecules or mean-field objects need
the `generator` extra when they are called:

```bash
python -m pip install "atomref-proatoms[generator]"
```

## State selection and input checks

The state objects retain the complete source record while exposing the fields
most often used by scripts as properties.

| Object | Purpose |
|---|---|
| `AtomState(record)` | Generator-ready atomic state with properties such as `state_id`, `symbol`, `charge`, `electron_count`, `spin_2s`, `multiplicity`, and alpha/beta angular-momentum counts. |
| `StateSelection` | Result of a packaged-state selection; its `states`, `state_ids`, `warnings`, and `summary()` members are useful in scripts. |
| `BasisSpec` | Normalized PySCF, Basis Set Exchange, or local-file basis request returned by `parse_basis_spec`. |
| `BasisCheckResult` | Basis coverage and all-electron/ECP check result; use `as_dict()` for manifests. |
| `MethodSpec` | Normalized HF or DFT method request returned by `parse_method`. |
| `RelativitySpec` | Normalized `none` or spin-free one-electron X2C request. |
| `MethodCheck` | Optional PySCF method-validation result; use `as_dict()` for manifests. |

```python
validate_atom_state(record: dict) -> list[str]

select_packaged_states(
    *,
    elements: tuple[str, ...] | list[str],
    policy: str = "neutral",
    charges: tuple[int, ...] | list[int] | None = None,
    resource_root: Path | str | None = None,
) -> StateSelection

parse_basis_spec(
    *,
    basis: str | None = None,
    basis_file: str | Path | None = None,
    basis_name: str | None = None,
) -> BasisSpec

check_basis_source(
    spec: BasisSpec,
    symbols: tuple[str, ...] | list[str],
) -> BasisCheckResult

parse_method(method: str) -> MethodSpec
parse_relativity(relativity: str) -> RelativitySpec
check_method_with_pyscf(spec: MethodSpec) -> MethodCheck
```

`select_packaged_states` supports the same curated `neutral` and `stockholder`
policies as the CLI. Construct an `AtomState` directly only when a custom state
is intentional, visible in the script, and has first passed
`validate_atom_state`.

`check_basis_source` needs PySCF for `pyscf:` sources and Basis Set Exchange for
`bse:` sources. Local NWChem-format file checks are lightweight. A missing PySCF
installation is reported by `check_method_with_pyscf` rather than imported at
package-import time.

## Spherical SCF

These functions form the low-level custom-state path demonstrated in the expert
notebook. Except for simple configuration of an existing object, they operate on
PySCF objects and therefore require the `generator` extra at call time.

```python
validate_spherical_ao_layout(mol) -> None

make_spherical_uks(
    mol,
    *,
    xc: str = "PBE0",
    alpha_l_counts: Mapping[int | str, float] | None = None,
    beta_l_counts: Mapping[int | str, float] | None = None,
)

make_spherical_uhf(
    mol,
    *,
    alpha_l_counts: Mapping[int | str, float] | None = None,
    beta_l_counts: Mapping[int | str, float] | None = None,
)

configure_dft_grid(mf, *, level: int = 4, prune=None)
apply_x2c_if_requested(mf, *, use_x2c: bool)
write_scf_npz(path: Path, mf) -> None
```

The `alpha_l_counts` and `beta_l_counts` mappings describe total occupation in
each angular-momentum block, using `0`, `1`, `2`, and `3` for s, p, d, and f.
`make_spherical_uks` and `make_spherical_uhf` distribute those occupations over
complete angular manifolds during SCF.

## Radial profiles

All radii in this API are in bohr and all densities are in electron/bohr³.

```python
log_radial_grid(r_min: float, r_max: float, n_points: int) -> ndarray

density_profile_from_mf(
    mf,
    *,
    r_grid=None,
    n_ang: int = 110,
    dm_total=None,
    compute_qa: bool = True,
    qa_r_min: float = 1e-7,
    qa_r_max: float = 120.0,
    qa_n_r: int = 400,
    qa_n_ang: int = 110,
    prefer_pyscf_angular_grid: bool = True,
) -> dict

load_profile_csv(
    path: Path | str,
    *,
    density_column: str | None = None,
) -> tuple[ndarray, ndarray]

interpolate_density(
    r_bohr,
    rho_e_bohr3,
    r_query_bohr,
    *,
    mode: str = "loglog",
    fill_value: float = 0.0,
) -> ndarray

radius_at_density(r_bohr, rho_e_bohr3, cutoff: float) -> float
derived_radii(r_bohr, rho_e_bohr3, cutoffs=(0.003, 0.001, 0.0001)) -> dict[str, float]

write_wide_profiles_csv(
    path: Path,
    *,
    r_bohr,
    densities_by_state_id,
) -> None
```

`load_profile_csv` requires `density_column` when a released wide profile table
contains more than one `rho_e_bohr3__<state_id>` column. The default
`interpolate_density` mode interpolates positive densities in log-log space and
falls back to linear interpolation if the supplied density contains a zero or
negative value.

## Multiwfn interoperability

The `.rad` and `.wfn` helpers write secondary interoperability products. Radial
profiles and project-native SCF arrays remain the preferred structured data
paths.

```python
multiwfn_rad_filename(symbol: str, charge: int) -> str
atom_wfn_filename(symbol: str) -> str

evaluate_scf_radial_density(
    mol,
    dm_total,
    *,
    r_bohr=MULTIWFN_ATMRAD_GRID_BOHR,
    n_ang: int = 1,
    coord_block_size: int = 8192,
    prefer_pyscf_angular_grid: bool = True,
) -> tuple[ndarray, ndarray]

write_multiwfn_rad_file(
    path: Path | str,
    r_bohr,
    rho_e_bohr3,
) -> dict

write_atomref_spherical_wfn(
    path: Path | str,
    state,
    scf_run_or_mf,
    *,
    title: str | None = None,
    occ_tol: float = 1e-10,
    keep_beta_index_gap: bool = True,
) -> dict
```

`evaluate_scf_radial_density` evaluates the SCF density directly; it does not
construct release `.rad` files by interpolating a committed profile table.

## Minimal packaged-state example

```python
from atomref_proatoms import select_packaged_states

selection = select_packaged_states(
    elements=["C", "Ni"],
    policy="stockholder",
    charges=[-1, 0, 1],
)

for state in selection.states:
    print(state.state_id, state.charge, state.multiplicity)
```

See [Python scripting for custom states](generator/scripting.md) and the expert
custom-state notebook for a complete optional SCF pipeline.
