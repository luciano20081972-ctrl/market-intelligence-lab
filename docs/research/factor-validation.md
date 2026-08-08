# Factor validation

A `FactorExperiment` binds one hypothesis, feature specification, outcome, universe version, immutable feature snapshot, graph state, period, protocol, costs, software/dependencies, and seed. Completed/rejected experiments cannot be edited. Retained outputs include Pearson/Spearman IC, mean/std/information ratio, quantile monotonicity and spread, hit rate, turnover, coverage/missingness, decay, sector/time stability, autocorrelation, and conventional baseline-versus-candidate predictive error. Sharpe is never the sole criterion.

SciPy 1.18.0 supplies statistics, statsmodels 0.14.6 supplies multiple-testing corrections, scikit-learn 1.9.0 supplies the baseline comparison, and skfolio 0.20.1 supplies purged/embargoed cross-validation. These permissively licensed dependencies replace bespoke numerical implementations while MIL owns temporal boundaries and governance.
