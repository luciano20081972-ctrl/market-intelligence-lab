# Multiple testing

Every tested family retains the raw p-value, adjusted p-value, family name, family size, correction method, alpha, and decision. Supported methods are Bonferroni, Holm, and Benjamini–Hochberg false-discovery-rate control through statsmodels. APIs and UI never present raw p-values alone for a multiple-hypothesis family. Failure after correction is an expected rejected-research outcome.
