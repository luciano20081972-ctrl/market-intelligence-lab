# Adversarial build-vs-integrate audit

NumPy, SciPy, statsmodels, and scikit-learn are BSD-licensed, maintained, Python-compatible dependencies already available through the integrations extra. They remain suitable for bounded residualization, robustness, and sensitivity work. NetworkX is BSD-licensed and maintained, but MIL already has persisted temporal graph traversal and adding a second graph authority would complicate point-in-time replay.

DoWhy (MIT) and EconML (MIT) are maintained causal-inference projects with substantial scientific value when identification assumptions are defensible. v0.12 does not add them: the release performs mechanism-conditioned simulations, not identified causal estimation; their dependency and reproducibility burden provides no measured value for the required deterministic fixtures. Reconsider them only for a separately reviewed, explicitly identified design.

MIL therefore builds a small deterministic rules layer over existing graph, ablation, Research Memory, Signal Independence, NumPy/statsmodels capabilities. Inputs remain versioned and as-of bounded, manifests retain exact parameters and checksums, and no opaque model output becomes authoritative.
