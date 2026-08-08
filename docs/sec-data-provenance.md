# SEC data provenance

`accepted_at` is the first simulation-eligible time for a filing fixture. Research must not use
filing or fact content before that timestamp. Retrieval time, parser version, EdgarTools version,
document reference, accession number, amendment flag, and SHA-256 checksum make imports
auditable and idempotent.

SEC public data is system-shared. Import requests and parse jobs remain workspace-scoped.
Duplicate accession numbers are not duplicated; child facts, holdings, and insider transactions
use deterministic identity checks.
