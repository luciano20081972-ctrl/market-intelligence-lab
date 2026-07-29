# Exchange calendars

Version 0.3.0 seeds XNYS sessions for 2025-2027 with America/New_York timezone conversion, weekends, observed holidays, and known early closes. Session timestamps are persisted in UTC while the source timezone remains explicit.

Ingestion compares daily bars with stored open sessions and rejects closed-session bars. The bundled holiday table is deliberately finite; Sprint 4 should integrate a maintained calendar source and add ongoing reconciliation.
