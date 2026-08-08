# RD-Agent integration audit

Audited release: `rdagent 0.8.0`, MIT, Python 3.10+, with current documentation describing Linux support, Docker for most scenarios, tested Python 3.10/3.11, LLM chat/JSON/embedding requirements, and Qlib-oriented factor/model workflows. Its generated-code execution, external-model cost, platform constraints, and container boundary make it unsuitable as an ordinary runtime dependency.

Decision: optional, disabled artifact adapter only. MIL provides a bounded secret-free research brief to a future isolated runner with network off by default, timeout and CPU/memory limits, deterministic inputs, restricted filesystem, and captured artifacts. Output becomes a candidate specification and must pass the complete MIL validation pipeline. It receives no database, Supabase, GitHub, brokerage, or production credentials; generated code is neither canonical nor merged automatically.

Sources: [PyPI](https://pypi.org/project/rdagent/), [repository](https://github.com/microsoft/RD-Agent), and [releases](https://github.com/microsoft/RD-Agent/releases).
