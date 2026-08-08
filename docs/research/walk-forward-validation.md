# Walk-forward validation

Every experiment declares non-overlapping TRAIN/DEVELOPMENT, VALIDATION, and sealed FINAL OUT-OF-SAMPLE TEST ranges. Expanding and rolling folds are supported. Each fold stores its ranges, observation count, coverage, factor/model statistics, warnings, failures, purge observations, and embargo observations; failed folds remain visible.

The generator cannot inspect the sealed test period. Overlap, reversed ranges, and insufficient purge/embargo separation are rejected. `skfolio.model_selection.CombinatorialPurgedCV` is wrapped where combinatorial purged evaluation is appropriate; MIL retains explicit dates in its manifest.
