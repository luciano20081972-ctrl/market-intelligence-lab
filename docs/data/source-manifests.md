# Source and data manifests

A manifest is an immutable provenance envelope for one exact acquired object. It records safe provider/dataset identifiers, source/schema/parser versions, retrieval and source-update times, temporal coverage, raw-object reference, SHA-256 checksum, bytes, total/accepted/rejected rows, quality summary, license identifier, import job, and optional parent manifest.

The unique `(source_id, dataset_id, checksum)` constraint makes repeated acquisition idempotent. A child manifest may represent an extracted or normalized derivative but never replaces its parent. Normalized observations reference a manifest with `RESTRICT` deletion semantics.

Health responses expose configuration, fixture/live verification independently, latest retrieval, freshness, expected frequency, lag, record count, latest manifest, coverage, and license. “Fixture verified” does not imply network availability.
