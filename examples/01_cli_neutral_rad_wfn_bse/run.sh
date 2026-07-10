#!/usr/bin/env bash
set -euo pipefail

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"

atomref-proatoms generate \
  --elements H \
  --element-range B-F \
  --method PBE0 \
  --relativity none \
  --basis bse:cc-pVDZ \
  --state-policy neutral \
  --artifacts rad,wfn \
  --workdir output \
  --allow-pyscf-version-mismatch \
  --allow-unverified-basis \
  --quiet-scf-log \
  --verbose 0 \
  --force
