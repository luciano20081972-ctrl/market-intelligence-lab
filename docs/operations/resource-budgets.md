# Resource budgets and backpressure

Configuration bounds concurrent ingestion/research work, backlog, raw storage, free disk, and
scheduler/worker leases. Admission defers work when a budget is reached. Priority is critical
operations, data refresh, forecast maturity, research maintenance, then background research.
Queue depth and oldest age remain visible; the system never starts an unbounded set of jobs.
