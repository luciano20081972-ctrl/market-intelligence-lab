import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function Operations() {
  const queryClient = useQueryClient();
  const queueQuery = useQuery({ queryKey: ["operations-queue"], queryFn: api.operationQueue, refetchInterval: 10_000 });
  const workersQuery = useQuery({ queryKey: ["operations-workers"], queryFn: api.operationWorkers, refetchInterval: 10_000 });
  const healthQuery = useQuery({ queryKey: ["operations-health"], queryFn: api.operationHealth, refetchInterval: 10_000 });
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
  if (queueQuery.isLoading || workersQuery.isLoading || healthQuery.isLoading) return <LoadingState label="Loading queue and workers" />;
  if (queueQuery.error) return <ErrorState error={queueQuery.error} />;
  if (workersQuery.error) return <ErrorState error={workersQuery.error} />;
  if (healthQuery.error) return <ErrorState error={healthQuery.error} />;
  const queue = queueQuery.data!;
  const workers = workersQuery.data?.items ?? [];
  return <section><div className="page-heading"><div><p className="eyebrow">OPERATIONS</p><h1>Queue dashboard</h1><p>Durable job depth, failures, leases, and persisted worker heartbeats.</p></div><button type="button" className="secondary" disabled={recover.isPending} onClick={() => recover.mutate()}>{recover.isPending ? "Recovering…" : "Recover abandoned jobs"}</button></div>
    <div className="metric-grid"><article><span>Queue depth</span><strong>{queue.depth}</strong></article><article><span>Running</span><strong>{queue.running}</strong></article><article><span>Failed / dead letter</span><strong>{queue.failed}</strong></article><article><span>Overall</span><strong>{String(healthQuery.data?.status ?? "unknown")}</strong></article></div>
    <h2 className="section-title">Queue state</h2><div className="source-grid">{Object.entries(queue.by_status).map(([state, count]) => <article className="panel" key={state}><span>{state}</span><strong className="large-number">{count}</strong></article>)}</div>
    <h2 className="section-title">Workers</h2>{workers.length === 0 ? <EmptyState title="No worker registered" detail="Start python -m packages.market_data.worker to process queued imports." /> : <div className="table-card"><table><thead><tr><th>Worker</th><th>Status</th><th>Heartbeat</th><th>Current job</th></tr></thead><tbody>{workers.map(worker => <tr key={worker.id}><td>{worker.worker_identifier}</td><td><span className="status-chip">{worker.status}</span></td><td>{new Date(worker.last_heartbeat_at).toLocaleString()}</td><td>{worker.current_job_id ?? "Idle"}</td></tr>)}</tbody></table></div>}
    {recover.data ? <p className="success-message" role="status">Recovered {recover.data.count} abandoned job(s).</p> : null}{recover.error ? <p className="validation-error" role="alert">{recover.error.message}</p> : null}
  </section>;
}
