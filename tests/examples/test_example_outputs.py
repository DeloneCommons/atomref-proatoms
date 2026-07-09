from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = ROOT / "examples"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _example_output_roots() -> list[Path]:
    return sorted(path.parent for path in EXAMPLES_ROOT.glob("0*/output/manifest.json"))


def test_committed_generator_example_manifests_reference_existing_files() -> None:
    output_roots = _example_output_roots()
    assert output_roots, "no committed generator example outputs found"

    for output_root in output_roots:
        manifest = _read_json(output_root / "manifest.json")
        for rel_path in manifest.get("generated_files", []):
            assert (output_root / rel_path).is_file(), f"missing generated file {rel_path!r}"

        failures_csv = output_root / str(manifest.get("failures_csv", "failures.csv"))
        assert failures_csv.is_file(), f"missing {failures_csv.relative_to(ROOT)}"

        run_id = str(manifest["run_id"])
        for state_id, status in manifest.get("scf_status", {}).items():
            if status == "skipped_no_requested_artifacts":
                continue
            state_dir = output_root / "scf" / run_id / state_id
            for filename in ("scf.chk", "scf.json", "scf.log", "scf.npz"):
                assert (state_dir / filename).is_file(), (
                    f"missing SCF example artifact {state_dir.relative_to(ROOT) / filename}"
                )


def test_committed_example_multiwfn_manifests_reference_existing_files() -> None:
    manifests = sorted(EXAMPLES_ROOT.glob("0*/output/multiwfn/manifest.json"))
    assert manifests, "no committed example Multiwfn manifests found"

    for manifest_path in manifests:
        output_root = manifest_path.parents[1]
        manifest = _read_json(manifest_path)
        records = manifest.get("files", [])
        assert records, f"empty Multiwfn manifest: {manifest_path.relative_to(ROOT)}"
        for record in records:
            rel_path = Path(str(record["path"]))
            assert (output_root / rel_path).is_file(), f"missing Multiwfn file {rel_path}"

            # The generator manifest keeps a legacy `file` alias for older
            # diagnostics. In committed examples it is repo-relative.
            file_alias = record.get("file")
            if file_alias is not None:
                assert (ROOT / str(file_alias)).is_file(), f"missing file alias {file_alias!r}"

            for key in ("source_scf_checkpoint", "source_scf_npz", "source_scf_metadata"):
                source_rel = record.get(key)
                if source_rel is not None:
                    assert (output_root / str(source_rel)).is_file(), (
                        f"missing {key} target {source_rel!r}"
                    )


def test_one_letter_example_wfn_names_keep_multiwfn_spacing() -> None:
    wfn_dir = EXAMPLES_ROOT / "01_cli_neutral_rad_wfn_bse" / "output" / "multiwfn" / "wfn"
    names = {path.name for path in wfn_dir.glob("*.wfn")}
    assert {"H .wfn", "B .wfn", "C .wfn", "N .wfn", "O .wfn", "F .wfn"} <= names
    assert not {"H.wfn", "B.wfn", "C.wfn", "N.wfn", "O.wfn", "F.wfn"} & names
