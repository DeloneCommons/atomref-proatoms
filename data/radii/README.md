# Cutoff radii

Generated cutoff-radius result tables live under:

```text
data/radii/<dataset_id>/
  radii.csv
  metadata.json
```

`radii.csv` contains one row per generated state and includes radii in bohr and ångström
for every cutoff declared in `data/profile_datasets.yaml`. The v1 release treats the
0.003 and 0.001 electron/bohr³ cutoff radii as primary practical results; the 0.0001
cutoff remains useful as a low-density tail diagnostic.
