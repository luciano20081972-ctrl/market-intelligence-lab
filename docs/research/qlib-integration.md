# Qlib integration audit

Audited release: `pyqlib 0.9.7`, MIT. It advertises Python 3.8–3.12 and publishes CPython 3.12 Windows and manylinux wheels. Qlib supplies factor/model workflows, dataset abstractions, evaluation, and backtesting, but its dependency and data-initialization stack creates meaningful integration overhead; some documented multi-model tooling remains Linux-only.

Decision: optional research engine, not canonical storage. MIL exports a point-in-time universe, feature/outcome matrix, sealed partitions, snapshot and manifest; the adapter returns normalized results, version/config/seed/duration/warnings/artifact checksums. Temporal Truth, graph state, lineage, budgets, and audit history stay in MIL. The fixture adapter proves the contract when Qlib is absent. Adoption avoids reimplementing full model workflows, while MIL retains its unique temporal and governance layer.

Sources: [PyPI](https://pypi.org/project/pyqlib/), [repository](https://github.com/microsoft/qlib), and [MIT license](https://github.com/microsoft/qlib/blob/main/LICENSE).
