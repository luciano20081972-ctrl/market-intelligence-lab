# Qlib research engine

`QlibResearchEngine` is an optional internal adapter. It consumes only MIL-produced snapshots, universes, outcomes, partitions, and manifests and normalizes factor/model artifacts back into MIL records. Availability and version are observable without importing Qlib at application startup. The deterministic fixture validates the boundary when Qlib is not installed; core operation never depends on it.
