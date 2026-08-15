# Forecast scoring

Directional forecasts use correctness; explicit probabilities use Brier score and log loss; continuous forecasts use absolute/squared error and signed bias; intervals use coverage, width, and interval score; ranks use Spearman/rank IC. Scenario-conditional forecasts are scored only when their condition is valid. Incompatible types are never compressed into universal accuracy.
