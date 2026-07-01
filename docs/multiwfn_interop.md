# Multiwfn interoperability boundary

The v1 release publishes radial density profiles, density-cutoff radii, and QA
tables. It does not ship ready-made Multiwfn `atomwfn/` directories, `.wfn`
files, `.wfx` files, `.molden` files, checkpoint files, or Multiwfn `.rad` files.

## v1 status

The v1 data can be used as declared spherical reference-density data. It should
not be described as a drop-in replacement for Multiwfn's atomic wavefunction
files, and it should not be presented as a general Multiwfn proatom package.

Safe v1 wording:

```text
The v1 dataset can be exported or adapted for external tools, but
basis/method-matched Multiwfn atomwfn workflows are out of scope for v1.
```

Unsafe v1 wording:

```text
v1 provides ready-made Multiwfn atomwfn files
v1 replaces a Multiwfn atomwfn directory
v1 is a general Multiwfn proatom package
```

## Rationale

A radial profile is not the same object as an atomic wavefunction file. The v1
profile table stores only the spherical total density on a declared radial grid.
Multiwfn atom-wavefunction workflows may depend on additional choices, including
basis representation, orbital occupations, spin-channel layout, scalar
relativistic or effective-core conventions, wavefunction-file metadata, and the
level of theory used for the molecular calculation being analyzed.

For deformation-density and promolecular-wavefunction workflows, the safest
scientific convention is usually to recompute atomic references using the same or
explicitly chosen method/basis convention as the molecular calculation. A fixed
v1 radial-density table is therefore a useful reference dataset, but it is not a
universal atomic-wavefunction substitute.

## Tracked artifact policy

The following file types are intentionally absent from the v1 release artifacts:

```text
*.chk
*.log
*.molden
*.wfn
*.wfx
*.rad
```

The generated public artifacts remain:

```text
data/profiles/<dataset_id>/profiles.csv
data/radii/<dataset_id>/radii.csv
data/qa/<dataset_id>/qa.csv
```

Any external-tool adaptation should be documented as a derived workflow with its
own method, basis, file-format, and validation assumptions.
