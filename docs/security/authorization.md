# Authorization

Roles are owner, admin, member, and viewer. The centralized mapping covers workspace read/update, members, audit, research, backtests, paper portfolios/orders, schedules, providers, and recovery. The backend derives the user only from verified claims, resolves membership, applies the required permission, and scopes resource lookup before returning data. Frontend visibility is convenience, never the enforcement boundary.

Owners have all permissions. Admins manage members and providers but cannot bypass tenant scope. Members may create research, simulations, paper resources, and schedules. Viewers are read-only. Unknown workspace/resource identifiers return a uniform 404 to reduce identifier leakage.
