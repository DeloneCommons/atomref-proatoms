# atomref-proatoms report

This directory contains the generated scientific report for the active profile-data
version. Older reports are expected to live in Git tags, GitHub releases, and Zenodo
records rather than in parallel versioned report directories on the active branch.

Generated files:

```text
report/report.md
report/report_manifest.json
report/tables/dataset_summary.csv
report/tables/state_summary.csv
report/tables/qa_summary.csv
report/tables/derived_radii.csv
report/figures/electron_count_error.svg
```

The report is rebuilt from released profile artifacts under `data/profiles/`:

```bash
python scripts/build_report.py
```
