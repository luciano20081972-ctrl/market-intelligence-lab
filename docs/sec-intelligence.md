# SEC intelligence

v0.6.0 adds normalized support for 10-K, 10-Q, 8-K, Forms 3/4/5, 13F-HR,
company submissions, and company facts/XBRL. Canonical records retain CIK, accession,
filing/acceptance/reporting times, source URL, retrieval time, content checksum, parser and
EdgarTools versions, amendment status, raw-document reference, and simulation eligibility.

Ordinary tests use a deterministic fixture. Live retrieval is opt-in, requires an identifying
application/contact user agent, is capped at 10 requests/second (default 4), and must use caching,
bounded retries, timeouts, and a worker. The HTTP API never exposes EdgarTools objects.

Raw filing archives are not committed. Source URLs and content-addressed references are stored;
production object storage is future work.
