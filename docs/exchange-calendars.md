# Exchange calendars

Version 0.3.0 seeds XNYS sessions for 2025-2027 with America/New_York timezone conversion, weekends, observed holidays, and known early closes. Session timestamps are persisted in UTC while the source timezone remains explicit.

Ingestion compares daily bars with stored open sessions and rejects closed-session bars. The bundled holiday table is deliberately finite; Sprint 4 should integrate a maintained calendar source and add ongoing reconciliation.
# Maintained XNYS source

Version 0.4 uses `exchange-calendars` for timezone-aware XNYS sessions instead of relying on the finite hand-maintained 2025–2027 set. The standard seed persists 2020–2035 labels, UTC open/close timestamps, official holidays, weekends, and early-close flags in the existing tables. The generation API supports requested ranges beyond 2027.

Imported daily bar dates must match an eligible persisted session. A provider bar on a closed date is rejected and later visible in reconciliation; provider dates are not silently treated as authoritative. Calendar package upgrades may change exceptional sessions, so upgrades require drift review and reconciliation.
