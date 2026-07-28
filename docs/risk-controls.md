# Risk controls

Each paper portfolio starts with nine enabled rules. They are evaluated before a simulated order is accepted:

- maximum position percentage (40%)
- maximum total exposure (100%)
- maximum daily simulated loss (5%)
- maximum portfolio drawdown (25%)
- maximum daily fill count (20)
- maximum sector exposure (50%)
- minimum cash reserve (2%)
- maximum order value ($50,000)
- stale-price age (3,650 days for the fixed demonstration dataset)

Limits are configurable per portfolio through the API and Risk Settings screen. A rejection contains the measured/projected value and violated limit. Long-only ownership and active-portfolio checks apply in addition to configured rules.

Daily loss and fill-count checks use the eligible bar's date because this release works from historical fixed bars. Staleness uses the stored retrieval date against the current date. Rules reduce simulated risk but are not guarantees: daily gaps, unmodeled liquidity, and simplified bar paths can produce outcomes unlike a live market.
