from __future__ import annotations

from pathlib import Path

import pytest

from atomref_proatoms.basis import (
    EXPECTED_BASIS_IDS,
    EXPECTED_NWCHEM_SPHERICAL_HEADER,
    basis_covers_z,
    list_basis_bundles,
    load_basis_nw_text,
    parse_covered_z,
    validate_all_basis_bundles,
    verify_basis_source_metadata,
    verify_basis_source_url_shape,
)
from atomref_proatoms.datasets import BASIS_TO_DATASETS

ROOT = Path(__file__).resolve().parents[2]
BASIS_ROOT = ROOT / "data" / "basis_sets"


def test_expected_basis_bundles_exist_and_only_expected_dirs() -> None:
    actual = sorted(path.name for path in BASIS_ROOT.iterdir() if path.is_dir())
    assert actual == sorted(EXPECTED_BASIS_IDS)


def test_basis_bundles_validate_offline() -> None:
    assert validate_all_basis_bundles(BASIS_ROOT) == []


def test_no_manifest_csv_or_mhtml_files() -> None:
    assert list(BASIS_ROOT.rglob("manifest.csv")) == []
    assert list(BASIS_ROOT.rglob("*.mhtml")) == []


def test_source_objects_are_required_and_consistent() -> None:
    for bundle in list_basis_bundles(BASIS_ROOT):
        verify_basis_source_metadata(bundle.summary_row, bundle.manifest)
        verify_basis_source_url_shape(bundle.manifest["source"]["source_api_url"])
        assert bundle.manifest["source"] == bundle.summary_row["source"]


def test_basis_nw_identity_header_and_coverage() -> None:
    for bundle in list_basis_bundles(BASIS_ROOT):
        text = load_basis_nw_text(bundle)
        assert EXPECTED_NWCHEM_SPHERICAL_HEADER in text
        assert text.rstrip().endswith("END")
        assert len(parse_covered_z(text)) == bundle.manifest["coverage"]["n_elements"]
        for start, end in bundle.manifest["coverage"]["z_coverage_intervals"]:
            assert basis_covers_z(bundle, start)
            assert basis_covers_z(bundle, end)


def test_expected_dataset_ids_are_declared_in_manifest_usage() -> None:
    for bundle in list_basis_bundles(BASIS_ROOT):
        expected = set(BASIS_TO_DATASETS[bundle.basis_id])
        actual = set(bundle.manifest["usage"]["dataset_ids_using_this_basis"])
        assert expected <= actual


@pytest.mark.parametrize(
    "url",
    ["https://example.com/api/basis/x/format/nwchem/?version=1&elements=1"],
)
def test_basis_source_url_shape_rejects_non_bse_hosts(url: str) -> None:
    with pytest.raises(ValueError):
        verify_basis_source_url_shape(url)
