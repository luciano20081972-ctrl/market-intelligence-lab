# Progressive resolution

The versioned policy defines `LEVEL_0` Universe, `LEVEL_1` Cheap Screen, `LEVEL_2` Structured Research, `LEVEL_3` Domain Deep Dive, and `LEVEL_4` AI Research Candidate. Each level specifies entry/exit policies, maximum population, allowed data/feature sets, compute/data class, refresh interval, and promotion/demotion rules in `config/research-resolution.yaml`. LEVEL_4 is only eligibility for future research; v0.9 does not run AI research.

The deterministic reference funnel is 100 → 50 → 20 → 8 → 3. Identical eligible inputs, policy, seed, and software produce identical decisions. Screening prioritizes research and never estimates returns.
