# Upstream license policy

Public visibility and repository popularity are not permission to copy code.

MIT, BSD-2-Clause, and BSD-3-Clause dependencies or adapted files are allowed when
copyright/license notices and conditions are preserved. Apache-2.0 use must additionally
preserve NOTICE material where present, mark modifications, retain patent terms, and avoid
trademark implications.

LGPL libraries are replaceable dynamic dependencies or external processes by default.
Copying LGPL internals into the core requires legal review and any distribution must preserve
replacement/relinking rights. GPL projects are reference-only by default; even a separate
process requires legal review. AGPL projects are reference-only and may not underpin a network
service without an explicit source-offer decision. Custom, commercial, or unlicensed code is
reference-only; implementation must be independently derived from public behavior and
requirements.

Unknown licenses fail CI. GPL/AGPL/custom-restricted source paths may not be vendored.
Direct dependencies must appear in `config/upstream-projects.yaml`, and notices must remain in
`THIRD_PARTY_NOTICES.md`.
