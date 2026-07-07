from __future__ import annotations

import numpy as np
import pytest

from atomref_proatoms.validation.wfn_density import (
    MOSPIN_ALPHA,
    MOSPIN_BETA,
    evaluate_alpha_beta_density,
    evaluate_density,
    evaluate_spin_density,
    parse_wfn_file,
    primitive_type_powers,
)


def _write_minimal_wfn(
    path,
    *,
    primitive_type: int = 1,
    exponents: list[float] | None = None,
    coefficients: list[list[float]] | None = None,
    occupations: list[float] | None = None,
    mospin: list[int] | None = None,
) -> None:
    exponents = [0.0] if exponents is None else exponents
    nprim = len(exponents)
    occupations = [1.0] if occupations is None else occupations
    coefficients = [[1.0] * nprim for _ in occupations] if coefficients is None else coefficients
    lines = [
        "minimal WFN fixture",
        f"GAUSSIAN {len(occupations):14d} MOL ORBITALS {nprim:5d} PRIMITIVES {1:8d} NUCLEI",
        "H    1    (CENTRE  1)   0.00000000  0.00000000  0.00000000  CHARGE =  1.0",
        "CENTRE ASSIGNMENTS  " + "".join(f"{1:3d}" for _ in range(nprim)),
        "TYPE ASSIGNMENTS    " + "".join(f"{primitive_type:3d}" for _ in range(nprim)),
        "EXPONENTS " + "".join(f"{value:14.7E}" for value in exponents),
    ]
    for idx, (occ, coeff) in enumerate(zip(occupations, coefficients, strict=True), start=1):
        # Deliberately skip printed index 2 for the second MO to make the gap auditable.
        printed_idx = idx if idx == 1 else idx + 1
        lines.append(
            f"MO{printed_idx:5d}     MO 0.0        OCC NO = {occ:12.7f}  "
            f"ORB. ENERGY ={-0.5 / idx:12.6f}"
        )
        lines.append("".join(f"{value:16.8E}" for value in coeff))
    lines.extend(
        [
            "END DATA",
            " THE  HF ENERGY =     -0.500000000000 THE VIRIAL(-V/T)=   2.00000000",
        ]
    )
    if mospin is not None:
        lines.extend(["$MOSPIN", "".join(f"{value:2d}" for value in mospin), "$END"])
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def test_wfn_parser_reads_core_records_and_mospin(tmp_path) -> None:
    path = tmp_path / "spin.wfn"
    _write_minimal_wfn(
        path,
        primitive_type=1,
        occupations=[1.0, 0.25],
        coefficients=[[1.0], [0.5]],
        mospin=[MOSPIN_ALPHA, MOSPIN_BETA],
    )

    wfn = parse_wfn_file(path)

    assert wfn.title == "minimal WFN fixture"
    assert wfn.symbols == ["H"]
    assert wfn.centers_bohr.tolist() == [[0.0, 0.0, 0.0]]
    assert wfn.charges.tolist() == [1.0]
    assert wfn.primitive_centers.tolist() == [0]
    assert wfn.primitive_types.tolist() == [1]
    assert wfn.exponents.tolist() == [0.0]
    assert wfn.mo_indices.tolist() == [1, 3]
    assert wfn.occupations.tolist() == [1.0, 0.25]
    assert wfn.coefficients.tolist() == [[1.0], [0.5]]
    assert wfn.spin_types.tolist() == [MOSPIN_ALPHA, MOSPIN_BETA]


def test_density_evaluator_reproduces_simple_known_values(tmp_path) -> None:
    path = tmp_path / "simple.wfn"
    _write_minimal_wfn(path, primitive_type=1, occupations=[0.5], coefficients=[[2.0]])
    wfn = parse_wfn_file(path)

    rho = evaluate_density(wfn, np.array([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]]))

    # exponent=0 and coefficient=2 gives psi=2 everywhere, rho=occ*psi^2=2.
    assert rho.tolist() == pytest.approx([2.0, 2.0])


def test_g_and_h_external_type_labels_follow_multiwfn_convention(tmp_path) -> None:
    g_path = tmp_path / "g.wfn"
    _write_minimal_wfn(g_path, primitive_type=21)
    g_wfn = parse_wfn_file(g_path)

    h_path = tmp_path / "h.wfn"
    _write_minimal_wfn(h_path, primitive_type=56)
    h_wfn = parse_wfn_file(h_path)

    assert primitive_type_powers([21]).tolist() == [[4, 0, 0]]
    assert primitive_type_powers([56]).tolist() == [[5, 0, 0]]
    assert evaluate_density(g_wfn, np.array([[2.0, 0.0, 0.0]]))[0] == pytest.approx(16.0**2)
    assert evaluate_density(g_wfn, np.array([[0.0, 2.0, 0.0]]))[0] == pytest.approx(0.0)
    assert evaluate_density(h_wfn, np.array([[2.0, 0.0, 0.0]]))[0] == pytest.approx(32.0**2)


def test_open_shell_spin_orbital_density_channels_sum_to_total(tmp_path) -> None:
    path = tmp_path / "open_shell.wfn"
    _write_minimal_wfn(
        path,
        primitive_type=1,
        occupations=[1.0, 0.25],
        coefficients=[[1.0], [1.0]],
        mospin=[MOSPIN_ALPHA, MOSPIN_BETA],
    )
    wfn = parse_wfn_file(path)

    points = np.array([[0.0, 0.0, 0.0]])
    alpha, beta = evaluate_alpha_beta_density(wfn, points)
    total = evaluate_density(wfn, points)
    spin = evaluate_spin_density(wfn, points)

    assert alpha[0] == pytest.approx(1.0)
    assert beta[0] == pytest.approx(0.25)
    assert alpha[0] != pytest.approx(beta[0])
    assert total[0] == pytest.approx(alpha[0] + beta[0])
    assert spin[0] == pytest.approx(alpha[0] - beta[0])
