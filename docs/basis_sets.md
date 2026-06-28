# Basis sets

The frozen `basis.nw` files under `data/basis_sets/` define basis-data identity.
Default checks are offline and validate stored metadata, SHA256 hashes, NWChem spherical
headers, coverage, and root-summary/per-manifest source consistency.

The BSE `source.source_api_url` is mandatory stored provenance, but ordinary checks do not
fetch the current BSE internet response.
