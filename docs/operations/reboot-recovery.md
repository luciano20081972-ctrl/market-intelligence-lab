# Reboot recovery

API readiness gates dependents. Worker and scheduler use restart policies and durable database
state, not in-memory timers or long sleeps. On startup, expired leases become reclaimable and queued
work remains present. SIGTERM stops new claims, checkpoints bounded work, expires/releases leases,
and flushes structured logs.
