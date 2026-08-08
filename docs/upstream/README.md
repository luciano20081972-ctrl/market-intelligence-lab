# Upstream integration governance

Market Intelligence Lab integrates external financial software only through stable,
replaceable internal protocols. The repository inventory is authoritative for evaluated
projects; the dependency lock files remain authoritative for resolved package graphs.

No evaluated upstream source file was copied or adapted for v0.6.0. Ordinary tests use
deterministic fixtures and do not make SEC, brokerage, cloud, or upstream network calls.

- `license-policy.md` defines allowed and prohibited license categories.
- `provenance-policy.md` defines evidence for any future copied/adapted file.
- `upstream-inventory.md` explains the reviewed projects.
- `reference-feature-study.md` records independent architecture inspiration.
- `config/upstream-projects.yaml` is the machine-readable gate.
