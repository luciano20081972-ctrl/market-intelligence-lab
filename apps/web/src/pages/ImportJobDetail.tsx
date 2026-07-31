import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function ImportJobDetail() {
  const { id = "" } = useParams();
  const queryClient = useQueryClient();
  const jobQuery = useQuery({ queryKey: ["import-job", id], queryFn: () => api.importJob(id), enabled: Boolean(id) });
  const eventsQuery = useQuery({ queryKey: ["import-job-events", id], queryFn: () => api.importJobEvents(id), enabled: Boolean(id) });
  const qualityQuery = useQuery({ queryKey: ["import-job-quality", id], queryFn: () => api.importJobQuality(id), enabled: Boolean(id) });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["import-job", id] }),
      queryClient.invalidateQueries({ queryKey: ["import-job-events", id] }),
      queryClient.invalidateQueries({ queryKey: ["import-job-quality", id] }),
    ]);
  };
  const cancel = useMutation({ mutationFn: () => api.cancelImportJob(id), onSuccess: refresh });
  const retry = useMutation({ mutationFn: () => api.retryImportJob(id), onSuccess: refresh });
  if (jobQuery.isLoading || eventsQuery.isLoading || qualityQuery.isLoading) return <LoadingState label="Loading import timeline" />;
  if (jobQuery.error) return <ErrorState error={jobQuery.error} />;
  if (eventsQuery.error) return <ErrorState error={eventsQuery.error} />;
  if (qualityQuery.error) return <ErrorState error={qualityQuery.error} />;
  const job = jobQuery.data!;
  const events = eventsQuery.data ?? [];
  const canCancel = ["queued", "running", "retrying"].includes(job.status);
  const canRetry = ["failed", "retrying", "interrupted", "cancelled"].includes(job.status);
  return <section><div className="page-heading"><div><p className="eyebrow">IMPORT {job.id.slice(0, 8)}</p><h1>{job.provider_code} · {job.status}</h1><p>{job.mode} import for {job.symbols.join(", ")} · {job.adjustment_preference}</p></div><div className="button-row"><button type="button" className="secondary" disabled={!canCancel || cancel.isPending} onClick={() => cancel.mutate()}>Cancel</button><button type="button" disabled={!canRetry || retry.isPending} onClick={() => retry.mutate()}>{retry.isPending ? "Retrying…" : "Retry"}</button></div></div>
    <div className="metric-grid"><article><span>Processed</span><strong>{job.records_processed}</strong></article><article><span>Inserted</span><strong>{job.records_inserted}</strong></article><article><span>Skipped</span><strong>{job.records_skipped}</strong></article><article><span>Duration</span><strong>{job.processing_duration_ms} ms</strong></article></div>
    <div className="detail-grid"><article className="panel"><h2>Provenance</h2><dl className="detail-list"><div><dt>Provider</dt><dd>{job.provider_code}</dd></div><div><dt>Queue</dt><dd>{job.queue_name}</dd></div><div><dt>Attempt</dt><dd>{job.attempt} / {job.max_attempts}</dd></div><div><dt>Resume cursor</dt><dd><code>{JSON.stringify(job.resume_cursor)}</code></dd></div><div><dt>Dry run</dt><dd>{job.dry_run ? "Yes" : "No"}</dd></div></dl></article><article className="panel"><h2>Quality report</h2><pre className="json-block">{JSON.stringify(qualityQuery.data?.report ?? {}, null, 2)}</pre></article></div>
    {job.error_summary ? <div className="state-card error" role="alert">{job.error_summary}</div> : null}
    <h2 className="section-title">Timeline</h2>{events.length === 0 ? <EmptyState title="No job events" detail="Events appear as the durable worker advances this job." /> : <ol className="timeline">{events.map(event => <li key={event.id}><strong>{event.event_type}</strong><span>{event.from_status ?? "created"} → {event.to_status ?? "unchanged"}</span><p>{event.message}</p><time dateTime={event.created_at}>{new Date(event.created_at).toLocaleString()}</time></li>)}</ol>}
    <h2 className="section-title">Batches</h2><div className="table-card"><table><thead><tr><th>#</th><th>Status</th><th>Processed</th><th>Inserted</th><th>Skipped</th><th>Checksum</th></tr></thead><tbody>{job.batches.map(batch => <tr key={batch.id}><td>{batch.sequence + 1}</td><td>{batch.status}</td><td>{batch.records_processed}</td><td>{batch.records_inserted}</td><td>{batch.records_skipped}</td><td><code>{batch.checksum.slice(0, 12) || "pending"}</code></td></tr>)}</tbody></table></div>
  </section>;
}
