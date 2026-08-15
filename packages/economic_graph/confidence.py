from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CONFIDENCE_FORMULA_VERSION = "graph-confidence-v1"
CONFIDENCE_WEIGHTS: dict[str, Decimal] = {
    "source_reliability": Decimal("0.20"),
    "identifier_confidence": Decimal("0.20"),
    "temporal_validity": Decimal("0.15"),
    "evidence_agreement": Decimal("0.15"),
    "extraction_confidence": Decimal("0.10"),
    "relationship_specificity": Decimal("0.10"),
    "recency": Decimal("0.10"),
}


def aggregate_confidence(components: dict[str, Decimal]) -> Decimal:
    missing = set(CONFIDENCE_WEIGHTS) - set(components)
    extra = set(components) - set(CONFIDENCE_WEIGHTS)
    if missing or extra:
        raise ValueError(
            f"confidence components mismatch; missing={sorted(missing)} extra={sorted(extra)}"
        )
    for name, value in components.items():
        if value < 0 or value > 1:
            raise ValueError(f"confidence component {name} must be between 0 and 1")
    score = sum(
        (components[name] * weight for name, weight in CONFIDENCE_WEIGHTS.items()),
        start=Decimal("0"),
    )
    return score.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
