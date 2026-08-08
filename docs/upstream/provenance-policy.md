# Source provenance policy

Every future copied or adapted file must have an upstream project record containing the exact
repository revision, upstream path, local path, SHA-256 hash, license, copyright holder,
modification summary, attribution requirements, and replacement strategy. Hashes are checked
against the local file by `python scripts/validate_upstream.py`.

Restricted-license projects must always have empty `source_files_used` and
`source_file_hashes`. Generated reports, raw filing archives, credentials, and third-party
branding are never provenance artifacts and must not be committed.

v0.6.0 copied no upstream source. All adapter code and screen design are original to Market
Intelligence Lab.
