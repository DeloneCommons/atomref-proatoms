#!/usr/bin/env bash
set -euo pipefail

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"

atomref-proatoms generate \
  --elements Ni,Pd \
  --charges=-1,0,+1 \
  --method PBE0 \
  --relativity x2c \
  --basis-file input/dyall-v2z-ni-pd-pt.nw \
  --basis-name dyall-v2z-ni-pd-pt \
  --state-policy stockholder \
  --artifacts all \
  --workdir output \
  --allow-pyscf-version-mismatch \
  --allow-unverified-basis \
  --quiet-scf-log \
  --verbose 0 \
  --grid-level 0 \
  --force
