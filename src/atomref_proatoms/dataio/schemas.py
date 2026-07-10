"""Schema constants used by atomref-proatoms data checks."""

from __future__ import annotations

ATOM_STATE_SCHEMA_VERSION = "atomref.proatoms.state.v2"
ATOM_STATE_SUMMARY_SCHEMA_VERSION = "atomref.proatoms.state_build_summary.v2"
BASIS_BUNDLE_SCHEMA_VERSION = "atomref.proatoms.basis_bundle.v0"
BASIS_SET_SUMMARY_SCHEMA_VERSION = "atomref.proatoms.basis_set_summary.v0"
PROFILE_METADATA_SCHEMA_VERSION = "atomref.proatom_profile.v1"
PROFILE_DATASET_MANIFEST_SCHEMA_VERSION = "atomref.proatoms.profile_dataset.v1"

DENSITY_MODEL = "self_consistent_fractional_occupation_spherical_uks"
V2_OCCUPATION_POLICY = "spherical_l_counts_from_curated_multiplicity_v2"
V2_SPIN_MODEL = "curated_ground_multiplicity"
V2_SPIN_VARIANT = "curated_multiplicity"
ALLOWED_ATOM_STATE_SCHEMA_VERSIONS = frozenset({ATOM_STATE_SCHEMA_VERSION})
ALLOWED_OCCUPATION_POLICIES = frozenset({V2_OCCUPATION_POLICY})
ALLOWED_SPIN_MODELS = frozenset({V2_SPIN_MODEL})
ALLOWED_SPIN_VARIANTS = frozenset({V2_SPIN_VARIANT})

REQUIRED_STATE_FIELDS = frozenset(
    {
        "schema_version",
        "state_id",
        "symbol",
        "z",
        "charge",
        "electron_count",
        "configuration",
        "spin_2s",
        "multiplicity",
        "alpha_l_counts",
        "beta_l_counts",
        "spin_model",
        "spin_variant",
        "state_role",
        "occupation_policy",
        "state_category",
        "curation_status",
        "notes",
    }
)

FORBIDDEN_STATE_FIELDS = frozenset({"source", "sources"})

REQUIRED_PROFILE_METADATA_FIELDS = frozenset(
    {
        "schema_version",
        "dataset_id",
        "state_id",
        "density_model",
        "method",
        "state",
        "units",
        "derived",
        "qa",
    }
)

REQUIRED_PROFILE_METHOD_FIELDS = frozenset(
    {
        "engine",
        "engine_version",
        "scf_type",
        "xc",
        "relativity",
        "basis_id",
        "basis_sha256",
    }
)
