import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function Operations() {
  const queryClient = useQueryClient();
  const queueQuery = useQuery({ queryKey: ["operations-queue"], queryFn: api.operationQueue, refetchInterval: 10_000 });
  const workersQuery = useQuery({ queryKey: ["operations-workers"], queryFn: api.operationWorkers, refetchInterval: 10_000 });
  const healthQuery = useQuery({ queryKey: ["operations-health"], queryFn: api.operationHealth, refetchInterval: 10_000 });
  const centerQuery = useQuery({ queryKey: ["operations-center"], queryFn: api.operationsCenter, refetchInterval: 10_000 });
  const freshnessQuery = useQuery({ queryKey: ["operations-freshness"], queryFn: api.freshnessStatuses, refetchInterval: 30_000 });
  const alertsQuery = useQuery({ queryKey: ["operations-alerts"], queryFn: api.operationalAlerts, refetchInterval: 30_000 });
  const schedulesQuery = useQuery({ queryKey: ["operational-schedules"], queryFn: api.scheduledTasks, refetchInterval: 30_000 });
  const recover = useMutation({
    mutationFn: api.recoverAbandoned,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["operations-queue"] }),
        queryClient.invalidateQueries({ queryKey: ["operations-workers"] }),
        queryClient.invalidateQueries({ queryKey: ["operations-health"] }),
      ]);
    },
  });
  if (queueQuery.isLoading || workersQuery.isLoading || healthQuery.isLoading || centerQuery.isLoading) return <LoadingState label="Loading Operations Center" />;
  if (queueQuery.error) return <ErrorState error={queueQuery.error} />;
  if (workersQuery.error) return <ErrorState error={workersQuery.error} />;
  if (healthQuery.error) return <ErrorState error={healthQuery.error} />;
  if (centerQuery.error) return <ErrorState error={centerQuery.error} />;
  const queue = queueQuery.data!;
  const workers = workersQuery.data?.items ?? [];
  const center = centerQuery.data!;
  return <section><div className="page-heading"><div><p className="eyebrow">PRIVATE BETA OPERATIONS</p><h1>Operations Center</h1><p>Health, freshness, durable work, providers, backups, and operator actions in one place.</p></div><span className="status-chip">{center.overall}</span></div>
    <h2 className="section-title">System health</h2><div className="metric-grid">{Object.entries(center.categories).map(([name, value]) => <article key={name}><span>{name.replaceAll("_", " ")}</span><strong>{value}</strong></article>)}</div>
    {center.maintenance.enabled ? <div className="warning-card" role="status"><strong>Maintenance mode</strong><p>{center.maintenance.reason}</p></div> : null}
    <div className="page-heading"><div><h2>Jobs and workers</h2><p>Claims are leased and abandoned work becomes safely reclaimable.</p></div><button type="button" className="secondary" disabled={recover.isPending} onClick={() => recover.mutate()}>{recover.isPending ? "Recovering…" : "Recover abandoned jobs"}</button></div>
    <div className="metric-grid"><article><span>Queue depth</span><strong>{queue.depth}</strong></article><article><span>Running</span><strong>{queue.running}</strong></article><article><span>Failed / dead letter</span><strong>{queue.failed}</strong></article><article><span>Overall</span><strong>{String(healthQuery.data?.status ?? "unknown")}</strong></article></div>
    <h2 className="section-title">Queue state</h2><div className="source-grid">{Object.entries(queue.by_status).map(([state, count]) => <article className="panel" key={state}><span>{state}</span><strong className="large-number">{count}</strong></article>)}</div>
    <h2 className="section-title">Workers</h2>{workers.length === 0 ? <EmptyState title="No worker registered" detail="Start python -m packages.market_data.worker to process queued imports." /> : <div className="table-card"><table><thead><tr><th>Worker</th><th>Status</th><th>Heartbeat</th><th>Current job</th></tr></thead><tbody>{workers.map(worker => <tr key={worker.id}><td>{worker.worker_identifier}</td><td><span className="status-chip">{worker.status}</span></td><td>{new Date(worker.last_heartbeat_at).toLocaleString()}</td><td>{worker.current_job_id ?? "Idle"}</td></tr>)}</tbody></table></div>}
    <h2 className="section-title">Data freshness</h2>{freshnessQuery.isLoading ? <LoadingState label="Loading data freshness" /> : freshnessQuery.error ? <ErrorState error={freshnessQuery.error} /> : freshnessQuery.data?.length ? <div className="table-card"><table><thead><tr><th>Provider</th><th>Dataset</th><th>Freshness</th><th>Expected next update</th><th>Current issue</th></tr></thead><tbody>{freshnessQuery.data.map(item => <tr key={item.id}><td>{item.provider}</td><td>{item.dataset}</td><td><span className="status-chip">{item.provider_delayed ? "SOURCE NOT PUBLISHED YET" : item.status}</span></td><td>{item.expected_next_update_at ? new Date(item.expected_next_update_at).toLocaleString() : "Unknown"}</td><td>{item.current_error ?? "None"}</td></tr>)}</tbody></table></div> : <EmptyState title="No freshness records" detail="Freshness appears after an approved dataset is scheduled." />}
    <h2 className="section-title">Schedules</h2>{schedulesQuery.data?.length ? <div className="table-card"><table><thead><tr><th>Schedule</th><th>Task</th><th>Cadence</th><th>Next run</th><th>Status</th></tr></thead><tbody>{schedulesQuery.data.map(item => <tr key={item.id}><td>{item.name}</td><td>{item.task_type}</td><td>{item.schedule_type}</td><td>{new Date(item.next_due_at).toLocaleString()}</td><td>{item.enabled ? "Enabled" : "Paused"}</td></tr>)}</tbody></table></div> : <EmptyState title="No private-beta schedules" detail="Define only approved providers and controlled research maintenance tasks." />}
    <h2 className="section-title">Operational alerts</h2>{alertsQuery.data?.length ? <div className="source-grid">{alertsQuery.data.map(alert => <article className="panel" key={alert.id}><span className="status-chip">{alert.severity}</span><h3>{alert.summary}</h3><p><strong>Affected:</strong> {alert.impact}</p><p><strong>Still available:</strong> {alert.unaffected}</p><p><strong>Recommended action:</strong> {alert.recommended_action}</p></article>)}</div> : <EmptyState title="No open operational alerts" detail="Repeated conditions are deduplicated and remain visible until resolved." />}
    <h2 className="section-title">Backup and deployment readiness</h2><div className="source-grid"><article className="panel"><h3>Backup status</h3><p>{center.latest_backup ? `${center.latest_backup.status} · ${center.latest_backup.verification_state}` : "No verified backup manifest recorded"}</p></article><article className="panel"><h3>Deployment readiness</h3><p>Run <code>python -m scripts.private_beta_readiness</code> before deployment. Production deploy remains a separate approval.</p></article><article className="panel"><h3>Resource usage</h3><p>Backlog, provider concurrency, storage, and CPU-heavy work are bounded by configuration.</p></article></div>
    {recover.data ? <p className="success-message" role="status">Recovered {recover.data.count} abandoned job(s).</p> : null}{recover.error ? <p className="validation-error" role="alert">{recover.error.message}</p> : null}
  </section>;
}
