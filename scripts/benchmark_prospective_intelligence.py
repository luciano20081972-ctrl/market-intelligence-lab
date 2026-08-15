from __future__ import annotations

import json
import time

from packages.core.time import utc_now
from packages.prospective_intelligence.service import (
    aggregate_scores,
    construct_portfolio,
    research_risk,
    score_forecast,
)


def timed(operation):  # type: ignore[no-untyped-def]
    started = time.perf_counter()
    value = operation()
    return time.perf_counter() - started, value


def main() -> None:
    now = utc_now()
    scoring_seconds, scores = timed(
        lambda: [
            score_forecast("PROBABILITY", (index % 100) / 100, index % 2)
            for index in range(100_000)
        ]
    )
    rows = [{"evaluation_mode": "PROSPECTIVE", "observed_at": now, **score} for score in scores]
    calibration_seconds, calibration = timed(
        lambda: aggregate_scores(rows, mode="PROSPECTIVE", as_of=now)
    )
    candidate_scores = {f"ASSET-{index}": 1 / (index + 1) for index in range(1_000)}
    portfolio_seconds, plan = timed(
        lambda: construct_portfolio(candidate_scores, max_position=0.02, min_cash=0.1)
    )
    risk_seconds, risk = timed(
        lambda: research_risk(
            plan["weights"],
            {asset: f"domain-{index % 20}" for index, asset in enumerate(plan["weights"])},
            max_position=0.02,
            max_domain=0.2,
        )
    )
    print(
        json.dumps(
            {
                "forecast_scores": 100_000,
                "scoring_seconds": round(scoring_seconds, 6),
                "calibration_seconds": round(calibration_seconds, 6),
                "calibration_sample_count": calibration["sample_count"],
                "paper_candidates": 1_000,
                "portfolio_seconds": round(portfolio_seconds, 6),
                "risk_seconds": round(risk_seconds, 6),
                "portfolio_positions": len(plan["weights"]),
                "risk_approved": risk["approved"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
