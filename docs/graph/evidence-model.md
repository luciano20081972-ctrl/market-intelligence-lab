# Relationship evidence and confidence

`evidence_records` references a source manifest or source entity and stores the source record identifier, publication and eligibility times, evidence type, bounded structured payload, content reference, an exact supporting span only where permitted, checksum, parser/extractor version, and confidence. Large source documents stay in content-addressed storage; they are not copied into graph rows.

`relationship_evidence` links many evidence records to a relationship as supporting or contradicting. Verified relationships require supporting evidence. Contradicting evidence remains visible and produces a quality issue.

Confidence uses formula `graph-confidence-v1`. Separate component rows preserve source reliability, identifier confidence, temporal validity, evidence agreement, extraction confidence, relationship specificity, and recency. The deterministic weighted average is stored with its formula version. Scores are bounded judgment aids, not fabricated probabilities, and a future formula creates a new version rather than rewriting history.
