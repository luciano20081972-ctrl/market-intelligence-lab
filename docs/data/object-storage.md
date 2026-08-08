# Immutable object storage

`RawObjectStore` defines `put`, `metadata`, `exists`, and checksum verification. The local adapter writes beneath a configured root and rejects traversal. A logical key is:

```text
provider/dataset/YYYY/MM/DD/checksum-or-stable-id
```

Keys are immutable: the same key/content is idempotent; different content at an existing key fails closed. SHA-256 metadata is verified from stored bytes.

The protocol maps to S3-compatible object storage, Cloudflare R2, or Supabase Storage without embedding any vendor URL, bucket, or credential. Supabase Storage's S3 compatibility does not provide S3 object versioning, so content-addressed immutable keys remain required. Server credentials stay backend-only. Browser clients must never receive server S3 keys; Supabase `storage.objects` policies remain independently required for any user-scoped browser access.

The local adapter is implemented and fixture-tested. Cloud adapters are compatibility contracts and are not live-verified in v0.7.
