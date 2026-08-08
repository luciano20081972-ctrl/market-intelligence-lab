from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy import stats  # type: ignore[import-untyped]
from skfolio.model_selection import CombinatorialPurgedCV  # type: ignore[import-untyped]
from sklearn.linear_model import LinearRegression  # type: ignore[import-untyped]
from sklearn.metrics import mean_squared_error  # type: ignore[import-untyped]
from statsmodels.stats.multitest import multipletests  # type: ignore[import-untyped]

from packages.hypothesis.types import FactorMetrics, TimePartition


def validate_partition(partition: TimePartition) -> None:
    boundaries = (
        partition.train_start,
        partition.train_end,
        partition.validation_start,
        partition.validation_end,
        partition.test_start,
        partition.test_end,
    )
    if any(value.tzinfo is None for value in boundaries):
        raise ValueError("partition boundaries must be timezone-aware")
    if not (
        partition.train_start
        < partition.train_end
        < partition.validation_start
        < partition.validation_end
        < partition.test_start
        < partition.test_end
    ):
        raise ValueError("TRAIN, VALIDATION, and FINAL OOS TEST boundaries must not overlap")
    if partition.purge_observations < 0 or partition.embargo_observations < 0:
        raise ValueError("purge and embargo observations cannot be negative")


def expanding_walk_forward(
    *,
    start: datetime,
    train_days: int,
    validation_days: int,
    test_days: int,
    folds: int,
    purge_days: int = 0,
    embargo_days: int = 0,
) -> list[TimePartition]:
    if min(train_days, validation_days, test_days, folds) <= 0:
        raise ValueError("walk-forward windows and fold count must be positive")
    result: list[TimePartition] = []
    for fold in range(folds):
        train_start = start
        train_end = start + timedelta(days=train_days + fold * test_days)
        validation_start = train_end + timedelta(days=purge_days + 1)
        validation_end = validation_start + timedelta(days=validation_days)
        test_start = validation_end + timedelta(days=embargo_days + 1)
        test_end = test_start + timedelta(days=test_days)
        partition = TimePartition(
            train_start=train_start,
            train_end=train_end,
            validation_start=validation_start,
            validation_end=validation_end,
            test_start=test_start,
            test_end=test_end,
            purge_observations=purge_days,
            embargo_observations=embargo_days,
        )
        validate_partition(partition)
        result.append(partition)
    return result


def purged_cross_validation(
    *, n_folds: int, n_test_folds: int, purge_observations: int, embargo_observations: int
) -> CombinatorialPurgedCV:
    if purge_observations < 0 or embargo_observations < 0:
        raise ValueError("purge and embargo observations cannot be negative")
    return CombinatorialPurgedCV(
        n_folds=n_folds,
        n_test_folds=n_test_folds,
        purged_size=purge_observations,
        embargo_size=embargo_observations,
    )


def partition_manifest(partition: TimePartition) -> dict[str, Any]:
    validate_partition(partition)
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in asdict(partition).items()
    }


def factor_statistics(
    factor: npt.ArrayLike, outcome: npt.ArrayLike, *, quantiles: int = 5
) -> FactorMetrics:
    x = np.asarray(factor, dtype=float)
    y = np.asarray(outcome, dtype=float)
    if x.shape != y.shape or x.ndim != 1:
        raise ValueError("factor and outcome must be one-dimensional arrays of equal length")
    valid = np.isfinite(x) & np.isfinite(y)
    coverage = float(np.mean(valid)) if len(x) else 0.0
    if int(valid.sum()) < max(5, quantiles):
        raise ValueError("factor statistics require at least five complete observations")
    clean_x, clean_y = x[valid], y[valid]
    pearson = float(stats.pearsonr(clean_x, clean_y).statistic)
    spearman = float(stats.spearmanr(clean_x, clean_y).statistic)
    boundaries = np.quantile(clean_x, np.linspace(0, 1, quantiles + 1))
    groups = np.clip(np.digitize(clean_x, boundaries[1:-1], right=True), 0, quantiles - 1)
    means = [float(np.mean(clean_y[groups == index])) for index in range(quantiles)]
    monotonic = float(stats.spearmanr(range(quantiles), means).statistic)
    spread = means[-1] - means[0]
    direction = np.sign(clean_x - float(np.median(clean_x)))
    hit_rate = float(np.mean(direction * clean_y > 0))
    ranks = stats.rankdata(clean_x)
    turnover = float(np.mean(np.abs(np.diff(ranks)))) if len(ranks) > 1 else 0.0
    autocorrelation = (
        float(np.corrcoef(clean_x[:-1], clean_x[1:])[0, 1]) if len(clean_x) > 2 else 0.0
    )
    warnings: list[str] = []
    if coverage < 0.8:
        warnings.append("LOW_COVERAGE")
    if not math.isfinite(monotonic):
        monotonic = 0.0
        warnings.append("UNDEFINED_QUANTILE_MONOTONICITY")
    return FactorMetrics(
        pearson_ic=pearson,
        spearman_ic=spearman,
        hit_rate=hit_rate,
        coverage=coverage,
        missingness=1.0 - coverage,
        quantile_monotonicity=monotonic,
        top_minus_bottom=spread,
        turnover=turnover,
        autocorrelation=autocorrelation,
        warnings=tuple(warnings),
    )


def aggregate_ic(values: Sequence[float]) -> dict[str, float]:
    items = np.asarray(values, dtype=float)
    if len(items) == 0:
        raise ValueError("at least one fold IC is required")
    mean = float(np.mean(items))
    standard_deviation = float(np.std(items, ddof=1)) if len(items) > 1 else 0.0
    return {
        "mean_ic": mean,
        "ic_std": standard_deviation,
        "ic_information_ratio": mean / standard_deviation if standard_deviation else 0.0,
        "positive_fold_rate": float(np.mean(items > 0)),
    }


def adjust_p_values(
    p_values: Sequence[float], *, method: str, alpha: float = 0.05
) -> list[dict[str, float | bool | int | str]]:
    methods = {
        "bonferroni": "bonferroni",
        "holm": "holm",
        "benjamini-hochberg": "fdr_bh",
    }
    if method not in methods:
        raise ValueError("unsupported multiple-testing correction")
    if not p_values or any(not 0 <= value <= 1 for value in p_values):
        raise ValueError("p-values must be a non-empty sequence within [0, 1]")
    rejected, adjusted, _, _ = multipletests(p_values, alpha=alpha, method=methods[method])
    return [
        {
            "raw_p_value": float(raw),
            "adjusted_p_value": float(corrected),
            "rejected_null": bool(is_rejected),
            "number_of_hypotheses": len(p_values),
            "correction_method": method,
        }
        for raw, corrected, is_rejected in zip(p_values, adjusted, rejected, strict=True)
    ]


def incremental_information_test(
    baseline: npt.ArrayLike,
    candidate: npt.ArrayLike,
    outcome: npt.ArrayLike,
    train_size: int,
) -> dict[str, float]:
    base = np.asarray(baseline, dtype=float)
    addition = np.asarray(candidate, dtype=float).reshape(-1, 1)
    target = np.asarray(outcome, dtype=float)
    if not 5 <= train_size < len(target):
        raise ValueError("train_size must preserve a non-empty out-of-sample partition")
    if base.shape[0] != len(target) or addition.shape[0] != len(target):
        raise ValueError("baseline, candidate, and outcome rows must align")
    base_model = LinearRegression().fit(base[:train_size], target[:train_size])
    combined = np.column_stack([base, addition])
    combined_model = LinearRegression().fit(combined[:train_size], target[:train_size])
    base_predictions = base_model.predict(base[train_size:])
    combined_predictions = combined_model.predict(combined[train_size:])
    base_error = float(mean_squared_error(target[train_size:], base_predictions))
    combined_error = float(mean_squared_error(target[train_size:], combined_predictions))
    return {
        "baseline_mse": base_error,
        "baseline_plus_candidate_mse": combined_error,
        "mse_improvement": base_error - combined_error,
        "candidate_adds_information": float(combined_error < base_error),
    }


def deterministic_negative_controls(values: npt.ArrayLike, seed: int) -> dict[str, np.ndarray]:
    original = np.asarray(values, dtype=float)
    generator = np.random.default_rng(seed)
    shuffled = original.copy()
    generator.shuffle(shuffled)
    return {
        "shuffled": shuffled,
        "deterministic_noise": generator.normal(0, 1, len(original)),
        "unrelated_sector": np.roll(original, max(1, len(original) // 3)),
        "temporal_corruption": original[::-1],
    }


LEAKAGE_ATTACKS = frozenset(
    {
        "future_alfred_vintage",
        "future_sec_disclosure",
        "future_graph_relationship",
        "future_feature_revision",
        "future_universe_membership",
        "future_normalization",
        "future_publication_time",
        "target_label_leakage",
        "post_event_identifier",
    }
)


def validate_leakage_fixture(metadata: dict[str, Any]) -> list[str]:
    detected = sorted(key for key in LEAKAGE_ATTACKS if metadata.get(key) is True)
    if detected:
        raise ValueError("temporally contaminated experiment: " + ", ".join(detected))
    return []
