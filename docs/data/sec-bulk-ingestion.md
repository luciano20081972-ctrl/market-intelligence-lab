# Direct SEC and bulk ingestion

The canonical v0.7 path uses official `data.sec.gov` submissions and companyfacts JSON directly. CIKs normalize to ten digits, accession numbers to `##########-##-######`, accepted timestamps remain distinct from filing dates, amendments retain `/A`, and simulation eligibility is no earlier than both acceptance and local retrieval.

Raw bytes are checksummed and stored before parsing. Repeated checksums are no-ops; normalized uniqueness provides a concurrent-write backstop. Manifests connect official URLs, parser version, counts, and raw references. Daily/incremental cursors permit restart after a completed accession or archive member.

The bulk foundation uses the same acquisition/manifest/extraction contract for official archives. Archive paths and members must be bounded, zip-slip safe, and decompressed under configured limits before normalization. v0.7 does not claim a complete historical SEC warehouse. EdgarTools remains an optional parser boundary and is not the canonical acquisition dependency.
