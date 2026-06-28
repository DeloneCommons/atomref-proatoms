from __future__ import annotations

import json
import math
import zipfile

from atomref_proatoms.artifacts import (
    write_json,
    write_profile_csv_zip,
    write_state_profile_artifacts,
)


def test_write_profile_csv_zip_contains_one_csv(tmp_path) -> None:
    path = tmp_path / "H_q0_mult2_hund.csv.zip"
    write_profile_csv_zip(path, rows=[(0.1, 2.0), (0.2, 1.0)])

    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == ["H_q0_mult2_hund.csv"]
        payload = archive.read("H_q0_mult2_hund.csv").decode("utf-8")

    assert payload.splitlines() == [
        "r_bohr,rho_e_bohr3",
        "0.10000000000000001,2",
        "0.20000000000000001,1",
    ]


def test_write_json_replaces_nonfinite_numbers_with_null(tmp_path) -> None:
    path = tmp_path / "metadata.json"
    write_json(path, {"finite": 1.0, "nan": math.nan, "inf": math.inf})

    text = path.read_text()
    assert "NaN" not in text
    assert "Infinity" not in text
    assert json.loads(text) == {"finite": 1.0, "nan": None, "inf": None}


def test_write_state_profile_artifacts_defaults_to_zip(tmp_path) -> None:
    profile_path, metadata_path = write_state_profile_artifacts(
        tmp_path,
        state_id="H_q0_mult2_hund",
        profile={"r_bohr": [0.1, 0.2], "rho_e_bohr3": [2.0, 1.0]},
        metadata={"qa": {"electron_count_error_qa": None}},
    )

    assert profile_path.name == "H_q0_mult2_hund.csv.zip"
    assert metadata_path.name == "H_q0_mult2_hund.json"
    assert json.loads(metadata_path.read_text()) == {"qa": {"electron_count_error_qa": None}}
