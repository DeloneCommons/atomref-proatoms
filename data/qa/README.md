# Quality-assurance tables

Generated QA artifacts live under:

```text
data/qa/<dataset_id>/
  qa.csv
  metadata.json

data/qa/qa_summary.csv
data/qa/qa_report.md
data/qa/metadata.json
```

The QA directory contains compact release-gate tables only. It intentionally avoids
figures and narrative analysis; user-facing explanation belongs in documentation notebooks
under `docs/notebooks/`.
